"""
Hauptmenü (Designvorlage 1).

Links: Überschrift "Bitte Spielmodus wählen" und die Spielarten als
Knöpfe, darunter abgesetzt "Archiv" und "Ende". Rechts: Logo.
Bedienung: [8] / [2] (bzw. Pfeiltasten) wählen, [Enter] bestätigt.

Die Anordnung folgt dem 1024 × 768-Referenzentwurf und wird proportional
zur verfügbaren Fläche skaliert und zentriert (``_layout``).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from ..models import GameMode
from ..settings import AppSettings
from .keymap import MenuKey, map_menu_key
from .widgets import LogoWidget, MenuButton, Plate

# Referenzmaße (Inhaltsbereich 1024 × 702 zwischen Titel- und Fußleiste)
CONTENT_W, CONTENT_H = 1024, 702

ARCHIVE = "archive"   # Menüeinträge, die keine Spielart sind
QUIT = "quit"


class MenuScreen(QWidget):
    mode_chosen = Signal(object)      # GameMode
    archive_requested = Signal()
    quit_requested = Signal()
    notice = Signal(str, bool)        # Text, Warnung?

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._modes: list[GameMode | str] = list(settings.menu_modes) + [ARCHIVE, QUIT]
        self._plate = Plate("Bitte Spielmodus wählen", self)
        self._buttons: list[MenuButton] = []
        for index, mode in enumerate(self._modes):
            if mode == ARCHIVE:
                button = MenuButton("Archiv", True, parent=self)
            elif mode == QUIT:
                button = MenuButton("Ende", True, parent=self)
            else:
                button = MenuButton(mode.title, mode.available,
                                    "" if mode.available else "in Vorbereitung", parent=self)
            button.clicked.connect(lambda i=index: self._click(i))
            self._buttons.append(button)
        self._logo = LogoWidget(settings.logo_path, self)
        self.reset_selection()

    def _first_playable(self) -> int:
        return next((i for i, m in enumerate(self._modes) if isinstance(m, GameMode) and m.available), 0)

    # ------------------------------------------------------------ Anzeige
    def title(self) -> str:
        return "BK-Scoreboard"

    def footer_segments(self) -> list[str]:
        return ["Wählen mit Richtungstasten  [2]  &  [8]", "Bestätigen mit  [Enter]"]

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._layout()
        super().resizeEvent(event)

    def _layout(self) -> None:
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 64, 62, 463, 47)
        # Spielarten untereinander, danach abgesetzt "Archiv" und "Ende" – alles passt
        # immer zwischen Überschrift (y = 155) und Unterkante (y = 690)
        count = len(self._buttons)
        gap = 30
        step = min(94.0, (690 - 155 - 64 - gap) / max(1, count - 1))
        height = min(64.0, step * 0.7)
        shadow = height * 0.075
        modes = count - 2
        for i, button in enumerate(self._buttons):
            y = 155 + i * step + (gap if i >= modes else 0)
            place(button, 146, y, 298 + shadow, height + shadow)
        place(self._logo, 599, 50, 387, 595)

    # ------------------------------------------------------------- Auswahl
    def reset_selection(self) -> None:
        self._index = self._first_playable()
        self._update_selection()

    def select_archive(self) -> None:
        self._index = self._modes.index(ARCHIVE)
        self._update_selection()

    def _update_selection(self) -> None:
        for i, button in enumerate(self._buttons):
            button.set_selected(i == self._index)

    def _move(self, delta: int) -> None:
        self._index = (self._index + delta) % len(self._buttons)
        self._update_selection()

    def _click(self, index: int) -> None:
        self._index = index
        self._update_selection()
        self._activate()

    def _activate(self) -> None:
        mode = self._modes[self._index]
        if mode == QUIT:
            self.quit_requested.emit()
        elif mode == ARCHIVE:
            self.archive_requested.emit()
        elif not mode.available:
            self.notice.emit(mode.note or f"„{mode.title}“ ist noch nicht verfügbar.", True)
        else:
            self.mode_chosen.emit(mode)

    def handle_key(self, event: QKeyEvent) -> bool:
        key = map_menu_key(event)
        if key is MenuKey.UP:
            self._move(-1)
        elif key is MenuKey.DOWN:
            self._move(1)
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            self._activate()
        else:
            return False
        return True
