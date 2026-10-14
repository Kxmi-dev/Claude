"""
Auswertung („Endergebnis“) einer Partie als eigener Bildschirm im Hauptfenster
(kein Extra-Fenster). Alles ist auf einen Blick sichtbar – ohne Scrollen
(Aufbau nach der Vorlage des Vereins)::

            [ Endergebnis ]
    ┌ Halbzeit ┐ ┌ Ergebnis ┐ ┌Spielzeit┐ ┌ Vereins- ┐
    │          │ │          │ ├ Minus ──┤ │  logo    │
    └──────────┘ └──────────┘ └─────────┘ └──────────┘
    Spielanalyse:  1er 2er 3er 4er 5er 6er 7er Leer Minus  (wie oft gestoßen)
    Statistik in drei Spalten (Stöße · Punkte · Halbzeit/Höchstwert/Korrekturen)
    [ Partie speichern ] [ Partie drucken ] [ Neue Partie ] [ Hauptmenü ]
    (aus dem Archiv: [ Partie speichern ] [ Partie drucken ] [ Zurück ])

Nach Partie-Ende sind [Enter]/[*] und Mausklicks ``result_lock_seconds`` lang
gesperrt – kein versehentlicher Doppeldruck direkt ins Hauptmenü.

Das PDF (automatisch in ``results``, „Partie speichern“, Drucken) bleibt
unverändert – siehe ``report_output``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QKeyEvent, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from ..game import Game
from ..models import GameState, GameStatus
from ..pdf_report import format_duration
from ..settings import AppSettings
from . import keymap, report_output, theme
from .keymap import MenuKey, map_menu_key
from .widgets import DisplayBox, MenuButton, Panel, Plate, _Painted, format_number

log = logging.getLogger(__name__)

CONTENT_W, CONTENT_H = 1024, 702
DASH = "–"
ANALYSIS = (("1er", 1), ("2er", 2), ("3er", 3), ("4er", 4), ("5er", 5), ("6er", 6), ("7er", 7),
            ("Leer", 0), ("Minus", None))


def format_average(game: Game) -> str:
    return f"{game.total / game.played:.2f}".replace(".", ",") if game.played else DASH


def statistics(game: Game) -> list[list[tuple[str, str, bool]]]:
    """Kennzahlen in drei Spalten: (Bezeichnung, Wert, rot?)."""
    strokes = game.state.strokes
    positive = [v for v in strokes if v > 0]
    negative = [v for v in strokes if v < 0]
    half = game.halftime_score
    halftime_after = game.state.mode.halftime_after
    second_half = (game.total - half) if half is not None and game.played > (halftime_after or 0) else None
    corrections = game.state.corrections
    minus = sum(negative)
    played = str(game.played) if game.is_complete else f"{game.played} von {game.max_strokes}"
    return [
        [("Ausgeführte Stöße", played, False),
         ("Positive Stöße", str(len(positive)), False),
         ("Leerstöße", str(strokes.count(0)), False),
         ("Minusstöße", str(len(negative)), bool(negative))],
        [("Summe positive Punkte", str(sum(positive)), False),
         ("Summe Minuspunkte", format_number(minus), minus < 0),
         ("Netto-Endergebnis", format_number(game.total), game.total < 0),
         ("Durchschnitt je Stoß", format_average(game), False)],
        [("Höchstes Stoßergebnis", format_number(max(strokes)) if strokes else DASH, False),
         ("Halbzeitergebnis", DASH if half is None else format_number(half), False),
         ("Punkte 2. Halbzeit", DASH if second_half is None else format_number(second_half), False),
         ("Korrekturen", DASH if corrections is None else str(corrections), False)],
    ]


class NoteLine(_Painted):
    """Einzeilige Hinweiszeile (z. B. „PDF gespeichert: …“)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self._error = False

    def set_text(self, text: str, error: bool = False) -> None:
        self._text, self._error = text, error
        self.update()

    def text(self) -> str:
        return self._text

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self._text:
            return
        p = self._painter()
        p.setPen(theme.WARNING if self._error else theme.TEXT_MUTED)
        p.setFont(theme.fitted_font(self._text, self.width() * 0.98, self.height() * 0.72, bold=self._error))
        p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class LogoBox(_Painted):
    """Vereinslogo in einem weißen Feld (leer, wenn keins gewählt ist)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logo = QPixmap()

    def set_logo(self, path: Path | None) -> None:
        self._logo = QPixmap(str(path)) if path is not None and Path(path).is_file() else QPixmap()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        inner = theme.draw_bezel(p, QRectF(self.rect()))
        if not self._logo.isNull():
            target = inner.adjusted(inner.width() * 0.06, inner.height() * 0.06,
                                    -inner.width() * 0.06, -inner.height() * 0.06)
            pix = self._logo.scaled(target.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(target.center().x() - pix.width() / 2), int(target.center().y() - pix.height() / 2), pix)
        p.end()


class StatsTable(_Painted):
    """Kennzahlen untereinander: Bezeichnung links, Wert rechts (gut lesbar groß)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, bool]] = []
        self._font_px = 0           # gemeinsame Schriftgröße aller Spalten (vom Bildschirm gesetzt)

    def set_rows(self, rows: list[tuple[str, str, bool]]) -> None:
        self._rows = rows
        self.update()

    def rows(self) -> list[tuple[str, str, bool]]:
        return list(self._rows)

    def _pad(self) -> float:
        return self.width() * 0.035

    def fitting_px(self) -> int:
        """Größte Schrift, bei der jede Zeile (Bezeichnung + Wert) in die Breite passt."""
        if not self._rows:
            return 0
        row_h = self.height() / len(self._rows)
        px = max(6, int(row_h * 0.5 * theme.FONT_SCALE))
        avail = (self.width() - 3 * self._pad()) * 0.94      # Puffer gegen Rundung
        for label, value, _ in self._rows:
            label_m = QFontMetricsF(theme.base_font(px))
            value_m = QFontMetricsF(theme.base_font(px, bold=True))
            needed = label_m.horizontalAdvance(label) + value_m.horizontalAdvance(value)
            if needed > avail > 0:
                px = max(6, int(px * avail / needed))
        return px

    def set_font_px(self, px: int) -> None:
        self._font_px = px
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self._rows:
            return
        p = self._painter()
        w, h = float(self.width()), float(self.height())
        row_h = h / len(self._rows)
        pad = self._pad()
        px = self._font_px or self.fitting_px()
        label_font, value_font = theme.base_font(px), theme.base_font(px, bold=True)
        value_w = max(QFontMetricsF(value_font).horizontalAdvance(v) for _, v, _ in self._rows)
        label_w = w - value_w - 3 * pad
        for index, (label, value, red) in enumerate(self._rows):
            row = QRectF(0, index * row_h, w, row_h)
            if index % 2 == 0:
                p.fillRect(row.adjusted(0, 1, 0, -1), QColor(0, 0, 0, 16))
            p.setPen(theme.TEXT)
            p.setFont(label_font)
            p.drawText(QRectF(pad, row.top(), label_w, row_h), Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignLeft, label)
            p.setPen(theme.MINUS if red else theme.TEXT)
            p.setFont(value_font)
            p.drawText(QRectF(w - pad - value_w, row.top(), value_w, row_h), Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignRight, value)
        p.end()


