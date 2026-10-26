"""
Zählansicht einer laufenden Partie (Designvorlage 2).

Aufbau (Referenz 1024 × 768, per Layout-Streckfaktoren auf jede
Bildschirmgröße übertragen)::

    ┌ Stoß-Anzahl ┐ ┌ Punktestand ┐     ┌ Prognose ┐ ┌ Halbzeit ┐
    │             │ │             │     └──────────┘ └──────────┘
    └─────────────┘ └─────────────┘     ┌ Aktueller┐ ┌ Letzte   ┐
    ┌──────── Stoß-Raster 10 × n ─────┐ │  Stoß    │ │  Stöße   │
    │                                 │ └──────────┘ └──────────┘
    │                                 │ ┌ Minus ───┐ ┌ Eingabe ─┐
    │                                 │ └──────────┘ └──────────┘
    └─────────────────────────────────┘    ┌ Spieldauer ┐

Ablauf einer Wertung (ohne Bestätigungstaste)::

    Ziffer 0–7 (Plus)  bzw.  [−] → Ziffer 0–7 (Minus)
        → Wertung speichern → Punktestand → Stoßzähler → Spielstand sichern
        → Sperre (INPUT_LOCK_SECONDS) → BEREIT (wieder Plus)
    [Enter] während der Sperre → sofort BEREIT (abschaltbar: ENTER_SKIPS_LOCK)

Korrektur: [/] markiert den letzten Stoß im Raster gelb und fragt nach;
[Enter] nimmt ihn zurück, jede andere Taste (oder Zeitablauf) verwirft.

Nach dem letzten Stoß bleibt die Zählansicht stehen („ENDE“, Korrektur mit [/]
weiter möglich). Erst [Enter] meldet ``completed`` – dann schließt das
Hauptfenster die Partie ab und zeigt die Auswertung.

Wiedergabe (aus dem Archiv): Dieselbe Ansicht spielt eine gespeicherte
Partie Stoß für Stoß ab. Dabei wird eine KOPIE angezeigt – es wird nichts
gespeichert und keine Eingabe als Wertung ausgewertet.
[Enter] Pause/Weiter (am Ende: Auswertung), [+]/[−] Tempo, [*]/[Esc] beenden.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget

from ..game import Game, GameError
from ..media import SoundPlayer, active_images, pick_image, resolve_file
from ..input_logic import Action, GameKey, InputResult, ScoreInputController
from ..models import GameState, GameStatus
from ..pdf_report import format_duration
from ..settings import AppSettings
from ..storage import GameStorage, StorageError
from . import keymap, theme
from .celebration import CelebrationOverlay
from .keymap import MenuKey, map_game_key, map_menu_key
from .widgets import DisplayBox, HistoryBox, Panel, ScoreGrid, format_number, format_points

log = logging.getLogger(__name__)

TICK_MS = 100
MINUS_TINT = QColor("#fbe7e7")
HALFTIME_TINT = QColor("#fff2a8")   # Halbzeit-Feld bleibt gelb, sobald die Halbzeit erreicht ist
REPLAY_SPEEDS = (2.0, 1.2, 0.8, 0.5, 0.3, 0.15)   # Sekunden pro Stoß


class GameScreen(QWidget):
    completed = Signal()                 # alle Stöße gewertet und mit [Enter] bestätigt
    abort_confirmed = Signal()           # Abbruch mit [*] + [−] bestätigt
    abort_prompt = Signal(bool, float)   # Abbruch-Frage anzeigen/aktualisieren, Restzeit
    message = Signal(str, bool)          # Kurzmeldung (Text, Warnung?)
    warning = Signal(str, object)        # dauerhafte Warnung (Schlüssel, Text oder None)
    footer_changed = Signal()            # Bedienhinweise haben sich geändert (Wiedergabe)
    replay_exit = Signal()               # Wiedergabe beendet -> zurück ins Archiv
    replay_stats = Signal(object)        # Auswertung der wiedergegebenen Partie (GameState)

    def __init__(self, settings: AppSettings, storage: GameStorage,
                 parent: QWidget | None = None, clock=time.monotonic) -> None:
        super().__init__(parent)
        self._settings = settings
        self._storage = storage
        self._clock = clock
        self._controller = self._new_controller(settings)
        self._game: Game | None = None
        self._completion_sent = False
        self._elapsed_base = 0.0
        self._session_start: float | None = None
        self._spacers: list[tuple[QSpacerItem, float, float]] = []
        self._build()
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._on_tick)
        self._autosave = QTimer(self)
        self._autosave.setInterval(int(settings.autosave_seconds * 1000))
        self._autosave.timeout.connect(lambda: self._persist(reason="autosave"))
        self._replay_source: GameState | None = None
        self._replay_paused = False
        self._replay_speed = 2
        self._replay_timer = QTimer(self)
        self._replay_timer.timeout.connect(self._replay_step)
        self._sound = SoundPlayer()
        self._last_image = None
        self._celebration = CelebrationOverlay(self)
        self._was_complete = False

    def _new_controller(self, settings: AppSettings) -> ScoreInputController:
        # Korrektur-Frage gilt so lange wie die Abbruch-Frage
        return ScoreInputController(settings.input_lock_seconds, settings.undo_lock_seconds,
                                    settings.abort_confirm_seconds, self._clock,
                                    undo_confirm_seconds=settings.abort_confirm_seconds,
                                    enter_skips_lock=settings.enter_skips_lock)

    # ================================================================ Aufbau
    def _spacer(self, w: float, h: float) -> QSpacerItem:
        item = QSpacerItem(int(w), int(h), QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._spacers.append((item, w, h))
        return item

    def _build(self) -> None:
        self.strokes_box = DisplayBox()
        self.score_box = DisplayBox()
        self.prognosis_box = DisplayBox()
        self.halftime_box = DisplayBox()
        self.current_box = DisplayBox()
        self.history_box = HistoryBox(self._settings.history_length)
        self.minus_box = DisplayBox()
        self.status_box = DisplayBox()
        self.duration_box = DisplayBox("flat")
        self.score_box.text_ratio = 0.88
        self.strokes_box.text_ratio = 0.88
        self.current_box.text_ratio = 0.8
        self.grid = ScoreGrid()

        self.panels = {
            "strokes": Panel("Stoß - Anzahl", self.strokes_box, 40, 0.71),
            "score": Panel("Punktestand", self.score_box, 40, 0.70),
            "prognosis": Panel("Prognose", self.prognosis_box, 34),
            "halftime": Panel("Halbzeit", self.halftime_box, 34),
            "current": Panel("Aktueller Stoß", self.current_box, 30),
            "history": Panel("Letzte Stöße", self.history_box, 30),
            "minus": Panel("Minus", self.minus_box, 32),
            "status": Panel("Eingabe", self.status_box, 32),
            "duration": Panel("Spieldauer", self.duration_box, 32),
        }

        self._root = QHBoxLayout(self)
        left = QVBoxLayout()
        left.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(0)
        top.addWidget(self.panels["strokes"], 280)
        top.addItem(self._spacer(26, 0))
        top.addWidget(self.panels["score"], 310)
        left.addLayout(top, 240)
        left.addItem(self._spacer(0, 12))
        grid_row = QHBoxLayout()
        grid_row.setSpacing(0)
        grid_row.addItem(self._spacer(6, 0))
        grid_row.addWidget(self.grid, 1)
        grid_row.addItem(self._spacer(6, 0))
        left.addLayout(grid_row, 412)

        self._right = QGridLayout()
        self._right.addWidget(self.panels["prognosis"], 0, 0)
        self._right.addWidget(self.panels["halftime"], 0, 1)
        self._arrange_optional()
        duration_row = QHBoxLayout()
        duration_row.setSpacing(0)
        duration_row.addStretch(61)
        duration_row.addWidget(self.panels["duration"], 200)
        duration_row.addStretch(61)
        self._right.addLayout(duration_row, 3, 0, 1, 2)
        for row, stretch in enumerate((180, 184, 152, 76)):   # Prognose/Halbzeit größer, Aktueller Stoß kleiner
            self._right.setRowStretch(row, stretch)
        self._right.setColumnStretch(0, 1)
        self._right.setColumnStretch(1, 1)

        self._root.addLayout(left, 660)        # Raster breiter, rechte Spalte etwas schmaler
        self._root.addItem(self._spacer(30, 0))
        self._root.addLayout(self._right, 296)
        self.apply_unit(1.0)

    def _arrange_optional(self) -> None:
        """„Letzte Stöße“ und „Eingabe“ sind abschaltbar; der Nachbar nimmt dann die ganze Zeile ein."""
        for row, (left, right, show) in enumerate(
                (("current", "history", self._settings.show_history),
                 ("minus", "status", self._settings.show_input_status)), start=1):
            for name in (left, right):
                self._right.removeWidget(self.panels[name])
            self._right.addWidget(self.panels[left], row, 0, 1, 1 if show else 2)
            if show:
                self._right.addWidget(self.panels[right], row, 1)
            self.panels[right].setVisible(show)

    def apply_unit(self, unit: float) -> None:
        """Abstände und Plattenhöhen an die Bildschirmgröße anpassen."""
        self._root.setContentsMargins(round(16 * unit), round(25 * unit), round(14 * unit), round(8 * unit))
        self._root.setSpacing(0)
        self._right.setHorizontalSpacing(round(16 * unit))
        self._right.setVerticalSpacing(round(24 * unit))
        for item, w, h in self._spacers:
            item.changeSize(round(w * unit), round(h * unit), QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for panel in self.panels.values():
            panel.set_unit(unit)
        self._root.invalidate()

    # =============================================================== Ablauf
    @property
    def game(self) -> Game | None:
        return self._game

    @property
    def controller(self) -> ScoreInputController:
        return self._controller

    @property
    def is_replay(self) -> bool:
        return self._replay_source is not None

    @property
    def has_live_game(self) -> bool:
        """True, wenn eine echte (speicherbare) Partie läuft – nie bei einer Wiedergabe."""
        return self._game is not None and self._game.is_running and not self.is_replay

    def title(self) -> str:
        if self._game is None:
            return "Partie"
        if self.is_replay:
            started = datetime.fromisoformat(self._game.state.started_at)
            return f"Wiedergabe: {self._game.state.mode.title} vom {started:%d.%m.%Y, %H:%M} Uhr"
        return f"Partie: {self._game.state.mode.title}"

    def footer_segments(self) -> list[str]:
        if self.is_replay:
            if self._replay_done():
                return ["Wiedergabe beendet", f"Auswertung mit  [{keymap.label('enter')}]",
                        f"Zurück mit  [{keymap.label_all('back')}]"]
            return [f"Pause / Weiter mit  [{keymap.label('enter')}]",
                    f"Tempo mit  [{keymap.label('plus')}]  /  [{keymap.label('minus')}]",
                    f"Beenden mit  [{keymap.label_all('back')}]"]
        if self._game is not None and self._game.is_complete and self._game.is_running:
            return ["Partie beendet", f"Auswertung mit  [{keymap.label('enter')}]",
                    f"Korrektur mit  [{keymap.label('undo')}]  &  [{keymap.label('enter')}]"]
        return ["Plus:  [0] bis [7]",
                f"Minus:  [{keymap.label('minus')}]  und dann  [0] bis [7]",
                f"Korrektur mit  [{keymap.label('undo')}]  &  [{keymap.label('enter')}]",
                f"Partie-Abbruch mit  [{keymap.label('abort')}]  &  [{keymap.label('minus')}]"]

    def start_game(self, game: Game) -> None:
        """Neue oder fortgesetzte Partie anzeigen und Eingabe freigeben."""
        self._end_replay()
        self._hide_extras()
        self._game = game
        self._controller = self._new_controller(self._settings)
        self._completion_sent = False
        self._was_complete = game.is_complete
        self._elapsed_base = float(game.state.elapsed_seconds)
        self._session_start = self._clock()
        mode = game.state.mode
        self.grid.configure(mode.strokes, mode.grid_columns, mode.halftime_after, mode.highlight_last)
        self.refresh()
        self._tick.start()
        self._autosave.start()

    def stop(self) -> None:
        """Timer anhalten und Spieldauer in den Zustand übernehmen."""
        self._tick.stop()
        self._autosave.stop()
        self._replay_timer.stop()
        self._hide_extras()
        if self._game is not None and not self.is_replay:
            self._game.state.elapsed_seconds = self.current_elapsed()
            self._elapsed_base = self._game.state.elapsed_seconds
        self._session_start = None
        self._controller.cancel_abort()

    def clear(self) -> None:
        self.stop()
        self._end_replay()
        self._game = None

    # ============================================================ Wiedergabe
    def start_replay(self, state: GameState, seconds_per_stroke: float) -> None:
        """Gespeicherte Partie Stoß für Stoß abspielen (nur Anzeige, keine Speicherung)."""
        self.stop()
        self._replay_source = state
        copy = GameState(game_id=state.game_id, mode=state.mode, started_at=state.started_at,
                         strokes=[], status=GameStatus.RUNNING, elapsed_seconds=state.elapsed_seconds)
        self._game = Game(copy)
        self._controller.reset()
        self._completion_sent = False
        self._elapsed_base = float(state.elapsed_seconds)   # Spieldauer: Original-Dauer der Partie
        self._session_start = None
        self._replay_paused = False
        self._replay_speed = min(range(len(REPLAY_SPEEDS)),
                                 key=lambda i: abs(REPLAY_SPEEDS[i] - seconds_per_stroke))
        mode = state.mode
        self.grid.configure(mode.strokes, mode.grid_columns, mode.halftime_after, mode.highlight_last)
        self._replay_timer.start(int(REPLAY_SPEEDS[self._replay_speed] * 1000))
        self.refresh()

    def _end_replay(self) -> None:
        self._replay_timer.stop()
        self._replay_source = None

    def _replay_done(self) -> bool:
        return (self.is_replay and self._game is not None
                and self._game.played >= len(self._replay_source.strokes))  # type: ignore[union-attr]

    def _replay_step(self) -> None:
        if not self.is_replay or self._game is None:
            return
        if not self._replay_done():
            self._game.record(self._replay_source.strokes[self._game.played])  # type: ignore[union-attr]
        if self._replay_done():
            self._replay_timer.stop()
            self.footer_changed.emit()
        self.refresh()

    def _handle_replay_key(self, event: QKeyEvent) -> bool:
        if event.isAutoRepeat():
            return True
        menu_key = map_menu_key(event)
        if menu_key is MenuKey.BACK:
            self._replay_timer.stop()
            self.replay_exit.emit()
        elif menu_key is MenuKey.ENTER:
            if self._replay_done():
                self.replay_stats.emit(self._replay_source)
            else:
                self._replay_paused = not self._replay_paused
                if self._replay_paused:
                    self._replay_timer.stop()
                else:
                    self._replay_timer.start()
        elif keymap.matches(event, "plus") or keymap.matches(event, "minus"):
            faster = keymap.matches(event, "plus")
            self._replay_speed = max(0, min(len(REPLAY_SPEEDS) - 1, self._replay_speed + (1 if faster else -1)))
            self._replay_timer.setInterval(int(REPLAY_SPEEDS[self._replay_speed] * 1000))
            self.message.emit(f"Tempo: {REPLAY_SPEEDS[self._replay_speed]:.2f} s pro Stoß".replace(".", ","),
                              False)
        else:
            return False
        self.footer_changed.emit()
        self._update_live()
        return True

    def current_elapsed(self) -> float:
        if self._session_start is None:
            return self._elapsed_base
        return self._elapsed_base + max(0.0, self._clock() - self._session_start)

    def persist_now(self) -> bool:
        return self._persist(reason="extern")

    # ============================================================== Eingabe
    def handle_key(self, event: QKeyEvent) -> bool:
        """Verarbeitet eine Taste. Jede Taste wird genau einmal ausgewertet."""
        if self.is_replay:
            return self._handle_replay_key(event)
        if self._game is None or not self._game.is_running or self._completion_sent:
            return True
        if event.isAutoRepeat():   # gedrückt gehaltene Taste nie mehrfach werten
            return True
        mapped = map_game_key(event, self._settings.numpad_only)
        if mapped is None and map_menu_key(event) is MenuKey.ENTER:
            mapped = (GameKey.ENTER, None)
        if mapped is None:
            if self._controller.abort_pending():   # jede andere Taste verwirft den Abbruch
                self._controller.cancel_abort()
                self._apply(InputResult(Action.ABORT_CANCELLED))
            if self._controller.undo_pending():    # … und die Korrektur-Frage
                self._controller.cancel_undo()
                self._apply(InputResult(Action.UNDO_CANCELLED))
            return False
        key, digit = mapped
        if key is GameKey.ABORT and self._game.is_complete and not self._controller.undo_pending():
            self.message.emit(f"Alle Stöße gewertet – Auswertung mit [{keymap.label('enter')}].", False)
            return True
        self._apply(self._controller.press(key, digit))
        return True

    def _finish(self) -> None:
        """Partie-Ende mit [Enter] bestätigt -> Hauptfenster schließt ab und zeigt die Auswertung."""
        self._completion_sent = True
        self._tick.stop()
        self._autosave.stop()
        self._update_live()
        self.completed.emit()

    def _apply(self, result: InputResult) -> None:
        game = self._game
        if game is None:
            return
        action = result.action
        if action is Action.SCORE:
            try:
                entry = game.record(result.value)  # type: ignore[arg-type]
            except GameError as exc:
                log.warning("Wertung abgelehnt: %s", exc)
                self.message.emit(str(exc), True)
                self.refresh()
                return
            log.info("Stoß %s: %s (Gesamt %s)", entry.number, entry.value, entry.running_total)
            self._persist(reason="wertung")
            self._celebrate(entry.value)
            if game.played == game.state.mode.halftime_after:
                self._halftime_alert()
            if game.is_complete:
                self.message.emit(f"Letzter Stoß gewertet – Auswertung mit [{keymap.label('enter')}], "
                                  f"Korrektur mit [{keymap.label('undo')}].", False)
        elif action is Action.UNDO_REQUESTED:
            if game.played == 0:
                self._controller.cancel_undo()
                self.message.emit("Keine Wertung zum Zurücknehmen vorhanden.", True)
            else:
                value = format_points(game.state.strokes[-1])
                self.message.emit(f"Stoß {game.played} ({value}) korrigieren?  Ja mit [{keymap.label('enter')}], "
                                  "jede andere Taste = Nein.", True)
        elif action is Action.UNDO_CANCELLED:
            self.message.emit("Keine Korrektur – die Wertung bleibt stehen.", False)
        elif action in (Action.LOCK_SKIPPED, Action.CONFIRM):
            if game.is_complete:
                log.info("Partie-Ende mit Enter bestätigt")
                self._finish()
                return
        elif action is Action.UNDO:
            try:
                removed = game.undo()
            except GameError as exc:
                self.message.emit(str(exc), True)
                removed = None
            if removed is None:
                self.message.emit("Keine Wertung zum Zurücknehmen vorhanden.", True)
            else:
                log.info("Stoß %s (%s) zurückgenommen", removed.number, removed.value)
                self._celebration.dismiss()
                self._persist(reason="ruecknahme")
                self.message.emit(f"Stoß {removed.number} ({format_points(removed.value)}) zurückgenommen.", False)
        elif action is Action.ABORT_REQUESTED:
            self.abort_prompt.emit(True, self._controller.abort_remaining())
        elif action is Action.ABORT_CONFIRMED:
            self.abort_prompt.emit(False, 0.0)
            log.info("Partie-Abbruch bestätigt")
            self.abort_confirmed.emit()
            return
        elif action is Action.ABORT_CANCELLED:
            self.abort_prompt.emit(False, 0.0)
            self.message.emit("Kein Abbruch – die Partie läuft weiter.", False)
        elif action is Action.IGNORED_LOCKED:
            remaining = f"{self._controller.lock_remaining():.1f}".replace(".", ",")
            self.message.emit(f"Eingabe gesperrt – noch {remaining} s", True)
        elif action is Action.IGNORED_INVALID:
            self.message.emit("Nur die Zahlen 0 bis 7 sind erlaubt.", True)
        self.refresh()

    # ================================================== Ton und Bilder (Zugabe)
    def _hide_extras(self) -> None:
        self._celebration.dismiss()

    def _celebrate(self, value: int) -> None:
        """Ton bei +6/+7, Bild/GIF bei +6/+7 bzw. −6/−7 (automatisch aus bilder/plus und bilder/minus).
        Fehler stören nie."""
        self._celebration.dismiss()
        cfg = self._settings
        if value in cfg.celebration_values:
            try:
                self.play_sound(cfg.celebration_sound)
            except Exception:
                log.exception("Ton bei %s fehlgeschlagen", value)
        if not cfg.celebration_enabled:
            return
        try:
            if value in cfg.celebration_minus_values:
                # Ordner bilder/minus; ist er leer, die Bilder aus bilder/plus
                files = (active_images(cfg.images_minus_dir, cfg.disabled_images, "minus")
                         or active_images(cfg.images_plus_dir, cfg.disabled_images, "plus"))
            elif value in cfg.celebration_values:
                files = active_images(cfg.images_plus_dir, cfg.disabled_images, "plus")
            else:
                return
            image = pick_image(files, self._last_image)
            if image is not None and self._celebration.show_image(image, cfg.celebration_seconds):
                self._last_image = image
        except Exception:
            log.exception("Bildeinblendung fehlgeschlagen")

    def _halftime_alert(self) -> None:
        """Halbzeit: Ton (falls möglich); das Halbzeit-Feld wird in ``refresh`` dauerhaft gelb."""
        cfg = self._settings
        try:
            self.play_sound(cfg.halftime_sound)
        except Exception:
            log.exception("Halbzeit-Hinweis fehlgeschlagen")

    def play_sound(self, name: str) -> bool:
        """Ton aus dem Ordner sounds mit eingestellter Lautstärke (leerer Name = kein Ton)."""
        cfg = self._settings
        if not cfg.sound_enabled or not name:
            return False
        path = resolve_file(cfg.sounds_dir, name)
        if path is None:
            log.warning("Tondatei nicht gefunden: %s", name)
            return False
        return self._sound.play(path, cfg.sound_volume)

    def set_settings(self, settings: AppSettings) -> None:
        """Geänderte Einstellungen übernehmen (Zeiten erst ab der nächsten Partie, falls eine läuft)."""
        self._settings = settings
        self._autosave.setInterval(int(settings.autosave_seconds * 1000))
        self.history_box.set_lines(settings.history_length)
        self._arrange_optional()
        if not self.has_live_game:
            self._controller = self._new_controller(settings)
        self.refresh()
        self.footer_changed.emit()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().resizeEvent(event)
        self._celebration.reposition()

    def _persist(self, reason: str) -> bool:
        """Spielstand sofort und sicher speichern."""
        if self._game is None or self.is_replay:   # eine Wiedergabe wird nie gespeichert
            return False
        self._game.state.elapsed_seconds = self.current_elapsed()
        try:
            self._storage.save_active(self._game.state)
        except StorageError as exc:
            log.error("Speichern (%s) fehlgeschlagen: %s", reason, exc)
            self.warning.emit("save", "ACHTUNG: Spielstand konnte nicht gespeichert werden!")
            return False
        self.warning.emit("save", None)
        return True

    # =========================================================== Anzeige
    def _on_tick(self) -> None:
        timeout = self._controller.check_timeouts()
        if timeout is not None:
            self._apply(timeout)
        if self._controller.abort_pending():
            self.abort_prompt.emit(True, self._controller.abort_remaining())
        self._update_live()

    def _update_live(self) -> None:
        """Zeitabhängige Anzeigen: Sperre, Spieldauer."""
        self.duration_box.set_value(format_duration(self.current_elapsed()))
        game = self._game
        ctrl = self._controller
        if game is None:
            return
        if self.is_replay:
            total = max(1, len(self._replay_source.strokes))  # type: ignore[union-attr]
            speed = f"{REPLAY_SPEEDS[self._replay_speed]:.2f} s".replace(".", ",")
            if self._replay_done():
                self.status_box.set_value("ENDE", theme.TEXT, bold=True)
            elif self._replay_paused:
                self.status_box.set_value("PAUSE", theme.WARNING, bold=True)
            else:
                self.status_box.set_value("WIEDERGABE", theme.CURRENT, bold=True)
            self.status_box.set_progress(game.played / total, theme.CURRENT, speed)
            return
        if ctrl.undo_pending():
            self.status_box.set_value("KORREKTUR?", theme.WARNING, bold=True,
                                      subtext=f"Ja = [{keymap.label('enter')}]")
            self.status_box.set_progress(None)
        elif ctrl.is_locked():
            remaining = f"{ctrl.lock_remaining():.1f} s".replace(".", ",")
            self.status_box.set_value("GESPERRT", theme.MINUS, bold=True)
            self.status_box.set_progress(ctrl.lock_fraction(), theme.MINUS, remaining)
        elif game.is_complete:
            self.status_box.set_value("ENDE", theme.TEXT, bold=True,
                                      subtext=f"Auswertung = [{keymap.label('enter')}]")
            self.status_box.set_progress(None)
        elif ctrl.abort_pending():
            self.status_box.set_value("ABBRUCH?", theme.WARNING, bold=True)
            self.status_box.set_progress(None)
        elif ctrl.minus_selected:
            self.status_box.set_value("MINUS", theme.MINUS, bold=True)
            self.status_box.set_progress(None)
        else:
            self.status_box.set_value("BEREIT", theme.PLUS, bold=True)
            self.status_box.set_progress(None)

    def refresh(self) -> None:
        """Alle Anzeigen aus dem Spielzustand neu setzen."""
        game = self._game
        if game is None:
            return
        state = game.state
        # Stoß-Anzahl: Zahl der GESPIELTEN Stöße – am Anfang 0, nach dem 1. Stoß 1 …
        # (ohne „/ 100“ – auf Wunsch des Vereins)
        self.strokes_box.set_value(str(game.played))
        total = game.total
        self.score_box.set_value(format_number(total), theme.MINUS if total < 0 else theme.TEXT)
        prog = game.prognosis
        self.prognosis_box.set_value("" if prog is None else format_number(prog))
        half = game.halftime_score
        self.halftime_box.set_value("" if half is None else format_number(half))
        self.halftime_box.set_fill(HALFTIME_TINT if half is not None else None)   # bleibt gelb
        minus = game.minus_total
        self.minus_box.set_value(format_number(minus), theme.MINUS if minus < 0 else theme.TEXT_MUTED)
        # Aktueller Stoß: gewählter Minus-Modus oder zuletzt gewertete Wertung
        if self._controller.minus_selected:
            self.current_box.set_value("\u2212", theme.MINUS, subtext="Minus: Zahl 0 – 7", bold=True)
            self.current_box.set_fill(MINUS_TINT)
        elif game.last_value is not None:
            value = game.last_value
            color = theme.MINUS if value < 0 else (theme.TEXT_MUTED if value == 0 else theme.TEXT)
            self.current_box.set_value(format_number(value), color)
            self.current_box.set_fill(None)
        else:
            self.current_box.set_value("", subtext="")
            self.current_box.set_fill(None)
        self.history_box.set_entries([(e.number, e.value) for e in game.history(self._settings.history_length)])
        show_current = game.is_running and not game.is_complete and not self._replay_done()
        self.grid.set_running_total(self._settings.grid_running_total)
        self.grid.set_values(state.strokes, show_current=show_current)
        pending = self._controller.undo_pending() and game.played > 0 and not self.is_replay
        self.grid.set_pending(game.played - 1 if pending else None)
        complete = game.is_complete and game.is_running
        if complete != self._was_complete:
            self._was_complete = complete
            self.footer_changed.emit()
        self._update_live()
