"""
Archiv: Liste aller gespeicherten Partien (beendet, abgebrochen, unterbrochen).

Bedienung: [8] / [2] wählen, [Enter] öffnen (Statistik, Wiedergabe, Weiterspielen),
[*] oder [Esc] zurück zum Hauptmenü. Maus: Zeile anklicken, Doppelklick öffnet, Mausrad blättert.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..game import Game
from ..settings import AppSettings
from ..storage import ArchiveEntry, GameStorage
from . import theme
from . import keymap
from .keymap import MenuKey, map_menu_key
from .widgets import Plate, _Painted, format_number

CONTENT_W, CONTENT_H = 1024, 702

# Spalten: (Überschrift, Anteil an der Breite, Ausrichtung)
COLUMNS = (
    ("Datum", 0.19, Qt.AlignmentFlag.AlignLeft),
    ("Uhrzeit", 0.12, Qt.AlignmentFlag.AlignLeft),
    ("Spielart", 0.18, Qt.AlignmentFlag.AlignLeft),
    ("Status", 0.19, Qt.AlignmentFlag.AlignLeft),
    ("Stöße", 0.15, Qt.AlignmentFlag.AlignRight),
    ("Ergebnis", 0.17, Qt.AlignmentFlag.AlignRight),
)
STATUS_COLORS = {"beendet": QColor("#16803a"), "abgebrochen": theme.MINUS, "unterbrochen": QColor("#b86e00")}


def entry_cells(entry: ArchiveEntry) -> list[str]:
    state = entry.state
    started = datetime.fromisoformat(state.started_at)
    game = Game(state)
    return [f"{started:%d.%m.%Y}", f"{started:%H:%M}", state.mode.title, entry.status_label,
            f"{game.played} / {game.max_strokes}", format_number(game.total)]


class ArchiveList(_Painted):
    """Tabelle der Partien im Stil der Anzeigefelder."""

    activated = Signal(int)
    selection_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[list[str]] = []
        self._selected = 0
        self._top = 0
        self._row_rects: list[tuple[int, QRectF]] = []

    def set_rows(self, rows: list[list[str]], selected: int = 0) -> None:
        self._rows = rows
        self._selected = max(0, min(selected, len(rows) - 1))
        self._top = 0
        self.update()

    @property
    def selected(self) -> int:
        return self._selected

    def step(self, delta: int) -> None:
        if not self._rows:
            return
        self._selected = max(0, min(len(self._rows) - 1, self._selected + delta))
        self.selection_changed.emit(self._selected)
        self.update()

    # ---------------------------------------------------------- Geometrie
    def _metrics(self) -> tuple[QRectF, float, float, int]:
        inner = theme.bezel_geometry(QRectF(self.rect()))[2]
        area = inner.adjusted(inner.width() * 0.025, inner.height() * 0.02, -inner.width() * 0.025,
                              -inner.height() * 0.02)
        row_h = max(22.0, min(48.0, self.height() / 13.5))
        header_h = row_h * 0.9
        visible = max(1, int((area.height() - header_h) // row_h))
        return area, row_h, header_h, visible

    # ------------------------------------------------------------- Maus
    def _row_at(self, pos) -> int | None:
        for index, rect in self._row_rects:
            if rect.contains(pos):
                return index
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self._row_at(event.position())
        if index is not None:
            self._selected = index
            self.selection_changed.emit(index)
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        index = self._row_at(event.position())
        if index is not None:
            self.activated.emit(index)

    def wheelEvent(self, event) -> None:  # noqa: N802
        self.step(-1 if event.angleDelta().y() > 0 else 1)

    # ---------------------------------------------------------- Zeichnen
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        theme.draw_bezel(p, QRectF(self.rect()))
        area, row_h, header_h, visible = self._metrics()
        self._row_rects = []
        if not self._rows:
            p.setPen(theme.TEXT_MUTED)
            text = "Noch keine Partien im Archiv."
            p.setFont(theme.fitted_font(text, area.width() * 0.8, row_h * 0.7))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, text)
            p.end()
            return
        # sichtbaren Ausschnitt so verschieben, dass die Auswahl sichtbar bleibt
        if self._selected < self._top:
            self._top = self._selected
        elif self._selected >= self._top + visible:
            self._top = self._selected - visible + 1
        self._top = max(0, min(self._top, max(0, len(self._rows) - visible)))

        pad = area.width() * 0.02
        widths = [area.width() * share for _, share, _ in COLUMNS]
        font_px = theme.fitted_font("29.09.2026", widths[0] * 0.9, row_h * 0.52).pixelSize()

        # Kopfzeile
        x = area.left()
        p.setFont(theme.base_font(font_px * 0.85, bold=True))
        p.setPen(theme.TEXT_MUTED)
        for (title, _, align), width in zip(COLUMNS, widths):
            p.drawText(QRectF(x + pad, area.top(), width - 2 * pad, header_h),
                       align | Qt.AlignmentFlag.AlignVCenter, title)
            x += width
        p.setPen(theme.GRID_LINE)
        p.drawLine(int(area.left()), int(area.top() + header_h), int(area.right()), int(area.top() + header_h))

        # Zeilen
        y = area.top() + header_h + row_h * 0.1
        for index in range(self._top, min(len(self._rows), self._top + visible)):
            rect = QRectF(area.left(), y, area.width(), row_h * 0.92)
            self._row_rects.append((index, rect))
            selected = index == self._selected
            if selected:
                theme.draw_menu_button(p, rect.adjusted(0, 0, -3, -3), "", True)
            elif index % 2:
                p.fillRect(rect, QColor("#f4f4f0"))
            x = area.left()
            for column, ((_, _, align), width) in enumerate(zip(COLUMNS, widths)):
                text = self._rows[index][column]
                color = theme.TEXT if selected else QColor("#333333")
                if column == 3:
                    color = STATUS_COLORS.get(text, color)
                elif column == 5 and text.startswith("\u2212"):
                    color = theme.MINUS
                p.setPen(color)
                p.setFont(theme.base_font(font_px, bold=(column == 5)))
                p.drawText(QRectF(x + pad, rect.top(), width - 2 * pad, rect.height() - 3),
                           align | Qt.AlignmentFlag.AlignVCenter, text)
                x += width
            y += row_h

        # Hinweis auf weitere Einträge
        if len(self._rows) > visible:
            info = f"{self._top + 1}–{min(len(self._rows), self._top + visible)} von {len(self._rows)}"
            p.setPen(theme.TEXT_MUTED)
            p.setFont(theme.base_font(font_px * 0.75))
            p.drawText(QRectF(area.left(), area.bottom() - row_h * 0.6, area.width(), row_h * 0.6),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, info)
        p.end()


class ArchiveScreen(QWidget):
    entry_chosen = Signal(object)    # ArchiveEntry
    back_requested = Signal()

    def __init__(self, settings: AppSettings, storage: GameStorage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._entries: list[ArchiveEntry] = []
        self._plate = Plate("Archiv – gespeicherte Partien", self)
        self._list = ArchiveList(self)
        self._list.activated.connect(self._open)

    # ------------------------------------------------------------- Anzeige
    def title(self) -> str:
        return "Archiv"

    def footer_segments(self) -> list[str]:
        return [f"Wählen mit  [{keymap.label('down')}]  &  [{keymap.label('up')}]",
                f"Öffnen mit  [{keymap.label('enter')}]",
                f"Zurück mit  [{keymap.label_all('back')}]"]

    def reload(self) -> None:
        """Archiv neu einlesen; die bisherige Auswahl bleibt nach Möglichkeit erhalten."""
        previous = self.selected_entry()
        self._entries = self._storage.list_archive()
        selected = 0
        if previous is not None:
            for index, entry in enumerate(self._entries):
                if entry.path == previous.path:
                    selected = index
                    break
        self._list.set_rows([entry_cells(e) for e in self._entries], selected)
        count = len(self._entries)
        self._plate.set_text(f"Archiv – {count} gespeicherte Partie{'n' if count != 1 else ''}")

    def selected_entry(self) -> ArchiveEntry | None:
        if not self._entries:
            return None
        return self._entries[self._list.selected]

    def _open(self, index: int | None = None) -> None:
        entry = self.selected_entry()
        if entry is not None:
            self.entry_chosen.emit(entry)

    def handle_key(self, event: QKeyEvent) -> bool:
        key = map_menu_key(event)
        if key is MenuKey.UP:
            self._list.step(-1)
        elif key is MenuKey.DOWN:
            self._list.step(1)
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            self._open()
        elif key is MenuKey.BACK:
            self.back_requested.emit()
        else:
            return False
        return True

    def resizeEvent(self, event) -> None:  # noqa: N802
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 212, 26, 600, 47)
        place(self._list, 40, 92, 944, 594)
        super().resizeEvent(event)
