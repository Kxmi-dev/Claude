"""
Überlagerungs-Karte für Abfragen und Meldungen.

Verwendet für:
* "Unterbrochene Partie gefunden"  (PARTIE FORTSETZEN / NEUE PARTIE)
* Abbruch-Frage während der Partie ([−] = Ja, jede andere Taste = Nein)
* Korrekturfeld (alte Punktzahl / neue Punktzahl des letzten Stoßes)
* "Partie beendet" mit Endresultat und PDF-Pfad
* Fehlermeldungen (z. B. beschädigter Spielstand)

Die Karte verdunkelt den Hintergrund und wird vollständig selbst gezeichnet
(gleiche Knöpfe wie im Hauptmenü). Bedienung: [8]/[2] wählen, [Enter].
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from . import theme
from .keymap import MenuKey, map_menu_key

WARNING_PLATE = QColor("#f2d4cf")
HIGHLIGHT_PLATE = QColor("#ffe14d")   # gelb wie das zu korrigierende Kästchen


@dataclass
class OverlayContent:
    title: str
    lines: list[str] = field(default_factory=list)
    top_lines: list[str] = field(default_factory=list)   # Zeilen über ``big``
    big: str = ""
    choices: list[str] = field(default_factory=list)
    hint: str = ""
    warning: bool = False
    highlight: bool = False    # gelbe Titelplatte (Korrektur)
    interactive: bool = True   # False = reine Anzeige, Tasten gehen an die Zählansicht
    back_choice: int | None = None   # Auswahl bei [*]/[Esc] (None = Taste ohne Wirkung)


class Overlay(QWidget):
    choice_made = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide()
        self._content = OverlayContent("")
        self._selected = 0
        self._button_rects: list[QRectF] = []

    # -------------------------------------------------------------- API
    @property
    def interactive(self) -> bool:
        return self.isVisible() and self._content.interactive

    @property
    def content(self) -> OverlayContent:
        return self._content

    def show_content(self, content: OverlayContent, selected: int = 0) -> None:
        self._content = content
        self._selected = max(0, min(selected, len(content.choices) - 1)) if content.choices else 0
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def update_lines(self, lines: list[str]) -> None:
        if lines != self._content.lines:
            self._content.lines = list(lines)
            self.update()

    def close_overlay(self) -> None:
        self.hide()

    def handle_key(self, event: QKeyEvent) -> bool:
        """Tasten bei sichtbarer, interaktiver Karte (alle werden verbraucht)."""
        key = map_menu_key(event)
        choices = len(self._content.choices)
        if key is MenuKey.UP and choices:
            self._selected = (self._selected - 1) % choices
            self.update()
        elif key is MenuKey.DOWN and choices:
            self._selected = (self._selected + 1) % choices
            self.update()
        elif key is MenuKey.ENTER and not event.isAutoRepeat() and choices:
            self.choice_made.emit(self._selected)
        elif key is MenuKey.BACK and self._content.back_choice is not None:
            self.choice_made.emit(self._content.back_choice)
        return True

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._content.interactive:
            return
        pos = event.position()
        for index, rect in enumerate(self._button_rects):
            if rect.contains(pos):
                self._selected = index
                self.update()
                self.choice_made.emit(index)
                return

    # ---------------------------------------------------------- Zeichnen
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        c = self._content
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.fillRect(self.rect(), QColor(0, 0, 0, 105))
        u = theme.ui_unit(self.width(), self.height())

        pad = 26 * u
        title_h = 50 * u
        big_h = 86 * u if c.big else 0
        line_h = 32 * u
        button_h = 62 * u
        button_gap = 16 * u
        hint_h = 26 * u if c.hint else 0
        height = (pad + title_h + 18 * u + big_h + (len(c.lines) + len(c.top_lines)) * line_h
                  + (18 * u + len(c.choices) * (button_h + button_gap) if c.choices else 0)
                  + hint_h + pad)
        width = min(self.width() * 0.92, 660 * u)
        card = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

        inner = theme.draw_bezel(p, card, QColor("#f7f7f2"))
        x0, w0 = inner.left() + pad * 0.7, inner.width() - pad * 1.4
        y = card.top() + pad
        theme.draw_plate(p, QRectF(x0, y, w0, title_h), c.title, text_ratio=0.56,
                         color=WARNING_PLATE if c.warning else HIGHLIGHT_PLATE if c.highlight else theme.PLATE)
        y += title_h + 18 * u
        for line in c.top_lines:
            p.setPen(theme.TEXT)
            p.setFont(theme.fitted_font(line, w0, line_h * 0.7))
            p.drawText(QRectF(x0, y, w0, line_h), Qt.AlignmentFlag.AlignCenter, line)
            y += line_h
        if c.big:
            p.setPen(theme.TEXT)
            p.setFont(theme.fitted_font(c.big, w0, big_h * 0.8, bold=True))
            p.drawText(QRectF(x0, y, w0, big_h), Qt.AlignmentFlag.AlignCenter, c.big)
            y += big_h
        for line in c.lines:
            p.setPen(theme.TEXT)
            p.setFont(theme.fitted_font(line, w0, line_h * 0.62))
            p.drawText(QRectF(x0, y, w0, line_h), Qt.AlignmentFlag.AlignCenter, line)
            y += line_h
        self._button_rects = []
        if c.choices:
            y += 18 * u
            bw = min(w0, 380 * u)
            for index, label in enumerate(c.choices):
                rect = QRectF(card.center().x() - bw / 2, y, bw, button_h)
                theme.draw_menu_button(p, rect, label, index == self._selected)
                self._button_rects.append(rect)
                y += button_h + button_gap
        if c.hint:
            p.setPen(theme.TEXT_MUTED)
            p.setFont(theme.fitted_font(c.hint, w0, hint_h * 0.7))
            p.drawText(QRectF(x0, y, w0, hint_h), Qt.AlignmentFlag.AlignCenter, c.hint)
        p.end()
