"""
Übersetzung von Qt-Tastenereignissen in abstrakte Tasten.

Nummernblock-Erkennung
----------------------
Qt kennzeichnet Tasten des Nummernblocks mit ``KeypadModifier``.

* NumLock an:  Ziffern kommen als Key_0 … Key_9
* NumLock aus: dieselben Tasten liefern Navigationscodes (Pos1, Ende,
  Pfeile …). Diese werden – nur wenn sie vom Nummernblock stammen – als
  Rückfallebene ebenfalls in Ziffern übersetzt. Ob Qt das Kennzeichen
  in diesem Fall setzt, hängt von System und Tastatur ab; primär sorgt
  daher die automatische NumLock-Aktivierung für korrekte Eingaben.

``+``, ``-``, ``/`` und ``*`` des Nummernblocks sind von NumLock unabhängig.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from ..input_logic import GameKey

K = Qt.Key

_DIGITS = {int(getattr(K, f"Key_{d}")): d for d in range(10)}

# Nummernblock bei ausgeschaltetem NumLock
_NUMPAD_NAVIGATION = {
    int(K.Key_Insert): 0,
    int(K.Key_End): 1,
    int(K.Key_Down): 2,
    int(K.Key_PageDown): 3,
    int(K.Key_Left): 4,
    int(K.Key_Clear): 5,
    int(K.Key_Right): 6,
    int(K.Key_Home): 7,
    int(K.Key_Up): 8,
    int(K.Key_PageUp): 9,
}

_SYMBOLS = {
    int(K.Key_Plus): GameKey.PLUS,
    int(K.Key_Minus): GameKey.MINUS,
    int(K.Key_Slash): GameKey.UNDO,
    int(K.Key_Asterisk): GameKey.ABORT,
}


def is_keypad(event: QKeyEvent) -> bool:
    return bool(event.modifiers() & Qt.KeyboardModifier.KeypadModifier)


def map_game_key(event: QKeyEvent, numpad_only: bool) -> tuple[GameKey, int | None] | None:
    """Liefert (Taste, Ziffer) oder None, wenn die Taste im Spiel keine Bedeutung hat."""
    key = int(event.key())
    keypad = is_keypad(event)
    if numpad_only and not keypad:
        return None
    if key in _SYMBOLS:
        return _SYMBOLS[key], None
    if key in _DIGITS:
        return GameKey.DIGIT, _DIGITS[key]
    if keypad and key in _NUMPAD_NAVIGATION:
        return GameKey.DIGIT, _NUMPAD_NAVIGATION[key]
    return None


class MenuKey(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ENTER = "enter"
    BACK = "back"


def map_menu_key(event: QKeyEvent) -> MenuKey | None:
    """Menüsteuerung: [8]/[2]/[4]/[6] (Nummernblock oder Ziffernreihe), Pfeiltasten,
    Enter, Zurück mit Esc oder [*] (damit auch reine Nummernblock-Bedienung möglich ist)."""
    key = int(event.key())
    if key in (int(K.Key_8), int(K.Key_Up)):
        return MenuKey.UP
    if key in (int(K.Key_2), int(K.Key_Down)):
        return MenuKey.DOWN
    if key in (int(K.Key_4), int(K.Key_Left)):
        return MenuKey.LEFT
    if key in (int(K.Key_6), int(K.Key_Right)):
        return MenuKey.RIGHT
    if key in (int(K.Key_Enter), int(K.Key_Return)):
        return MenuKey.ENTER
    if key in (int(K.Key_Escape), int(K.Key_Asterisk)):
        return MenuKey.BACK
    return None
