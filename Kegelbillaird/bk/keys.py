"""
Tastenbelegung (Qt-frei, damit testbar).

In ``config.py`` stehen die Tasten als Namen („+“, „Enter“, „Esc“, „F5“ …).
Dieses Modul prüft die Namen, erkennt doppelt belegte Tasten und liefert die
Beschriftungen für die Legende in der Fußleiste und in den Hinweisen. Die
Übersetzung in echte Qt-Tasten steht in ``bk/ui/keymap.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# Aktion -> (Standardtasten, Beschreibung). Die erste Taste steht in der Legende.
ACTIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "plus":  (("+",), "Plus wählen (hebt ein gewähltes Minus wieder auf)"),
    "minus": (("-",), "Minus wählen – gilt auch als „Ja“ bei der Abbruch-Frage"),
    "undo":  (("/",), "letzte Wertung zurücknehmen"),
    "abort": (("*",), "Partie abbrechen (danach mit der Minus-Taste bestätigen)"),
    "up":    (("8", "Up"), "Menü: nach oben / im Bericht nach oben blättern"),
    "down":  (("2", "Down"), "Menü: nach unten / im Bericht nach unten blättern"),
    "left":  (("4", "Left"), "Statistik-Fenster: Knopf links"),
    "right": (("6", "Right"), "Statistik-Fenster: Knopf rechts"),
    "enter": (("Enter",), "Bestätigen / Wiedergabe Pause und Weiter"),
    "back":  (("*", "Esc"), "Zurück / Fenster schließen / Wiedergabe beenden"),
}

# Tasten, die sich im selben Zusammenhang nicht doppeln dürfen
GAME_ACTIONS = ("plus", "minus", "undo", "abort")
MENU_ACTIONS = ("up", "down", "left", "right", "enter", "back")
REPLAY_ACTIONS = MENU_ACTIONS + ("plus", "minus")   # Wiedergabe: Menütasten + Tempo

# Zeichen, die als Namen erlaubt sind (zusätzlich Buchstaben, Ziffern, F1–F12)
SYMBOLS = ("+", "-", "/", "*", ".", ",")
NAMED = ("Enter", "Esc", "Space", "Tab", "Backspace", "Delete", "Insert", "Home", "End",
         "PageUp", "PageDown", "Up", "Down", "Left", "Right")

_ALIASES = {
    "return": "Enter", "escape": "Esc", "pos1": "Home", "ende": "End", "entf": "Delete",
    "plus": "+", "minus": "-", "slash": "/", "star": "*", "asterisk": "*", "stern": "*",
    "period": ".", "punkt": ".", "comma": ",", "komma": ",", "leertaste": "Space",
    "pageup": "PageUp", "pgup": "PageUp", "pagedown": "PageDown", "pgdn": "PageDown",
    "rauf": "Up", "runter": "Down", "links": "Left", "rechts": "Right",
}
_CANONICAL = {n.lower(): n for n in NAMED}
_CANONICAL.update({f"f{i}": f"F{i}" for i in range(1, 13)})

_LABELS = {"-": "−", "Up": "Pfeil hoch", "Down": "Pfeil runter", "Left": "Pfeil links",
           "Right": "Pfeil rechts", "Space": "Leertaste", "Delete": "Entf", "End": "Ende",
           "Home": "Pos1", "PageUp": "Bild hoch", "PageDown": "Bild runter", "Backspace": "Rücktaste"}


def normalize(name: str) -> str:
    """Taste in die einheitliche Schreibweise bringen. ValueError bei unbekannten Namen."""
    text = str(name).strip()
    if not text:
        raise ValueError("leerer Tastenname")
    low = text.lower()
    if len(text) == 1:
        if text in SYMBOLS or text.isdigit():
            return text
        if text.isalpha() and text.isascii():
            return text.upper()
        raise ValueError(f"unbekannte Taste „{name}“")
    low = _ALIASES.get(low, low).lower()
    if low in SYMBOLS:
        return low
    if low in _CANONICAL:
        return _CANONICAL[low]
    raise ValueError(f"unbekannte Taste „{name}“")


def display(name: str) -> str:
    """Beschriftung für die Legende."""
    return _LABELS.get(name, name)


DEFAULT_NAMES: Mapping[str, tuple[str, ...]] = {a: keys for a, (keys, _d) in ACTIONS.items()}


@dataclass(frozen=True)
class KeyBindings:
    names: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_NAMES))

    @classmethod
    def from_config(cls, cfg) -> "KeyBindings":
        """Liest KEY_PLUS, KEY_MINUS … aus der config.py; fehlende Einträge behalten den Standard."""
        names: dict[str, tuple[str, ...]] = {}
        for action, (default, _desc) in ACTIONS.items():
            raw = getattr(cfg, f"KEY_{action.upper()}", default)
            if isinstance(raw, str):
                raw = [raw]
            try:
                names[action] = tuple(dict.fromkeys(normalize(k) for k in raw))
            except ValueError as exc:
                raise ValueError(f"KEY_{action.upper()}: {exc}") from None
        bindings = cls(names)
        bindings.validate()
        return bindings

    def keys(self, action: str) -> tuple[str, ...]:
        return tuple(self.names.get(action) or DEFAULT_NAMES[action])

    def label(self, action: str) -> str:
        """Hauptbelegung für die Legende, z. B. „Enter“."""
        return display(self.keys(action)[0])

    def label_all(self, action: str) -> str:
        """Alle Belegungen, z. B. „*“ oder „Esc“ (Legende: [*]  oder  [Esc])."""
        return "]  oder  [".join(display(k) for k in self.keys(action))

    def validate(self) -> None:
        for action in ACTIONS:
            if not self.names.get(action):
                raise ValueError(f"KEY_{action.upper()}: mindestens eine Taste muss eingetragen sein.")
        for action in GAME_ACTIONS:
            for key in self.keys(action):
                if key.isdigit():
                    raise ValueError(f"KEY_{action.upper()}: Die Ziffern 0–9 sind für die Wertung reserviert.")
        for group, title in ((GAME_ACTIONS, "in der Partie"), (MENU_ACTIONS, "in Menüs"),
                             (REPLAY_ACTIONS, "in der Wiedergabe")):
            seen: dict[str, str] = {}
            for action in group:
                for key in self.keys(action):
                    if key in seen and seen[key] != action:
                        raise ValueError(f"Die Taste „{key}“ ist {title} doppelt belegt "
                                         f"(KEY_{seen[key].upper()} und KEY_{action.upper()}).")
                    seen[key] = action
