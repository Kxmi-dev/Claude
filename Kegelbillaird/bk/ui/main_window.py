"""
Hauptfenster: verbindet Bildschirme, Speicherung, PDF und NumLock.

Bildschirmfolge::

    Start ─► (Unterbrochene Partie? ─► FORTSETZEN ─► Zählansicht)
         └─► Hauptmenü ─► Zählansicht ─► Abschluss ─► Statistik-Fenster ─► Hauptmenü
                      └─► Archiv ─► Statistik-Fenster | Wiedergabe | Weiterspielen

Tastatur: Alle Unterelemente sind fokuslos; Tastendrücke landen genau
einmal in ``keyPressEvent`` und werden an die sichtbare Karte bzw. den
aktiven Bildschirm weitergegeben.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeyEvent, QPainter, QPixmap
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from .. import numlock
from ..game import Game, GameError
from ..maintenance import run_cleanup
from ..models import GameMode, GameState, GameStatus
from ..pdf_report import PdfError, report_base_name, write_report
from ..settings import AppSettings
from ..storage import ArchiveEntry, GameStorage, LoadStatus, StorageError
from . import keymap, theme
from .archive_screen import ArchiveScreen
from .game_screen import GameScreen
from .menu_screen import MenuScreen
from .overlays import Overlay, OverlayContent
from .widgets import FooterBar, TitleBar

log = logging.getLogger(__name__)

CLEANUP_INTERVAL_MS = 6 * 60 * 60 * 1000


class NumLockGuard(QObject):
    """Prüft NumLock beim Start und danach regelmäßig; schaltet es bei Bedarf ein.

    Schutz gegen Hin-und-her-Schalten: Ein Einschaltversuch nur, wenn das
    eigene Fenster aktiv ist, frühestens 3 s nach dem letzten Versuch und
    höchstens 3-mal, bis NumLock wieder als eingeschaltet erkannt wurde.
    """

    status = Signal(object)  # Warntext oder None

    RETRY_SECONDS = 3.0
    MAX_ATTEMPTS = 3

    def __init__(self, window: QWidget, auto_enable: bool, interval_seconds: float) -> None:
        super().__init__(window)
        self._window = window
        self._supported = numlock.is_supported()
        self._auto_enable = auto_enable
        self._attempts = 0
        self._last_attempt = -1e9
        self._timer = QTimer(self)
        self._timer.setInterval(int(interval_seconds * 1000))
        self._timer.timeout.connect(self.check)

    @property
    def supported(self) -> bool:
        return self._supported

    def start_watch(self) -> None:
        if self._supported:
            self._timer.start()

    def stop_watch(self) -> None:
        self._timer.stop()

    def check(self) -> None:
        """NumLock prüfen; bei AUTO_ENABLE_NUMLOCK einschalten, sonst nur warnen."""
        if not self._supported:
            return
        state = numlock.is_numlock_on()
        if state is None:
            return
        if state:
            self._attempts = 0
            self.status.emit(None)
            return
        now = time.monotonic()
        can_try = (self._auto_enable and self._window.isActiveWindow() and self._attempts < self.MAX_ATTEMPTS
                   and now - self._last_attempt >= self.RETRY_SECONDS)
        if can_try:
            self._attempts += 1
            self._last_attempt = now
            result = numlock.ensure_numlock_on()
            log.info("NumLock-Einschaltversuch %s: %s", self._attempts, result.value)
            self.status.emit("NUM-LOCK ist aus – wird eingeschaltet …")
            QTimer.singleShot(700, self._verify)
        else:
            self.status.emit("NUM-LOCK IST AUS – bitte die Taste [Num] drücken")

    def _verify(self) -> None:
        state = numlock.is_numlock_on()
        if state:
            self._attempts = 0
            self.status.emit(None)
        elif state is False:
            log.warning("NumLock ist nach Einschaltversuch weiterhin aus")
            self.status.emit("NUM-LOCK IST AUS – bitte die Taste [Num] drücken")


class MainWindow(QWidget):
    def __init__(self, settings: AppSettings, storage: GameStorage) -> None:
        super().__init__()
        keymap.configure(settings.key_bindings)   # Tastenbelegung aus config.py
        self._settings = settings
        self._storage = storage
        self._background: QPixmap | None = None
        self._started = False
        self._overlay_handler = None
        self._last_result_path: str | None = None

        self.setWindowTitle(f"{settings.app_title} {settings.app_version}")
        if settings.icon_path.is_file():
            self.setWindowIcon(QIcon(str(settings.icon_path)))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 480)

        self.title_bar = TitleBar(settings.icon_path, settings.club_name)
        self.footer = FooterBar()
        self.stack = QStackedWidget()
        self.menu_screen = MenuScreen(settings)
        self.game_screen = GameScreen(settings, storage)
        self.archive_screen = ArchiveScreen(settings, storage)
        for screen in (self.menu_screen, self.archive_screen, self.game_screen):
            self.stack.addWidget(screen)
        self._report_dialog = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.footer)

        self.overlay = Overlay(self)
        self.overlay.choice_made.connect(self._on_overlay_choice)

        self.numlock_guard = NumLockGuard(self, settings.auto_enable_numlock, settings.numlock_check_seconds)
        self.numlock_guard.status.connect(lambda text: self.footer.set_warning("numlock", text))

        self.menu_screen.mode_chosen.connect(self._start_new_game)
        self.menu_screen.quit_requested.connect(self.close)
        self.menu_screen.archive_requested.connect(self.show_archive)
        self.archive_screen.entry_chosen.connect(self._on_archive_entry)
        self.archive_screen.back_requested.connect(self._archive_back)
        self.game_screen.footer_changed.connect(self._refresh_footer)
        self.game_screen.replay_exit.connect(self.show_archive)
        self.game_screen.replay_stats.connect(self._show_archive_report)
        self.menu_screen.notice.connect(self._flash)
        self.game_screen.completed.connect(self._finalize_game)
        self.game_screen.abort_confirmed.connect(self._abort_game)
        self.game_screen.abort_prompt.connect(self._on_abort_prompt)
        self.game_screen.message.connect(self._flash)
        self.game_screen.warning.connect(self.footer.set_warning)

        self._show_screen(self.menu_screen)

        # Aufräumen alter Dateien: beim Start und danach alle 6 Stunden
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(CLEANUP_INTERVAL_MS)
        self._cleanup_timer.timeout.connect(self.run_cleanup)

    # ============================================================ Fenster
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._started:
            self._started = True
            QTimer.singleShot(300, self._startup)

    def resizeEvent(self, event) -> None:  # noqa: N802
        unit = theme.ui_unit(self.width(), self.height())
        bar_h = max(22, round(33 * unit))
        self.title_bar.setFixedHeight(bar_h)
        self.footer.setFixedHeight(bar_h)
        self.game_screen.apply_unit(unit)
        self.overlay.setGeometry(self.rect())
        self._background = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._background is None or self._background.size() != self.size():
            self._background = theme.make_background(self.width(), self.height())
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background)
        painter.end()

    def focusNextPrevChild(self, next_child: bool) -> bool:  # noqa: N802
        return False  # Tab wechselt keinen Fokus

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.game_screen.has_live_game:      # nie bei einer Wiedergabe
            self.game_screen.stop()
            self.game_screen.persist_now()
            log.info("Programm beendet – laufende Partie gesichert (kann fortgesetzt werden)")
        log.info("Programm beendet")
        super().closeEvent(event)

    # ============================================================ Tastatur
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._dispatch_key(event):
            super().keyPressEvent(event)

    def _dispatch_key(self, event: QKeyEvent) -> bool:
        if self.overlay.interactive:
            return self.overlay.handle_key(event)
        screen = self.stack.currentWidget()
        try:
            return bool(screen.handle_key(event))
        except Exception:  # Bedienfehler dürfen das Programm nie beenden
            log.exception("Fehler bei der Tastenverarbeitung")
            self._flash("Interner Fehler bei der Eingabe – siehe logs/application.log", True)
            return True

    # ========================================================== Bildschirme
    def _show_screen(self, screen: QWidget) -> None:
        self.stack.setCurrentWidget(screen)
        self.title_bar.set_title(screen.title())
        self.footer.set_segments(screen.footer_segments())
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_menu(self) -> None:
        self.menu_screen.reset_selection()
        self._show_screen(self.menu_screen)

    def _refresh_footer(self) -> None:
        screen = self.stack.currentWidget()
        self.title_bar.set_title(screen.title())
        if not self.overlay.interactive:
            self.footer.set_segments(screen.footer_segments())

    # =============================================================== Archiv
    def show_archive(self) -> None:
        self.game_screen.clear()          # beendet ggf. eine laufende Wiedergabe
        self.archive_screen.reload()
        self._show_screen(self.archive_screen)

    def _archive_back(self) -> None:
        self.show_menu()
        self.menu_screen.select_archive()

    def _on_archive_entry(self, entry: ArchiveEntry) -> None:
        state = entry.state
        game = Game(state)
        started = datetime.fromisoformat(state.started_at)
        actions = [("STATISTIK ANZEIGEN", lambda: self._show_archive_report(state)),
                   ("WIEDERGABE", lambda: self._start_replay(state))]
        if entry.can_continue:
            actions.append(("WEITERSPIELEN", lambda: self._continue_archived(entry)))
        actions.append(("ZURÜCK", None))
        lines = [f"{state.mode.title}   ·   {started:%d.%m.%Y} um {started:%H:%M} Uhr",
                 f"{entry.status_label.capitalize()}   ·   {game.played} von {game.max_strokes} Stößen"
                 f"   ·   {game.total} Punkte"]

        def handler(index: int) -> None:
            action = actions[index][1]
            if action is not None:
                action()

        self._ask(OverlayContent("Partie aus dem Archiv", lines, choices=[label for label, _ in actions],
                                 back_choice=len(actions) - 1), handler)

    def _show_archive_report(self, state: GameState) -> None:
        started = datetime.fromisoformat(state.started_at)
        game = Game(state)
        status = {GameStatus.FINISHED: "beendet", GameStatus.ABORTED: "abgebrochen"}.get(state.status, "unterbrochen")
        self.show_report(state, f"Statistik  –  {state.mode.title} vom {started:%d.%m.%Y}",
                         f"Partie {status}   ·   {game.played} von {game.max_strokes} Stößen   ·   "
                         f"Ergebnis: {game.total}")

    def _start_replay(self, state: GameState) -> None:
        log.info("Wiedergabe: %s vom %s", state.mode.key, state.started_at)
        self.game_screen.start_replay(state, self._settings.replay_seconds_per_stroke)
        self._show_screen(self.game_screen)

    def _continue_archived(self, entry: ArchiveEntry) -> None:
        try:
            state = self._storage.restore_from_archive(entry)
        except StorageError as exc:
            log.error("Weiterspielen nicht möglich: %s", exc)
            self._flash(f"Weiterspielen nicht möglich: {exc}", True)
            return
        log.info("Archivierte Partie wird weitergespielt (%s Stöße)", len(state.strokes))
        self._enter_game(Game(state))
        self._flash("Partie aus dem Archiv wird fortgesetzt.")

    # ======================================================= Statistik-Fenster
    def show_report(self, state: GameState, heading: str, note: str = "", on_close=None) -> bool:
        """Öffnet das Statistik-Fenster (Spielbericht mit Speichern / Drucken / Schließen)."""
        try:
            from .report_dialog import ReportDialog   # erst hier laden: Fehler dürfen den Start nie verhindern
            dialog = ReportDialog(self, state, self._settings, heading, note)
        except Exception:
            log.exception("Statistik-Fenster konnte nicht geöffnet werden")
            self._flash("Statistik-Fenster konnte nicht geöffnet werden – siehe logs/application.log", True)
            return False
        self._report_dialog = dialog
        self.footer.clear_flash()        # alte Kurzmeldungen (z. B. "Letzter Stoß …") ausblenden

        def closed(_result: int) -> None:
            self._report_dialog = None
            dialog.deleteLater()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            if on_close is not None:
                on_close()

        dialog.finished.connect(closed)
        dialog.open()
        log.info("Statistik-Fenster geöffnet: %s vom %s", state.mode.key, state.started_at)
        return True

    def _flash(self, text: str, warning: bool = False) -> None:
        self.footer.flash(text, warning, 3.0 if warning else 2.5)

    # ======================================================= Programmstart
    def _startup(self) -> None:
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.numlock_guard.supported:
            self.numlock_guard.check()          # beim Start prüfen (und ggf. einschalten)
            self.numlock_guard.start_watch()    # danach regelmäßig überwachen
        else:
            log.info("NumLock-Prüfung ist nur unter Windows verfügbar")
        self.run_cleanup()
        self._cleanup_timer.start()
        self._check_unfinished_game()

    def run_cleanup(self) -> None:
        """Löscht Archiv-, Log- (und ggf. Ergebnis-)Dateien, die älter als eingestellt sind."""
        s = self._settings
        run_cleanup(s.data_dir, s.logs_dir, s.results_dir, s.archive_retention_days,
                    s.log_retention_days, s.results_retention_days)

    def _check_unfinished_game(self) -> None:
        result = self._storage.load_active()
        if result.status is LoadStatus.NONE:
            return
        if result.status is LoadStatus.CORRUPT:
            moved = self._storage.quarantine_corrupt()
            log.error("Spielstand beschädigt, verschoben nach: %s", moved)
            self._ask(OverlayContent(
                "Spielstand beschädigt",
                ["Die gespeicherte Partie konnte nicht gelesen werden.",
                 "Die Dateien wurden nach „data/corrupt“ verschoben.",
                 "Es kann eine neue Partie gestartet werden."],
                choices=["OK"], warning=True), lambda _i: self.show_menu())
            return
        state = result.state
        assert state is not None
        if state.status is GameStatus.FINISHED:
            log.info("Beendete, aber nicht abgeschlossene Partie gefunden – Abschluss wird nachgeholt")
            self._complete_finished_state(state, recovered=True)
            return
        if state.status is GameStatus.ABORTED:
            self._safe_archive(state, "abgebrochen")
            return
        game = Game(state)
        started = datetime.fromisoformat(state.started_at)
        lines = [
            f"Spielart: {state.mode.title}",
            f"Stand: {game.played} von {game.max_strokes} Stößen gespielt   ·   {game.total} Punkte",
            f"Begonnen am {started:%d.%m.%Y} um {started:%H:%M} Uhr",
        ]
        if result.status is LoadStatus.RECOVERED:
            lines.append("Aus Sicherungskopie wiederhergestellt – bitte letzten Stoß prüfen!")
        lines.append("Möchtest du die letzte Partie fortsetzen?")
        self._ask(OverlayContent("Unterbrochene Partie gefunden", lines,
                                 choices=["PARTIE FORTSETZEN", "NEUE PARTIE"],
                                 hint=f"Wählen mit [{keymap.label('down')}] & [{keymap.label('up')}]   |   Bestätigen mit [{keymap.label('enter')}]"),
                  lambda choice: self._resume_choice(choice, state))

    def _resume_choice(self, choice: int, state: GameState) -> None:
        if choice == 0:
            log.info("Partie wird fortgesetzt (%s Stöße gespielt)", len(state.strokes))
            self._enter_game(Game(state))
            self._flash("Partie fortgesetzt.")
        else:
            self._safe_archive(state, "verworfen")
            self.show_menu()
            self._flash("Unterbrochene Partie archiviert (data/archive). Neue Partie wählen.")

    # ========================================================= Neue Partie
    def _start_new_game(self, mode: GameMode) -> None:
        """Im Hauptmenü gewählte Spielart sofort starten (Datum/Uhrzeit automatisch)."""
        if self._storage.has_active_files():
            # Sollte nie vorkommen – vorsichtshalber nichts überschreiben, sondern sichern
            loaded = self._storage.load_active()
            if loaded.state is not None:
                self._safe_archive(loaded.state, "verworfen")
            else:
                self._storage.quarantine_corrupt()
        try:
            state = GameState.new(mode)
        except ValueError as exc:
            self._flash(str(exc), True)
            return
        try:
            self._storage.save_active(state)
            self.footer.set_warning("save", None)
        except StorageError:
            self.footer.set_warning("save", "ACHTUNG: Spielstand konnte nicht gespeichert werden!")
        log.info("Neue Partie: %s", mode.key)
        self._enter_game(Game(state))

    def _enter_game(self, game: Game) -> None:
        self.overlay.close_overlay()
        self.game_screen.start_game(game)
        self._show_screen(self.game_screen)
        self.numlock_guard.check()

    # ============================================================ Abschluss
    def _finalize_game(self) -> None:
        game = self.game_screen.game
        if game is None:
            return
        self.game_screen.stop()
        try:
            game.finish()
        except GameError as exc:
            log.error("Abschluss nicht möglich: %s", exc)
            self._flash(str(exc), True)
            return
        try:
            self._storage.save_active(game.state)   # Zustand "beendet" sichern, bevor das PDF entsteht
        except StorageError:
            log.error("Beendeter Zustand konnte nicht gesichert werden")
        self._complete_finished_state(game.state, recovered=False)

    def _complete_finished_state(self, state: GameState, recovered: bool) -> None:
        """Ergebnis-JSON, PDF, Archivierung und Abschlussanzeige."""
        game = Game(state)
        base = report_base_name(state)
        lines = [f"{state.mode.title}   ·   {game.played} Stöße"]
        try:
            self._storage.save_result(state, base)
        except StorageError as exc:
            log.error("Ergebnis-JSON konnte nicht gespeichert werden: %s", exc)
            lines.append("Ergebnisdatei konnte nicht gespeichert werden!")
        pdf_ok = False
        try:
            pdf_path = write_report(state, self._settings.results_dir, self._settings.club_name,
                                    self._settings.app_title, self._settings.logo_path,
                                    self._settings.pdf_rows_per_block, self._settings.pdf_blocks_per_row)
            pdf_ok = True
            self._last_result_path = str(pdf_path)
            lines.append(f"PDF gespeichert: {pdf_path.parent.name}/{pdf_path.name}")
        except PdfError as exc:
            lines.append("PDF konnte nicht erstellt werden – Details in logs/application.log")
            lines.append("Ergebnis ist in „results“ als JSON gesichert.")
            log.error("PDF-Fehler: %s", exc)
        self._safe_archive(state, "beendet")
        if recovered:
            lines.append("(Abschluss nach Programmneustart nachgeholt)")
        self.game_screen.clear()
        if recovered:
            self._show_screen(self.menu_screen)
        self.title_bar.set_title(f"Partie beendet: {state.mode.title}")
        if pdf_ok and self._settings.open_pdf_after_game and self._last_result_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_result_path))
        if pdf_ok and self._settings.show_report_after_game:
            note = f"PDF automatisch gespeichert: {pdf_path.parent.name}\\{pdf_path.name}"
            if recovered:
                note += "   (Abschluss nach Programmneustart nachgeholt)"
            self.footer.set_segments(["Statistik-Fenster geöffnet", f"Schließen mit  [{keymap.label('enter')}]  oder  [{keymap.label_all('back')}]"])
            if self.show_report(state, f"Partie beendet  –  ENDRESULTAT: {game.total}", note,
                                on_close=self.show_menu):
                return
        self.footer.set_segments([f"Weiter mit  [{keymap.label('enter')}]"])
        self._ask(OverlayContent("Partie beendet", lines, big=f"ENDRESULTAT: {game.total}",
                                 choices=["Weiter zum Hauptmenü"], hint=f"Weiter mit [{keymap.label('enter')}]",
                                 warning=not pdf_ok),
                  lambda _i: self.show_menu())

    # ============================================================= Abbruch
    def _on_abort_prompt(self, visible: bool, remaining: float) -> None:
        if visible:
            lines = [f"[{keymap.label('minus')}]   =   Ja, Partie abbrechen",
                     "jede andere Taste   =   Nein, weiterspielen",
                     f"Automatisch weiter in {max(1, int(remaining + 0.99))} s"]
            if self.overlay.isVisible() and not self.overlay.interactive:
                self.overlay.update_lines(lines)
            else:
                self.overlay.show_content(OverlayContent(
                    "Partie abbrechen?", lines,
                    hint="Abgebrochene Partien werden archiviert, es wird kein PDF erstellt.",
                    warning=True, interactive=False))
        elif self.overlay.isVisible() and not self.overlay.interactive:
            self.overlay.close_overlay()

    def _abort_game(self) -> None:
        game = self.game_screen.game
        if game is None:
            return
        self.overlay.close_overlay()
        self.game_screen.stop()
        try:
            game.abort()
            self._storage.save_active(game.state)
        except (GameError, StorageError) as exc:
            log.error("Abbruch konnte nicht gespeichert werden: %s", exc)
        self._safe_archive(game.state, "abgebrochen")
        self.game_screen.clear()
        self.show_menu()
        self._flash("Partie abgebrochen und archiviert (data/archive).")

    # ============================================================ Hilfen
    def _safe_archive(self, state: GameState | None, reason: str) -> None:
        try:
            path = self._storage.archive_active(state, reason)
            log.info("Spielstand archiviert (%s): %s", reason, path)
        except StorageError as exc:
            log.error("Archivieren fehlgeschlagen: %s", exc)
            self._flash("Spielstand konnte nicht archiviert werden – siehe Log.", True)

    def _ask(self, content: OverlayContent, handler) -> None:
        self._overlay_handler = handler
        self.footer.clear_flash()
        self.overlay.show_content(content)
        self.footer.set_segments(
            [f"Wählen mit  [{keymap.label('down')}]  &  [{keymap.label('up')}]",
             f"Bestätigen mit  [{keymap.label('enter')}]"]
            if len(content.choices) > 1 else [f"Weiter mit  [{keymap.label('enter')}]"])

    def _on_overlay_choice(self, index: int) -> None:
        handler = self._overlay_handler
        self._overlay_handler = None
        self.overlay.close_overlay()
        screen = self.stack.currentWidget()
        self.footer.set_segments(screen.footer_segments())
        if handler is not None:
            try:
                handler(index)
            except Exception:
                log.exception("Fehler bei der Auswahl")
                self._flash("Interner Fehler – siehe logs/application.log", True)
                self.show_menu()
