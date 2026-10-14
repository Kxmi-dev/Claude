"""
Ton und Bilder (Qt-frei, damit testbar).

Beides ist reine Zugabe: Fehlt eine Datei, ist sie defekt oder hat der PC
keine Tonausgabe, wird nur ein Eintrag ins Protokoll geschrieben – die
Partie läuft immer ungestört weiter.
"""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from typing import Callable, Sequence

log = logging.getLogger(__name__)

IMAGE_SUFFIXES = (".gif", ".png", ".jpg", ".jpeg", ".bmp", ".webp")


def resolve_file(folder: Path, name: str) -> Path | None:
    """Datei im Ordner suchen (auch ein absoluter Pfad ist erlaubt). None, wenn sie fehlt."""
    name = str(name).strip()
    if not name:
        return None
    path = Path(name)
    if not path.is_absolute():
        path = folder / name
    return path if path.is_file() else None


def existing_files(folder: Path, names: Sequence[str]) -> list[Path]:
    """Alle Einträge der Liste, die als Datei vorhanden sind (Reihenfolge bleibt)."""
    found: list[Path] = []
    for name in names:
        path = resolve_file(folder, name)
        if path is None:
            if str(name).strip():
                log.warning("Bilddatei nicht gefunden: %s", name)
        elif path not in found:
            found.append(path)
    return found


def pick_image(files: Sequence[Path], last: Path | None = None,
               rng: random.Random | None = None) -> Path | None:
    """Genau eine Datei -> immer diese. Mehrere -> zufällig, nie zweimal direkt dieselbe."""
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    pool = [f for f in files if f != last] or list(files)
    return (rng or random).choice(pool)


class SoundPlayer:
    """Spielt eine WAV-Datei ab, ohne je einen Fehler nach außen zu geben."""

    def __init__(self, backend: Callable[[Path], None] | None = None) -> None:
        self._backend = backend or _default_backend()

    def play(self, path: Path | None) -> bool:
        if path is None or self._backend is None:
            return False
        try:
            self._backend(path)
            return True
        except Exception as exc:  # kein Audiogerät, defekte Datei, ... -> nie die Partie stören
            log.warning("Ton konnte nicht abgespielt werden (%s): %s", path.name, exc)
            return False


def _default_backend() -> Callable[[Path], None] | None:
    if sys.platform == "win32":
        import winsound

        def play_windows(path: Path) -> None:
            # SND_ASYNC: kehrt sofort zurück. SND_NODEFAULT: kein Systemton, wenn die Datei fehlt.
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)

        return play_windows
    return _qt_backend()


def _qt_backend() -> Callable[[Path], None] | None:
    """Für Entwicklung unter Linux/Mac. Ohne QtMultimedia gibt es einfach keinen Ton."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
    except ImportError:
        return None
    effects: list = []

    def play_qt(path: Path) -> None:
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effects[:] = [effect]   # Objekt am Leben halten, bis es spielt
        effect.play()

    return play_qt
