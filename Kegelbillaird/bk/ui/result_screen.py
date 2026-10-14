"""
Auswertung: Ergebnis einer Partie als eigener Bildschirm im Hauptfenster
(kein Extra-Fenster). Alles ist auf einen Blick sichtbar – ohne Scrollen:

    Überschrift (Ergebnis, Spielart, Datum) und Hinweiszeile
    Kennzahlen: Endresultat · Halbzeit · Minuspunkte · Schnitt · Stöße · Spieldauer
    links: Stoßliste im Raster der Zählansicht   rechts: Anzahl je Wertung (Balken)
    Knöpfe: [ Als PDF speichern ]  [ Drucken ]  [ Weiter ]

Das PDF (automatisch in ``results``, „Als PDF speichern“, Drucken) bleibt
unverändert – siehe ``report_output``.

Bedienung: [4]/[6] Knopf wählen, [Enter] ausführen, [*]/[Esc] weiter
(bzw. die eingestellten Tasten). Maus: Knöpfe anklicken.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..game import Game
from ..models import GameState, GameStatus
from ..pdf_report import format_duration
from ..settings import AppSettings
from . import keymap, report_output, theme
from .keymap import MenuKey, map_menu_key
from .widgets import DisplayBox, MenuButton, Panel, Plate, ScoreGrid, _Painted, format_number

log = logging.getLogger(__name__)

CONTENT_W, CONTENT_H = 1024, 702
MAX_POINTS = 7


def format_average(game: Game) -> str:
    return f"{game.total / game.played:.2f}".replace(".", ",") if game.played else "-"


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
        p.setPen(theme.WARNING if self._error else theme.TEXT)
        p.setFont(theme.fitted_font(self._text, self.width() * 0.98, self.height() * 0.7, bold=self._error))
        p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class DistributionBox(_Painted):
    """„Anzahl je Wertung“: waagrechte Balken von +7 (oben) bis −7 (unten)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: list[tuple[int, int]] = []

    def set_counts(self, counts: list[tuple[int, int]]) -> None:
        self._counts = sorted(counts, key=lambda c: -c[0])
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        inner = theme.draw_bezel(p, QRectF(self.rect()))
        if not self._counts:
            p.end()
            return
        area = inner.adjusted(inner.width() * 0.05, inner.height() * 0.03,
                              -inner.width() * 0.05, -inner.height() * 0.03)
        row_h = area.height() / len(self._counts)
        label_w = area.width() * 0.17
        count_w = area.width() * 0.15
        bar_area_w = area.width() - label_w - count_w
        highest = max((n for _, n in self._counts), default=0) or 1
        font = theme.fitted_font("−7", label_w * 0.9, row_h * 0.72)
        bold = theme.fitted_font("−7", label_w * 0.9, row_h * 0.72, bold=True)
        for index, (value, count) in enumerate(self._counts):
            y = area.top() + index * row_h
            color = theme.MINUS if value < 0 else (theme.PLUS if value > 0 else theme.TEXT_MUTED)
            label = "0" if value == 0 else f"{'+' if value > 0 else chr(0x2212)}{abs(value)}"
            p.setFont(bold)
            p.setPen(color)
            p.drawText(QRectF(area.left(), y, label_w, row_h), Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignLeft, label)
            bar_h = row_h * 0.62
            width = bar_area_w * count / highest
            if count:
                bar_color = QColor(color)
                bar_color.setAlpha(170)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(bar_color)
                p.drawRoundedRect(QRectF(area.left() + label_w, y + (row_h - bar_h) / 2, max(2.0, width), bar_h),
                                  2, 2)
            else:
                p.setPen(theme.GRID_LINE)
                p.drawLine(int(area.left() + label_w), int(y + row_h / 2),
                           int(area.left() + label_w + 4), int(y + row_h / 2))
            p.setFont(font)
            p.setPen(theme.TEXT if count else theme.TEXT_MUTED)
            p.drawText(QRectF(area.right() - count_w, y, count_w, row_h), Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignRight, str(count))
        p.end()


