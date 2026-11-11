"""
Autostart mit Windows (Einstellungen → Anzeige → „Beim Windows-Start öffnen“).

Eintrag in der Registry des angemeldeten Benutzers:
``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` → ``BK-Scoreboard``.
Keine Administratorrechte nötig, kein Konsolenfenster; derselbe Eintrag erscheint
im Task-Manager unter „Autostart“ (dort lässt er sich ebenfalls ausschalten).

Der Zustand wird immer aus der Registry gelesen (nicht aus einstellungen.json).
Wurde der Programmordner verschoben, korrigiert ``refresh()`` den Pfad beim Start.

Qt-frei; die Registry ist für Tests austauschbar (``Registry``).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "BK-Scoreboard"


class AutostartError(Exception):
    """Autostart konnte nicht geändert werden (Text ist für die Anzeige gedacht)."""


class Registry:
    """Lesen/Schreiben des Run-Schlüssels (nur Windows)."""

    def get(self) -> str | None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _type = winreg.QueryValueEx(key, VALUE_NAME)
                return str(value)
        except FileNotFoundError:
            return None

    def set(self, command: str) -> None:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

    def delete(self) -> None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def supported() -> bool:
    return sys.platform == "win32"


def start_command() -> str:
    """Befehl, mit dem Windows das Programm startet (.exe oder pythonw + main.py)."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    python = Path(sys.executable).resolve()
    pythonw = python.with_name("pythonw.exe")       # ohne Konsolenfenster
    if pythonw.is_file():
        python = pythonw
    main = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{python}" "{main}"'


class Autostart:
    def __init__(self, registry: Registry | None = None, command: str | None = None,
                 available: bool | None = None) -> None:
        self._registry = registry or Registry()
        self._command = command or start_command()
        self.available = supported() if available is None else available

    def is_enabled(self) -> bool:
        if not self.available:
            return False
        try:
            return self._registry.get() is not None
        except Exception:
            log.exception("Autostart-Eintrag nicht lesbar")
            return False

    def set_enabled(self, enabled: bool) -> None:
        """Ein-/ausschalten. Wirft AutostartError mit Klartext."""
        if not self.available:
            raise AutostartError("Autostart ist nur unter Windows möglich.")
        try:
            if enabled:
                self._registry.set(self._command)
            else:
                self._registry.delete()
        except Exception as exc:
            log.exception("Autostart konnte nicht geändert werden")
            raise AutostartError(f"Autostart konnte nicht geändert werden: {exc}") from exc
        log.info("Autostart %s (%s)", "eingeschaltet" if enabled else "ausgeschaltet", self._command)

    def refresh(self) -> bool:
        """Beim Programmstart: zeigt ein vorhandener Eintrag auf einen alten Ort, wird er korrigiert.
        True, wenn korrigiert wurde. Wirft nie."""
        if not self.available:
            return False
        try:
            current = self._registry.get()
            if current is None or current == self._command:
                return False
            self._registry.set(self._command)
            log.info("Autostart-Pfad korrigiert: %s -> %s", current, self._command)
            return True
        except Exception:
            log.exception("Autostart-Pfad konnte nicht geprüft werden")
            return False
