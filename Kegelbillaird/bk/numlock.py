"""
NumLock prüfen und aktivieren (Windows).

Vorgehen
--------
* Zustand lesen:  ``GetKeyState(VK_NUMLOCK) & 1``
* Aktivieren:     simulierter Druck der NumLock-Taste über ``SendInput``
                  (von Microsoft empfohlene API). Nur falls ``SendInput``
                  blockiert wird, erfolgt ein Rückfall auf ``keybd_event``.

Wichtig: ``GetKeyState`` liefert den Zustand aus Sicht des eigenen
GUI-Threads. Nach dem Senden muss die Anwendung ihre Nachrichten
verarbeiten, bevor der neue Zustand sichtbar wird. Die Prüfung nach dem
Einschalten erfolgt deshalb zeitversetzt (siehe ``NumLockGuard`` in der
GUI), und es wird nie zweimal direkt hintereinander umgeschaltet –
sonst könnte NumLock versehentlich wieder ausgeschaltet werden.

Auf anderen Betriebssystemen wird sauber ``UNSUPPORTED`` gemeldet.
"""

from __future__ import annotations

import logging
import sys
from enum import Enum

log = logging.getLogger(__name__)

VK_NUMLOCK = 0x90
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class NumLockResult(Enum):
    ALREADY_ON = "already_on"
    TOGGLED = "toggled"          # Tastendruck gesendet – Wirkung zeitversetzt prüfen
    UNSUPPORTED = "unsupported"  # kein Windows
    FAILED = "failed"


def is_supported() -> bool:
    return sys.platform == "win32"


if is_supported():  # pragma: no cover - nur unter Windows ausführbar
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    ULONG_PTR = ctypes.c_size_t

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class _INPUTUNION(ctypes.Union):
        # Die Union muss alle Varianten enthalten, damit die Strukturgröße
        # (insbesondere unter 64 Bit) der Windows-Definition entspricht.
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _user32.GetKeyState.argtypes = [ctypes.c_int]
    _user32.GetKeyState.restype = ctypes.c_short
    _user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    _user32.SendInput.restype = wintypes.UINT
    _user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
    _user32.keybd_event.restype = None


def is_numlock_on() -> bool | None:
    """True/False unter Windows, None wenn nicht ermittelbar."""
    if not is_supported():
        return None
    try:  # pragma: no cover - Windows
        return bool(_user32.GetKeyState(VK_NUMLOCK) & 1)
    except Exception:
        log.exception("NumLock-Status konnte nicht gelesen werden")
        return None


def _send_numlock_press() -> bool:  # pragma: no cover - Windows
    down = _INPUT(type=INPUT_KEYBOARD)
    down.ki = _KEYBDINPUT(wVk=VK_NUMLOCK, wScan=0x45, dwFlags=KEYEVENTF_EXTENDEDKEY, time=0, dwExtraInfo=0)
    up = _INPUT(type=INPUT_KEYBOARD)
    up.ki = _KEYBDINPUT(wVk=VK_NUMLOCK, wScan=0x45, dwFlags=KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
    inputs = (_INPUT * 2)(down, up)
    sent = _user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))
    if sent == 2:
        return True
    log.warning("SendInput für NumLock fehlgeschlagen (gesendet=%s, Fehler=%s) – nutze keybd_event",
                sent, ctypes.get_last_error())
    try:
        _user32.keybd_event(VK_NUMLOCK, 0x45, KEYEVENTF_EXTENDEDKEY, 0)
        _user32.keybd_event(VK_NUMLOCK, 0x45, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        log.exception("keybd_event für NumLock fehlgeschlagen")
        return False


def ensure_numlock_on() -> NumLockResult:
    """Schaltet NumLock ein, falls es aus ist.

    Liefert ``TOGGLED``, wenn ein Tastendruck gesendet wurde. Ob er gewirkt
    hat, muss der Aufrufer nach kurzer Zeit mit ``is_numlock_on`` prüfen.
    """
    state = is_numlock_on()
    if state is None:
        return NumLockResult.UNSUPPORTED if not is_supported() else NumLockResult.FAILED
    if state:
        return NumLockResult.ALREADY_ON
    try:  # pragma: no cover - Windows
        if _send_numlock_press():
            log.info("NumLock war aus – Einschalt-Tastendruck gesendet")
            return NumLockResult.TOGGLED
    except Exception:
        log.exception("NumLock konnte nicht eingeschaltet werden")
    return NumLockResult.FAILED