class ResultScreen(QWidget):
    closed = Signal()              # „Weiter“ / Zurück
    message = Signal(str, bool)    # Kurzmeldung für die Fußleiste
    footer_changed = Signal()

    SAVE, PRINT, CONTINUE = range(3)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._state: GameState | None = None
        self._title = "Auswertung"
        self._continue_label = "Weiter"

        self._plate = Plate("", self)
        self._note = NoteLine(self)
        self.boxes = {key: DisplayBox() for key in ("total", "halftime", "minus", "average", "strokes", "duration")}
        labels = {"total": "Endresultat", "halftime": "Halbzeit", "minus": "Minuspunkte",
                  "average": "Schnitt je Stoß", "strokes": "Stöße", "duration": "Spieldauer"}
        self.panels = {key: Panel(labels[key], box, 30, parent=self) for key, box in self.boxes.items()}
        self.boxes["total"].text_ratio = 0.78
        self.grid = ScoreGrid(self)
        self._grid_plate = Plate("Stoßliste", self)
        self.distribution = DistributionBox(self)
        self._dist_plate = Plate("Anzahl je Wertung", self)
        self._buttons = [MenuButton("Als PDF speichern", parent=self), MenuButton("Drucken", parent=self),
                         MenuButton("Weiter", parent=self)]
        for index, button in enumerate(self._buttons):
            button.clicked.connect(lambda i=index: self._activate(i))
        self._selected = self.CONTINUE
        self._update_selection()

    # ------------------------------------------------------------ Anzeige
    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def title(self) -> str:
        return self._title

    def footer_segments(self) -> list[str]:
        return [f"Wählen mit  [{keymap.label('left')}]  /  [{keymap.label('right')}]",
                f"Ausführen mit  [{keymap.label('enter')}]",
                f"{self._continue_label} mit  [{keymap.label_all('back')}]"]

    @property
    def state(self) -> GameState | None:
        return self._state

    def note_text(self) -> str:
        return self._note.text()

    def show_state(self, state: GameState, heading: str, note: str = "", continue_label: str = "Weiter") -> None:
        """Ergebnis einer Partie anzeigen."""
        self._state = state
        game = Game(state)
        mode = state.mode
        started = datetime.fromisoformat(state.started_at)
        status = {GameStatus.FINISHED: "", GameStatus.ABORTED: " (abgebrochen)"}.get(
            state.status, " (unterbrochen)")
        self._title = f"Auswertung: {mode.title}{status}"
        self._plate.set_text(heading)
        self._note.set_text(f"{started:%d.%m.%Y, %H:%M} Uhr" + (f"   ·   {note}" if note else ""))
        self._continue_label = continue_label
        self._buttons[self.CONTINUE].set_text(continue_label)

        total = game.total
        self.boxes["total"].set_value(format_number(total), theme.MINUS if total < 0 else theme.TEXT, bold=True)
        half = game.halftime_score
        self.boxes["halftime"].set_value("-" if half is None else format_number(half))
        self.panels["halftime"].set_label(f"Halbzeit (nach {mode.halftime_after})" if mode.halftime_after
                                          else "Halbzeit")
        minus = game.minus_total
        self.boxes["minus"].set_value(format_number(minus), theme.MINUS if minus < 0 else theme.TEXT_MUTED)
        self.boxes["average"].set_value(format_average(game))
        self.boxes["strokes"].set_value(str(game.played), suffix=f" / {game.max_strokes}")
        self.boxes["duration"].set_value(format_duration(state.elapsed_seconds))
        self.grid.configure(mode.strokes, mode.grid_columns, mode.halftime_after, mode.highlight_last)
        self.grid.set_values(state.strokes, show_current=False)
        self.distribution.set_counts([c for c in game.value_counts() if abs(c[0]) <= MAX_POINTS])
        self._selected = self.CONTINUE
        self._update_selection()
        self.footer_changed.emit()

    # ----------------------------------------------------------- Bedienung
    def _update_selection(self) -> None:
        for index, button in enumerate(self._buttons):
            button.set_selected(index == self._selected)

    def handle_key(self, event: QKeyEvent) -> bool:
        key = map_menu_key(event)
        if key is MenuKey.LEFT:
            self._selected = (self._selected - 1) % len(self._buttons)
            self._update_selection()
        elif key is MenuKey.RIGHT:
            self._selected = (self._selected + 1) % len(self._buttons)
            self._update_selection()
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            self._activate(self._selected)
        elif key is MenuKey.BACK and not event.isAutoRepeat():
            self.closed.emit()
        else:
            return False
        return True

    def _activate(self, index: int) -> None:
        self._selected = index
        self._update_selection()
        if index == self.SAVE:
            self.save_pdf()
        elif index == self.PRINT:
            self.print_report()
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
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 162, 12, 700, 46)
        place(self._note, 40, 62, 944, 22)
        width, gap = 150, (944 - 6 * 150) / 5
        for index, key in enumerate(("total", "halftime", "minus", "average", "strokes", "duration")):
            place(self.panels[key], 40 + index * (width + gap), 92, width, 118)
            self.panels[key].set_unit(unit)
        place(self._grid_plate, 40, 222, 220, 30)
        place(self.grid, 40, 258, 600, 340)
        place(self._dist_plate, 664, 222, 230, 30)
        place(self.distribution, 664, 258, 320, 340)
        button_w, button_h = 250, 58
        start = (CONTENT_W - 3 * button_w - 2 * 30) / 2
        for index, button in enumerate(self._buttons):
            place(button, start + index * (button_w + 30), 622, button_w + 4, button_h + 4)
        super().resizeEvent(event)
