"""
Computer herunterfahren (Hauptmenü → „Beenden & Herunterfahren“).

Windows: ``shutdown /s /t 0 /f`` – sofort, ohne Countdown, ohne Windows-Meldung und
ohne Konsolenfenster. ``/f`` schließt andere noch offene Programme zwangsweise, damit
Windows nicht bei „Programm verhindert das Herunterfahren“ hängen bleibt.

Qt-frei, damit testbar (``runner`` ist austauschbar).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Callable

log = logging.getLogger(__name__)

SHUTDOWN_COMMAND = ["shutdown", "/s", "/t", "0", "/f"]


def shutdown_supported() -> bool:
    return sys.platform == "win32"


def shutdown(runner: Callable = subprocess.run, platform: str | None = None) -> tuple[bool, str]:
    """Fährt den Computer herunter. Liefert (gestartet?, Meldung) – wirft nie."""
    if (platform or sys.platform) != "win32":
        return False, "Herunterfahren ist nur unter Windows möglich."
    try:
        result = runner(SHUTDOWN_COMMAND, capture_output=True, text=True, timeout=15,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        log.exception("Herunterfahren nicht möglich")
        return False, f"Herunterfahren nicht möglich: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        log.warning("Herunterfahren abgelehnt (Code %s): %s", result.returncode, detail)
        return False, f"Herunterfahren nicht möglich (Code {result.returncode}){': ' + detail if detail else ''}."
    log.info("Computer wird heruntergefahren")
    return True, ""
