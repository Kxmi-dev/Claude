"""
Hauptmenü (Designvorlage 1).

Links: Überschrift "Bitte Spielmodus wählen" und die Spielarten als
Knöpfe, darunter abgesetzt "Archiv" und "Ende". Rechts: Logo.
Bedienung: [8] / [2] (bzw. Pfeiltasten) wählen, [Enter] bestätigt.

Die Anordnung folgt dem 1024 × 768-Referenzentwurf und wird proportional
zur verfügbaren Fläche skaliert und zentriert (``_layout``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from ..models import GameMode
from ..settings import AppSettings
from . import keymap
from .keymap import MenuKey, map_menu_key
from .widgets import LogoWidget, MenuButton, Plate

# Referenzmaße (Inhaltsbereich 1024 × 702 zwischen Titel- und Fußleiste)
CONTENT_W, CONTENT_H = 1024, 702

ARCHIVE = "archive"   # Menüeinträge, die keine Spielart sind
SETTINGS = "settings"
QUIT = "quit"
SHUTDOWN = "shutdown"
EXTRA_ENTRIES = (ARCHIVE, SETTINGS, QUIT, SHUTDOWN)
SHUTDOWN_ARM_SECONDS = 5          # so lange gilt der erste [Enter]-Druck bei „Beenden & Herunterfahren“
SHUTDOWN_TEXT = "Beenden & Herunterfahren"


class MenuScreen(QWidget):
    mode_chosen = Signal(object)      # GameMode
    archive_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    shutdown_requested = Signal()
    notice = Signal(str, bool)        # Text, Warnung?

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._modes: list[GameMode | str] = list(settings.menu_modes) + list(EXTRA_ENTRIES)
        self._plate = Plate("Bitte Spielmodus wählen", self)
        self._buttons: list[MenuButton] = []
        for index, mode in enumerate(self._modes):
            if mode == ARCHIVE:
                button = MenuButton("Archiv", True, parent=self)
            elif mode == SETTINGS:
                button = MenuButton("Einstellungen", True, parent=self)
            elif mode == QUIT:
                button = MenuButton("Beenden", True, parent=self)
            elif mode == SHUTDOWN:
                button = MenuButton(SHUTDOWN_TEXT, True, parent=self)
            else:
                button = MenuButton(mode.title, mode.available,
                                    "" if mode.available else "in Vorbereitung", parent=self)
            button.clicked.connect(lambda i=index: self._click(i))
            self._buttons.append(button)
        self._logo = LogoWidget(settings.logo_path, self)
        self._club_logo = LogoWidget(None, self, placeholder=False)
        self._shutdown_armed = False
        self._disarm_timer = QTimer(self)
        self._disarm_timer.setSingleShot(True)
        self._disarm_timer.timeout.connect(self.disarm_shutdown)
        self.set_club_logo(settings.club_logo_path)
        self.reset_selection()

    def _first_playable(self) -> int:
        return next((i for i, m in enumerate(self._modes) if isinstance(m, GameMode) and m.available), 0)

    # ------------------------------------------------------------ Anzeige
    def title(self) -> str:
        return "BK-Scoreboard"

    def footer_segments(self) -> list[str]:
        return [f"Wählen mit Richtungstasten  [{keymap.label('down')}]  &  [{keymap.label('up')}]",
                f"Bestätigen mit  [{keymap.label('enter')}]"]

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._layout()
        super().resizeEvent(event)

    def _layout(self) -> None:
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 40, 30, 520, 56)
        # Spielarten untereinander, danach abgesetzt "Archiv", "Einstellungen" und "Beenden" – alles
        # passt immer zwischen Überschrift (y = 112) und Unterkante (y = 694)
        count = len(self._buttons)
        gap = 18
        top, bottom = 112, 694
        height = min(84.0, (bottom - top - gap) / max(1, count) * 0.86)
        step = (bottom - top - gap - height) / max(1, count - 1)
        shadow = height * 0.075
        modes = count - len(EXTRA_ENTRIES)
        for i, button in enumerate(self._buttons):
            y = top + i * step + (gap if i >= modes else 0)
            place(button, 70, y, 460 + shadow, height + shadow)
        if self._club_logo.has_image:
            # BK-Bild kleiner, darunter groß das Vereinslogo
            place(self._logo, 599, 30, 387, 300)
            place(self._club_logo, 599, 345, 387, 340)
        else:
            place(self._logo, 599, 50, 387, 595)

    def set_club_logo(self, path: Path | None) -> bool:
        """Vereinslogo setzen (None = keins). False, wenn die Datei fehlt oder nicht lesbar ist."""
        ok = self._club_logo.set_path(path)
        self._club_logo.setVisible(ok)
        self._layout()
        return ok or path is None

    # ------------------------------------------------------------- Auswahl
    def reset_selection(self) -> None:
        self._index = self._first_playable()
        self._update_selection()

    def select_archive(self) -> None:
        self._index = self._modes.index(ARCHIVE)
        self._update_selection()

    def select_settings(self) -> None:
        self._index = self._modes.index(SETTINGS)
        self._update_selection()

    def disarm_shutdown(self) -> None:
        self._disarm_timer.stop()
        if self._shutdown_armed:
            self._shutdown_armed = False
            self._buttons[self._modes.index(SHUTDOWN)].set_text(SHUTDOWN_TEXT)

    def _update_selection(self) -> None:
        if self._shutdown_armed and self._modes[self._index] != SHUTDOWN:
            self.disarm_shutdown()
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
        elif mode == SHUTDOWN:
            if self._shutdown_armed:              # zweiter Druck innerhalb der Frist
                self.disarm_shutdown()
                self.shutdown_requested.emit()
            else:                                 # erster Druck: nur scharf schalten
                self._shutdown_armed = True
                self._buttons[self._index].set_text(f"Zum Herunterfahren nochmal [{keymap.label('enter')}]")
                self._disarm_timer.start(int(SHUTDOWN_ARM_SECONDS * 1000))
        elif mode == ARCHIVE:
            self.archive_requested.emit()
        elif mode == SETTINGS:
            self.settings_requested.emit()
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
