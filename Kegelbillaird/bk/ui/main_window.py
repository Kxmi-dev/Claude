"""
Hauptfenster: verbindet Bildschirme, Speicherung, PDF und NumLock.

Bildschirmfolge::

    Start ─► (Unterbrochene Partie? ─► FORTSETZEN ─► Zählansicht)
         └─► Hauptmenü ─► Zählansicht ─► Abschluss ─► Auswertung ─► Hauptmenü
                      └─► Archiv ─► Auswertung | Wiedergabe | Weiterspielen

Tastatur: Alle Unterelemente sind fokuslos; Tastendrücke landen genau
einmal in ``keyPressEvent`` und werden an die sichtbare Karte bzw. den
aktiven Bildschirm weitergegeben.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCursor, QDesktopServices, QIcon, QKeyEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QStackedWidget, QVBoxLayout, QWidget

from .. import numlock, power
from ..game import Game, GameError
from ..maintenance import run_cleanup
from ..models import GameMode, GameState, GameStatus
from ..pdf_report import PdfError, report_base_name, write_report
from ..settings import AppSettings
from ..storage import ArchiveEntry, GameStorage, LoadStatus, StorageError
from ..user_settings import UserSettingsStore
from . import keymap, theme
from .archive_screen import ArchiveScreen
from .game_screen import GameScreen
from .menu_screen import MenuScreen
from .result_screen import ResultScreen
from .settings_screen import SettingsScreen
from .overlays import Overlay, OverlayContent
from .widgets import FooterBar, TitleBar, format_points

log = logging.getLogger(__name__)

_MOUSE_EVENTS = (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel,
                 QEvent.Type.HoverMove)

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

    def update_settings(self, auto_enable: bool, interval_seconds: float) -> None:
        self._auto_enable = auto_enable
        self._timer.setInterval(int(interval_seconds * 1000))

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
    def __init__(self, settings: AppSettings, storage: GameStorage,
                 store: UserSettingsStore | None = None) -> None:
        super().__init__()
        keymap.configure(settings.key_bindings)   # Tastenbelegung
        theme.apply_colors(settings.theme_mode, settings.primary_color, settings.secondary_color)
        theme.set_font_scale(settings.font_scale)
        # Ohne Angabe: Speicher ohne Laden (Tests); main.py übergibt den geladenen Speicher
        self._store = store if store is not None else UserSettingsStore(settings)
        self._force_windowed = False
        self._settings = settings
        self._storage = storage
        self._background: QPixmap | None = None
        self._started = False
        self._overlay_handler = None
        self._last_result_path: str | None = None
        self._on_top_suspended = False   # „immer im Vordergrund“ kurz aus, solange ein geöffnetes PDF vorne ist
        self._left_window = False
        self._cursor_hidden = False
        self._cursor_pos = QCursor.pos()
        self._cursor_timer = QTimer(self)    # Mauszeiger nach x s ohne Mausbewegung ausblenden
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.timeout.connect(lambda: self._apply_cursor(True))

        self.setWindowTitle(f"{settings.app_title} {settings.app_version}")
        if settings.icon_path.is_file():
            self.setWindowIcon(QIcon(str(settings.icon_path)))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 480)

        self.title_bar = TitleBar(settings.icon_path, settings.club_name)
        self.title_bar.set_logo(settings.club_logo_path)
        self.footer = FooterBar()
        self.stack = QStackedWidget()
        self.menu_screen = MenuScreen(settings)
        self.game_screen = GameScreen(settings, storage)
        self.archive_screen = ArchiveScreen(settings, storage)
        self.result_screen = ResultScreen(settings)
        self.settings_screen = SettingsScreen(self._store)
        self.settings_screen.preview_sound = self.game_screen.play_sound
        for screen in (self.menu_screen, self.archive_screen, self.game_screen, self.settings_screen,
                       self.result_screen):
            self.stack.addWidget(screen)
        self._result_close = None

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
        self.menu_screen.shutdown_requested.connect(self.quit_and_shutdown)
        self.menu_screen.archive_requested.connect(self.show_archive)
        self.menu_screen.settings_requested.connect(self.show_settings)
        self.result_screen.closed.connect(self._close_result)
        self.result_screen.new_game_requested.connect(self._new_game_from_result)
        self.result_screen.message.connect(self._flash)
        self.result_screen.footer_changed.connect(self._refresh_footer)
        self.settings_screen.back_requested.connect(self._settings_back)
        self.settings_screen.settings_changed.connect(self.apply_settings)
        self.settings_screen.notice.connect(self._flash)
        self.settings_screen.footer_changed.connect(self._refresh_footer)
        self.archive_screen.entry_chosen.connect(self._on_archive_entry)
        self.archive_screen.back_requested.connect(self._archive_back)
        self.game_screen.footer_changed.connect(self._refresh_footer)
        self.game_screen.replay_exit.connect(self.show_archive)
        self.game_screen.replay_stats.connect(self._show_archive_report)
        self.menu_screen.notice.connect(self._flash)
        self.game_screen.completed.connect(self._finalize_game)
        self.game_screen.abort_confirmed.connect(self._abort_game)
        self.game_screen.abort_prompt.connect(self._on_abort_prompt)
        self.game_screen.correction_prompt.connect(self._on_correction_prompt)
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

    def quit_and_shutdown(self) -> None:
        """„Beenden & Herunterfahren“: alles sichern, Windows sofort herunterfahren, Programm schließen.
        Schlägt das Herunterfahren fehl, bleibt das Programm offen und zeigt einen Hinweis.
        Außerhalb von Windows wird nur beendet."""
        if self.game_screen.has_live_game:
            self.game_screen.stop()
            self.game_screen.persist_now()
        if not self.shutdown_supported():
            log.info("Herunterfahren nur unter Windows – Programm wird nur beendet")
            self.close()
            return
        ok, message = self.shutdown_computer()
        if ok:
            self.close()
        else:
            self._flash(message, True)

    # austauschbar für Tests
    shutdown_supported = staticmethod(power.shutdown_supported)
    shutdown_computer = staticmethod(power.shutdown)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self._on_top_suspended:
            if not self.isActiveWindow():
                self._left_window = True
            elif self._left_window:          # zurück im Scoreboard -> wieder immer im Vordergrund
                self._on_top_suspended = False
                QTimer.singleShot(0, self._apply_window_mode)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cursor_timer.stop()
        QApplication.instance().removeEventFilter(self)
        self._apply_cursor(False)
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

    # ========================================================= Einstellungen
    def show_settings(self) -> None:
        self.settings_screen.open_page()
        self._show_screen(self.settings_screen)

    def _settings_back(self) -> None:
        self.show_menu()
        self.menu_screen.select_settings()

    def show_window(self, force_windowed: bool = False) -> None:
        """Erstes Anzeigen: Vollbild oder Fenster in der eingestellten Größe."""
        self._force_windowed = force_windowed
        self._apply_window_mode(first=True)
        QApplication.instance().installEventFilter(self)   # Mausbewegungen im ganzen Programm
        self._restart_cursor_timer()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind in _MOUSE_EVENTS:
            pos = QCursor.pos()
            # Windows schickt auch ohne echte Bewegung Mausereignisse -> nur zählen, wenn sich etwas tut
            if kind not in (QEvent.Type.MouseMove, QEvent.Type.HoverMove) or pos != self._cursor_pos:
                self._cursor_pos = pos
                self._apply_cursor(False)
                self._restart_cursor_timer()
        return False

    def _restart_cursor_timer(self) -> None:
        seconds = self._settings.hide_cursor_seconds
        if seconds > 0:
            self._cursor_timer.start(int(seconds * 1000))
        else:
            self._cursor_timer.stop()
            self._apply_cursor(False)

    def _apply_cursor(self, hidden: bool) -> None:
        """Mauszeiger im ganzen Programm aus-/einblenden (HIDE_CURSOR_SECONDS)."""
        if hidden == self._cursor_hidden:
            return
        self._cursor_hidden = hidden
        if hidden:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))
        else:
            QApplication.restoreOverrideCursor()

    @property
    def stays_on_top(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def _open_external(self, path: str) -> None:
        """Datei im Windows-Programm öffnen; „immer im Vordergrund“ ruht, bis das Scoreboard wieder aktiv ist."""
        if self._settings.stay_on_top and self.isVisible():
            self._on_top_suspended = True
            self._left_window = False
            self._apply_window_mode()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _apply_window_mode(self, first: bool = False) -> None:
        s = self._settings
        on_top = s.stay_on_top and not self._on_top_suspended
        if on_top != self.stays_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)   # versteckt das Fenster -> unten neu zeigen
        if s.fullscreen and not self._force_windowed:
            self.showFullScreen()
            return
        if self.isFullScreen() or first:
            self.showNormal()
        width, height = s.window_size
        screen = self.screen().availableGeometry() if self.screen() is not None else None
        if screen is not None:
            width, height = min(width, screen.width()), min(height, screen.height())
        self.resize(width, height)
        if screen is not None:
            self.move(screen.center().x() - width // 2, screen.center().y() - height // 2)
        self.show()

    def apply_settings(self, settings: AppSettings) -> None:
        """Im Einstellungsmenü geänderte Werte sofort übernehmen."""
        old = self._settings
        self._settings = settings
        keymap.configure(settings.key_bindings)
        theme.apply_colors(settings.theme_mode, settings.primary_color, settings.secondary_color)
        theme.set_font_scale(settings.font_scale)
        self.title_bar.set_club(settings.club_name)
        self.game_screen.set_settings(settings)
        self.result_screen.set_settings(settings)
        if old.club_logo_path != settings.club_logo_path:
            self._load_club_logo()
        self.numlock_guard.update_settings(settings.auto_enable_numlock, settings.numlock_check_seconds)
        if ((old.fullscreen, old.window_size, old.stay_on_top)
                != (settings.fullscreen, settings.window_size, settings.stay_on_top) and self.isVisible()):
            self._apply_window_mode()
        if self.isVisible():
            self._restart_cursor_timer()
        self._background = None
        for widget in [self] + self.findChildren(QWidget):
            widget.update()
        self._refresh_footer()

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
        actions = [("AUSWERTUNG ANZEIGEN", lambda: self._show_archive_report(state)),
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
        status = {GameStatus.FINISHED: "beendet", GameStatus.ABORTED: "abgebrochen"}.get(state.status, "unterbrochen")
        from_replay = self.stack.currentWidget() is self.game_screen and self.game_screen.is_replay
        back = (lambda: self._show_screen(self.game_screen)) if from_replay else self.show_archive
        self.show_result(state, f"aus dem Archiv – Partie {status}", on_close=back, close_label="Zurück")

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

    # ============================================================ Auswertung
    def show_result(self, state: GameState, note: str = "", on_close=None, close_label: str = "Hauptmenü",
                    after_game: bool = False) -> bool:
        """Auswertung im Hauptfenster anzeigen (kein Extra-Fenster). Direkt nach einer Partie
        mit „Neue Partie“ und kurzer Eingabesperre gegen versehentlichen Doppeldruck."""
        try:
            self.result_screen.show_state(state, note, close_label, offer_new_game=after_game,
                                          lock_seconds=self._settings.result_lock_seconds if after_game else 0.0)
        except Exception:
            log.exception("Auswertung konnte nicht angezeigt werden")
            self._flash("Auswertung konnte nicht angezeigt werden – siehe logs/application.log", True)
            return False
        self._result_close = on_close
        self.footer.clear_flash()        # alte Kurzmeldungen (z. B. "Letzter Stoß …") ausblenden
        self._show_screen(self.result_screen)
        log.info("Auswertung angezeigt: %s vom %s", state.mode.key, state.started_at)
        return True

    def _new_game_from_result(self, mode: GameMode) -> None:
        """„Neue Partie“ in der Auswertung: dieselbe Spielart sofort neu starten."""
        current = next((m for m in self._settings.game_modes if m.key == mode.key and m.available), None)
        if current is None:
            self._flash(f"Spielart „{mode.title}“ ist nicht mehr verfügbar.", True)
            return
        self._result_close = None
        self._start_new_game(current)

    def _close_result(self) -> None:
        action, self._result_close = self._result_close, None
        (action or self.show_menu)()

    def _flash(self, text: str, warning: bool = False) -> None:
        self.footer.flash(text, warning, 3.0 if warning else 2.5)

    # ======================================================= Programmstart
    def _startup(self) -> None:
        self.settings_screen.autostart.refresh()   # Programmordner verschoben -> Autostart-Pfad korrigieren
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.numlock_guard.supported:
            self.numlock_guard.check()          # beim Start prüfen (und ggf. einschalten)
            self.numlock_guard.start_watch()    # danach regelmäßig überwachen
        else:
            log.info("NumLock-Prüfung ist nur unter Windows verfügbar")
        self.run_cleanup()
        self._cleanup_timer.start()
        for text in self._store.warnings:      # z. B. beschädigte einstellungen.json
            self.footer.flash(text, True, seconds=6)
        self._load_club_logo()
        self._check_unfinished_game()

    def _load_club_logo(self) -> None:
        """Vereinslogo im Hauptmenü und klein in der Titelleiste."""
        path = self._settings.club_logo_path
        ok = self.menu_screen.set_club_logo(path)
        self.title_bar.set_logo(path if ok else None)
        if not ok:
            self._club_logo_warning()

    def _club_logo_warning(self) -> None:
        log.warning("Vereinslogo nicht lesbar: %s", self._settings.club_logo_path)
        self.footer.flash(f"Vereinslogo „{self._settings.club_logo}“ fehlt oder ist nicht lesbar.", True, seconds=6)

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
        self.game_screen.play_sound(self._settings.end_sound)

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
                                    self._settings.app_title, self._settings.club_logo_path,   # im PDF nur das Vereinslogo
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
            self._open_external(self._last_result_path)
        if pdf_ok and self._settings.show_report_after_game:
            note = f"PDF automatisch gespeichert: {pdf_path.parent.name}\\{pdf_path.name}"
            if recovered:
                note += "   (Abschluss nach Programmneustart nachgeholt)"
            if self.show_result(state, note, on_close=self.show_menu, after_game=True):
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

    def _on_correction_prompt(self, info) -> None:
        """Korrekturfeld: alte Punktzahl anzeigen, neue Punktzahl wird eingetippt (None = schließen)."""
        if info is None:
            if self.overlay.isVisible() and not self.overlay.interactive:
                self.overlay.close_overlay()
            return
        number, old, new, minus = info
        if new is None:
            new_text = "\u2212 _" if minus else "_"
        else:
            new_text = format_points(new)
        self.overlay.show_content(OverlayContent(
            f"Korrektur  Stoß {number}",
            [f"Bestätigen = [{keymap.label('enter')}]      Abbrechen = [{keymap.label('abort')}]"],
            top_lines=[f"Alte Punktzahl:   {format_points(old)}"],
            big=f"Neue Punktzahl:   {new_text}",
            hint=f"Minus: erst [{keymap.label('minus')}], dann [0] bis [7]. Nur der letzte Stoß ist änderbar.",
            highlight=True, interactive=False))

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
