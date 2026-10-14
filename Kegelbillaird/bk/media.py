"""
Ton und Bilder.

Beides ist reine Zugabe: Fehlt eine Datei, ist sie defekt oder hat der PC
keine Tonausgabe, wird nur ein Eintrag ins Protokoll geschrieben – die
Partie läuft immer ungestört weiter.

Töne: alle .wav/.mp3 im Ordner ``sounds`` werden automatisch erkannt.
Bilder: alle Bilder/GIFs in ``bilder/plus`` und ``bilder/minus`` werden
automatisch erkannt (einzelne können im Einstellungsmenü ausgeschaltet werden).
"""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from typing import Callable, Sequence

log = logging.getLogger(__name__)

IMAGE_SUFFIXES = (".gif", ".png", ".jpg", ".jpeg", ".bmp", ".webp")
SOUND_SUFFIXES = (".wav", ".mp3")
LOGO_SUFFIXES = IMAGE_SUFFIXES + (".svg", ".ico", ".tif", ".tiff")


def list_files(folder: Path, suffixes: Sequence[str]) -> list[str]:
    """Dateinamen im Ordner mit passender Endung, alphabetisch (fehlender Ordner = leer)."""
    try:
        return sorted((p.name for p in Path(folder).iterdir()
                       if p.is_file() and p.suffix.lower() in suffixes), key=str.lower)
    except OSError:
        return []


def list_sounds(folder: Path) -> list[str]:
    return list_files(folder, SOUND_SUFFIXES)


def list_images(folder: Path) -> list[str]:
    return list_files(folder, IMAGE_SUFFIXES)


def list_logos(folder: Path) -> list[str]:
    return list_files(folder, LOGO_SUFFIXES)


def resolve_file(folder: Path, name: str) -> Path | None:
    """Datei im Ordner suchen (auch ein absoluter Pfad ist erlaubt). None, wenn sie fehlt."""
    name = str(name).strip()
    if not name:
        return None
    path = Path(name)
    if not path.is_absolute():
        path = folder / name
    return path if path.is_file() else None


def active_images(folder: Path, disabled: Sequence[str], prefix: str) -> list[Path]:
    """Alle Bilder im Ordner außer den ausgeschalteten (Einträge wie „plus/bild.gif“)."""
    off = set(disabled)
    return [Path(folder) / name for name in list_images(folder) if f"{prefix}/{name}" not in off]


def pick_image(files: Sequence[Path], last: Path | None = None,
               rng: random.Random | None = None) -> Path | None:
    """Genau eine Datei -> immer diese. Mehrere -> zufällig, nie zweimal direkt dieselbe."""
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    pool = [f for f in files if f != last] or list(files)
    return (rng or random).choice(pool)


Backend = Callable[[Path, int], None]


class SoundPlayer:
    """Spielt eine .wav/.mp3-Datei mit Lautstärke (0–100) ab, ohne je einen Fehler nach außen zu geben."""

    def __init__(self, backend: Backend | None = None) -> None:
        self._backend = backend
        self._loaded = backend is not None

    def play(self, path: Path | None, volume: int = 100) -> bool:
        if path is None or volume <= 0:
            return False
        if not self._loaded:
            self._backend = _default_backend()
            self._loaded = True
        if self._backend is None:
            log.warning("Keine Tonausgabe verfügbar – %s wird nicht abgespielt", path.name)
            return False
        try:
            self._backend(path, max(0, min(100, int(volume))))
            return True
        except Exception as exc:  # kein Audiogerät, defekte Datei, ... -> nie die Partie stören
            log.warning("Ton konnte nicht abgespielt werden (%s): %s", path.name, exc)
            return False


def _default_backend() -> Backend | None:
    """Windows: MCI (wav + mp3 + Lautstärke, hängt ohne Audiogerät nicht), Rückfall winsound (nur wav).
    Andere Systeme (Entwicklung): Qt QSoundEffect (nur wav), nur wenn ein Audiogerät vorhanden ist."""
    if sys.platform == "win32":
        return _windows_backend
    return _qt_backend()


_MCI_ALIAS = "bk_scoreboard_sound"


def _mci(command: str) -> None:
    import ctypes
    winmm = ctypes.windll.winmm
    error = winmm.mciSendStringW(command, None, 0, None)
    if error:
        buffer = ctypes.create_unicode_buffer(256)
        winmm.mciGetErrorStringW(error, buffer, 256)
        raise RuntimeError(f"MCI-Fehler {error}: {buffer.value}")


def _windows_backend(path: Path, volume: int) -> None:
    try:
        try:
            _mci(f"close {_MCI_ALIAS}")       # vorigen Ton beenden
        except RuntimeError:
            pass
        _mci(f'open "{path}" type mpegvideo alias {_MCI_ALIAS}')
        _mci(f"setaudio {_MCI_ALIAS} volume to {volume * 10}")   # 0 … 1000
        _mci(f"play {_MCI_ALIAS}")                                # kehrt sofort zurück
    except Exception as exc:
        if path.suffix.lower() != ".wav":
            raise
        log.warning("MCI-Ton nicht möglich (%s) – Rückfall auf winsound ohne Lautstärke", exc)
        _winsound_backend(path, volume)


def _winsound_backend(path: Path, volume: int) -> None:
    import winsound
    if path.suffix.lower() != ".wav":
        raise RuntimeError("winsound kann nur .wav-Dateien abspielen")
    # SND_ASYNC: kehrt sofort zurück. SND_NODEFAULT: kein Systemton, wenn die Datei fehlt.
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


def _qt_backend() -> Backend | None:
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QMediaDevices, QSoundEffect
    except Exception as exc:   # Modul fehlt oder lässt sich nicht laden
        log.warning("Qt Multimedia nicht verfügbar: %s", exc)
        return None
    holder: list = []

    def play_qt(path: Path, volume: int) -> None:
        if not QMediaDevices.audioOutputs():
            raise RuntimeError("kein Audiogerät gefunden")
        if path.suffix.lower() != ".wav":
            raise RuntimeError("auf diesem System nur .wav (mp3 nur unter Windows)")
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(volume / 100)
        holder[:] = [effect]   # Objekt am Leben halten, bis es spielt
        effect.play()

    return play_qt
