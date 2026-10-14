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
from ..keys import ACTIONS, KeyBindings

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

# Tasten, die es auf dem Nummernblock gibt (nur sie unterliegen NUMPAD_ONLY)
_NUMPAD_NAMES = set("0123456789") | {"+", "-", "/", "*", ".", ",", "Enter"}

_ACTION_TO_GAMEKEY = {"plus": GameKey.PLUS, "minus": GameKey.MINUS, "undo": GameKey.UNDO, "abort": GameKey.ABORT}


def qt_keys(name: str) -> set[int]:
    """Qt-Tastencodes zu einem (normalisierten) Tastennamen."""
    named = {"+": "Plus", "-": "Minus", "/": "Slash", "*": "Asterisk", ".": "Period", ",": "Comma",
             "Esc": "Escape", "Backspace": "Backspace", "Delete": "Delete", "Space": "Space"}
    if name == "Enter":
        return {int(K.Key_Enter), int(K.Key_Return)}
    attr = named.get(name, name)
    return {int(getattr(K, attr if hasattr(K, attr) else f"Key_{attr}"))}


class _Active:
    """Die in config.py gewählte Tastenbelegung (einmal beim Start gesetzt)."""

    def __init__(self) -> None:
        self.configure(KeyBindings())

    def configure(self, bindings: KeyBindings) -> None:
        self.bindings = bindings
        self.by_action = {a: {k for n in bindings.keys(a) for k in qt_keys(n)} for a in ACTIONS}
        self.numpad_keys = {k for a in ("plus", "minus", "undo", "abort") for n in bindings.keys(a)
                            if n in _NUMPAD_NAMES for k in qt_keys(n)}


_active = _Active()


def configure(bindings: KeyBindings) -> None:
    """Tastenbelegung aus den Einstellungen übernehmen."""
    _active.configure(bindings)


def bindings() -> KeyBindings:
    return _active.bindings


def label(action: str) -> str:
    """Hauptbelegung einer Aktion für die Legende (z. B. „Enter“)."""
    return _active.bindings.label(action)


def label_all(action: str) -> str:
    return _active.bindings.label_all(action)


def matches(event: QKeyEvent, action: str) -> bool:
    return int(event.key()) in _active.by_action[action]


def is_keypad(event: QKeyEvent) -> bool:
    return bool(event.modifiers() & Qt.KeyboardModifier.KeypadModifier)


def map_game_key(event: QKeyEvent, numpad_only: bool) -> tuple[GameKey, int | None] | None:
    """Liefert (Taste, Ziffer) oder None, wenn die Taste im Spiel keine Bedeutung hat."""
    key = int(event.key())
    keypad = is_keypad(event)
    for action, game_key in _ACTION_TO_GAMEKEY.items():
        if key in _active.by_action[action]:
            if numpad_only and not keypad and key in _active.numpad_keys:
                return None
            return game_key, None
    if numpad_only and not keypad:
        return None
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
    """Menüsteuerung mit den in config.py gewählten Tasten (Standard: [8]/[2]/[4]/[6] und
    Pfeiltasten, Enter, Zurück mit [*] oder Esc, damit auch reine Nummernblock-Bedienung möglich ist)."""
    key = int(event.key())
    for menu_key in MenuKey:
        if key in _active.by_action[menu_key.value]:
            return menu_key
    return None