class ResultScreen(QWidget):
    closed = Signal()                  # „Hauptmenü“ / „Zurück“
    new_game_requested = Signal(object)    # GameMode – „Neue Partie“ (dieselbe Spielart)
    message = Signal(str, bool)        # Kurzmeldung für die Fußleiste
    footer_changed = Signal()

    SAVE, PRINT, NEW_GAME, CLOSE = range(4)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._state: GameState | None = None
        self._title = "Endergebnis"
        self._close_label = "Hauptmenü"
        self._offer_new_game = False
        self._locked_until = 0.0

        self._plate = Plate("Endergebnis", self)
        self._note = NoteLine(self)
        self.boxes = {key: DisplayBox() for key in ("halftime", "total", "duration", "minus")}
        labels = {"halftime": "Halbzeit", "total": "Ergebnis", "duration": "Spielzeit", "minus": "Minus"}
        plates = {"halftime": 30, "total": 30, "duration": 24, "minus": 24}
        self.panels = {key: Panel(labels[key], box, plates[key], parent=self) for key, box in self.boxes.items()}
        self.boxes["total"].text_ratio = 0.8
        self.boxes["halftime"].text_ratio = 0.8
        self.logo = LogoBox(self)
        self._analysis_plate = Plate("Spielanalyse", self)
        self.analysis = {name: DisplayBox() for name, _ in ANALYSIS}
        self.analysis_panels = {name: Panel(name, box, 24, parent=self) for name, box in self.analysis.items()}
        for box in self.analysis.values():
            box.text_ratio = 0.6
        self.stats = [StatsTable(self) for _ in range(3)]
        self._buttons = [MenuButton(text, parent=self)
                         for text in ("Partie speichern", "Partie drucken", "Neue Partie", "Hauptmenü")]
        for index, button in enumerate(self._buttons):
            button.clicked.connect(lambda i=index: self._click(i))
        self._selected = self.CLOSE
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(200)
        self._lock_timer.timeout.connect(self._tick_lock)
        self._update_selection()

    # ------------------------------------------------------------ Anzeige
    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def title(self) -> str:
        return self._title

    def footer_segments(self) -> list[str]:
        remaining = self.lock_remaining()
        if remaining > 0:
            return [f"Eingabe gesperrt – noch {int(remaining + 0.99)} s"]
        return [f"Wählen mit  [{keymap.label('left')}]  /  [{keymap.label('right')}]",
                f"Ausführen mit  [{keymap.label('enter')}]",
                f"{self._close_label} mit  [{keymap.label_all('back')}]"]

    @property
    def state(self) -> GameState | None:
        return self._state

    def note_text(self) -> str:
        return self._note.text()

    def button_texts(self) -> list[str]:
        return [self._buttons[i].text() for i in self._visible()]

    def show_state(self, state: GameState, note: str = "", close_label: str = "Hauptmenü",
                   offer_new_game: bool = False, lock_seconds: float = 0.0) -> None:
        """Ergebnis einer Partie anzeigen. ``lock_seconds``: Sperre gegen Doppeldruck."""
        self._state = state
        game = Game(state)
        mode = state.mode
        started = datetime.fromisoformat(state.started_at)
        status = {GameStatus.FINISHED: "", GameStatus.ABORTED: " (abgebrochen)"}.get(
            state.status, " (unterbrochen)")
        self._title = f"Partie: {mode.title} – Endergebnis{status}"
        self._plate.set_text("Endergebnis" if state.status is GameStatus.FINISHED else "Zwischenstand")
        self._note.set_text(f"{mode.title}   ·   {started:%d.%m.%Y, %H:%M} Uhr" + (f"   ·   {note}" if note else ""))
        self._close_label = close_label
        self._offer_new_game = offer_new_game
        self._buttons[self.CLOSE].set_text(close_label)

        half = game.halftime_score
        self.boxes["halftime"].set_value(DASH if half is None else format_number(half))
        total = game.total
        self.boxes["total"].set_value(format_number(total), theme.MINUS if total < 0 else theme.TEXT, bold=True)
        self.boxes["duration"].set_value(format_duration(state.elapsed_seconds))
        minus = game.minus_total
        self.boxes["minus"].set_value(format_number(minus), theme.MINUS if minus < 0 else theme.TEXT_MUTED)
        self.logo.set_logo(self._settings.club_logo_path)
        for name, value in ANALYSIS:
            count = (sum(1 for v in state.strokes if v < 0) if value is None
                     else sum(1 for v in state.strokes if v == value))
            red = value is None and count > 0
            self.analysis[name].set_value(str(count), theme.MINUS if red else theme.TEXT)
        for table, rows in zip(self.stats, statistics(game)):
            table.set_rows(rows)
        self._sync_stats_font()

        self._selected = self.CLOSE
        self._locked_until = time.monotonic() + max(0.0, lock_seconds)
        self._update_selection()
        self._relayout()
        if lock_seconds > 0:
            self._lock_timer.start()
        self.footer_changed.emit()

    # ------------------------------------------------------------- Sperre
    def lock_remaining(self) -> float:
        return max(0.0, self._locked_until - time.monotonic())

    def _tick_lock(self) -> None:
        if self.lock_remaining() <= 0:
            self._lock_timer.stop()
            self._update_selection()
        self.footer_changed.emit()

    def _blocked(self) -> bool:
        remaining = self.lock_remaining()
        if remaining > 0:
            self.message.emit(f"Bitte kurz warten – Eingabe noch {int(remaining + 0.99)} s gesperrt.", True)
            return True
        return False

    # ----------------------------------------------------------- Bedienung
    def _visible(self) -> list[int]:
        return [i for i in range(len(self._buttons)) if i != self.NEW_GAME or self._offer_new_game]

    def _update_selection(self) -> None:
        locked = self.lock_remaining() > 0
        for index, button in enumerate(self._buttons):
            button.set_selected(index == self._selected and not locked)
            button.setVisible(index in self._visible())

    def handle_key(self, event: QKeyEvent) -> bool:
        key = map_menu_key(event)
        visible = self._visible()
        if key in (MenuKey.LEFT, MenuKey.RIGHT):
            position = visible.index(self._selected) if self._selected in visible else len(visible) - 1
            position = (position + (1 if key is MenuKey.RIGHT else -1)) % len(visible)
            self._selected = visible[position]
            self._update_selection()
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            if not self._blocked():
                self._activate(self._selected)
        elif key is MenuKey.BACK and not event.isAutoRepeat():
            if not self._blocked():
                self.closed.emit()
        else:
            return False
        return True

    def _click(self, index: int) -> None:
        if not self._blocked():
            self._activate(index)

    def _activate(self, index: int) -> None:
        self._selected = index
        self._update_selection()
        if index == self.SAVE:
            self.save_pdf()
        elif index == self.PRINT:
            self.print_report()
        elif index == self.NEW_GAME and self._state is not None:
            self.new_game_requested.emit(self._state.mode)
        else:
            self.closed.emit()

    def save_pdf(self, target=None):
        """Speichert ohne Nachfrage im eingestellten Speicherort. Liefert den Pfad oder None."""
        if self._state is None:
            return None
        try:
            path = report_output.save_pdf(self._state, self._settings, target)
        except report_output.OutputError as exc:
            self._note.set_text(str(exc), error=True)
            self.message.emit(str(exc), True)
            return None
        self._note.set_text(f"PDF gespeichert: {path}")
        self.message.emit(f"PDF gespeichert: {path.name}", False)
        return path

    def print_report(self, printer=None) -> bool:
        if self._state is None:
            return False
        try:
            text = report_output.print_report(self._state, self._settings, printer)
        except report_output.OutputError as exc:
            self._note.set_text(str(exc), error=True)
            self.message.emit(str(exc), True)
            return False
        self._note.set_text(text)
        self.message.emit(text, False)
        return True

    # -------------------------------------------------------------- Layout
    def resizeEvent(self, event) -> None:  # noqa: N802
        self._relayout()
        super().resizeEvent(event)

    def _sync_stats_font(self) -> None:
        """Alle drei Statistik-Spalten in derselben (möglichst großen) Schrift."""
        px = min((table.fitting_px() for table in self.stats), default=0)
        for table in self.stats:
            table.set_font_px(px)

    def _relayout(self) -> None:
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 352, 6, 320, 46)
        place(self._note, 40, 54, 944, 20)
        # obere Reihe: Halbzeit · Ergebnis · Spielzeit/Minus · Vereinslogo
        place(self.panels["halftime"], 40, 82, 270, 176)
        place(self.panels["total"], 326, 82, 300, 176)
        place(self.panels["duration"], 642, 82, 160, 84)
        place(self.panels["minus"], 642, 174, 160, 84)
        place(self.logo, 818, 82, 166, 148)
        for panel in self.panels.values():
            panel.set_unit(unit)
        # Spielanalyse
        place(self._analysis_plate, 40, 270, 180, 26)
        width = (944 - 8 * 10) / len(ANALYSIS)
        for index, (name, _) in enumerate(ANALYSIS):
            place(self.analysis_panels[name], 40 + index * (width + 10), 302, width, 96)
            self.analysis_panels[name].set_unit(unit)
        # Statistik in drei Spalten
        column = (944 - 2 * 16) / 3
        for index, table in enumerate(self.stats):
            place(table, 40 + index * (column + 16), 412, column, 192)
        self._sync_stats_font()
        # Knöpfe
        visible = self._visible()
        button_w, button_h, gap = 214, 60, 20
        start = (CONTENT_W - len(visible) * button_w - (len(visible) - 1) * gap) / 2
        for position, index in enumerate(visible):
            place(self._buttons[index], start + position * (button_w + gap), 622, button_w + 4, button_h + 4)
