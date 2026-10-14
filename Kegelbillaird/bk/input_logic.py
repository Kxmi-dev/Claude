"""
Eingabelogik (Zustandsautomat) für die Bedienung per Nummernblock.

Diese Klasse ist bewusst unabhängig von Qt: Sie bekommt abstrakte Tasten
(``GameKey``) und eine Uhr (``clock``) und liefert eindeutige Ergebnisse
(``InputResult``). Dadurch ist sie vollständig automatisiert testbar,
inklusive Sperrzeit – ohne echtes Warten.

Bedienung
---------
Ziffer 0–7           ergibt +0 … +7   (Plus ist immer voreingestellt)
``-`` → Ziffer 0–7   ergibt -0 … -7   (-0 wird als 0 gewertet);
                     danach steht der Modus automatisch wieder auf Plus
``+``                hebt einen gewählten Minus-Modus wieder auf
``/``                letzte Wertung zurücknehmen
``*`` → ``-``        Partie abbrechen (jede andere Taste = nicht abbrechen)

Es gibt keine Bestätigungstaste: Die Ziffer schließt die Eingabe ab.

Zustände
--------
BEREIT (PLUS)   Ziffer wird als Plus gewertet
MINUS           ``-`` gewählt, die nächste Ziffer wird als Minus gewertet
GESPERRT        nach einer Wertung für ``lock_seconds``
ABBRUCH-FRAGE   nach ``*``; ``-`` bestätigt, alles andere verwirft

Regeln gegen Doppeleingaben
---------------------------
* Nach jeder Wertung sind Ziffern ``lock_seconds`` lang gesperrt. Ein
  prellender oder doppelter Tastendruck wird dadurch nie ein zweites Mal gezählt.
* ``-`` und ``+`` legen nur den Modus für den nächsten Stoß fest und sind
  auch während der Sperre erlaubt: Ein früh gedrücktes Minus darf nicht
  verloren gehen, sonst würde die folgende Ziffer fälschlich als Plus gezählt.
* ``/`` bleibt während der Sperre erlaubt, hat aber eine eigene kurze Sperre
  (``undo_lock_seconds``), damit ein prellender Tastendruck nicht zwei
  Wertungen auf einmal zurücknimmt. Nach ``/`` wird die Wertungssperre
  aufgehoben, damit die korrigierte Wertung sofort eingegeben werden kann.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .models import MAX_STROKE_POINTS


class GameKey(Enum):
    PLUS = "plus"
    MINUS = "minus"
    DIGIT = "digit"
    UNDO = "undo"
    ABORT = "abort"


class Action(Enum):
    MINUS_SELECTED = "minus_selected"      # nächste Ziffer wird als Minus gewertet
    PLUS_SELECTED = "plus_selected"        # Minus aufgehoben, nächste Ziffer ist Plus
    SCORE = "score"                        # vollständige Wertung -> verarbeiten
    UNDO = "undo"                          # letzte Wertung zurücknehmen
    ABORT_REQUESTED = "abort_requested"    # Abbruch-Frage anzeigen
    ABORT_CONFIRMED = "abort_confirmed"    # Partie abbrechen
    ABORT_CANCELLED = "abort_cancelled"    # Abbruch verworfen
    IGNORED_LOCKED = "ignored_locked"      # Eingabesperre aktiv
    IGNORED_INVALID = "ignored_invalid"    # Ziffer außerhalb 0–7
    IGNORED_UNDO_LOCKED = "ignored_undo_locked"


@dataclass(frozen=True)
class InputResult:
    action: Action
    value: int | None = None   # nur bei SCORE


class ScoreInputController:
    """Zustandsautomat für die Wertungseingabe."""

    def __init__(
        self,
        lock_seconds: float,
        undo_lock_seconds: float,
        abort_confirm_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if lock_seconds < 0 or undo_lock_seconds < 0 or abort_confirm_seconds <= 0:
            raise ValueError("Ungültige Zeitwerte für die Eingabelogik.")
        self._lock_seconds = float(lock_seconds)
        self._undo_lock_seconds = float(undo_lock_seconds)
        self._abort_seconds = float(abort_confirm_seconds)
        self._clock = clock
        self.reset()

    # --------------------------------------------------------------- Status
    def reset(self) -> None:
        """Grundzustand (neue oder fortgesetzte Partie)."""
        self._minus = False
        self._lock_until = 0.0
        self._undo_lock_until = 0.0
        self._abort_until: float | None = None

    @property
    def lock_seconds(self) -> float:
        return self._lock_seconds

    @property
    def minus_selected(self) -> bool:
        """True, wenn die nächste Ziffer als Minus gewertet wird."""
        return self._minus

    def is_locked(self) -> bool:
        return self._clock() < self._lock_until

    def lock_remaining(self) -> float:
        return max(0.0, self._lock_until - self._clock())

    def lock_fraction(self) -> float:
        """Verbleibender Anteil der Sperrzeit (1.0 → 0.0)."""
        if self._lock_seconds <= 0:
            return 0.0
        return min(1.0, self.lock_remaining() / self._lock_seconds)

    def abort_pending(self) -> bool:
        return self._abort_until is not None and self._clock() < self._abort_until

    def abort_remaining(self) -> float:
        if self._abort_until is None:
            return 0.0
        return max(0.0, self._abort_until - self._clock())

    def check_timeouts(self) -> InputResult | None:
        """Regelmäßig aufrufen: verwirft eine abgelaufene Abbruch-Frage."""
        if self._abort_until is not None and self._clock() >= self._abort_until:
            self._abort_until = None
            return InputResult(Action.ABORT_CANCELLED)
        return None

    def cancel_abort(self) -> None:
        self._abort_until = None

    # ------------------------------------------------------------ Eingabe
    def press(self, key: GameKey, digit: int | None = None) -> InputResult:
        now = self._clock()

        # 1) Offene Abbruch-Frage: nur "-" bestätigt, alles andere verwirft.
        if self._abort_until is not None:
            if now < self._abort_until:
                self._abort_until = None
                if key is GameKey.MINUS:
                    return InputResult(Action.ABORT_CONFIRMED)
                return InputResult(Action.ABORT_CANCELLED)
            self._abort_until = None  # abgelaufen -> Taste normal verarbeiten

        # 2) Abbruch anfordern
        if key is GameKey.ABORT:
            self._minus = False
            self._abort_until = now + self._abort_seconds
            return InputResult(Action.ABORT_REQUESTED)

        # 3) Rücknahme
        if key is GameKey.UNDO:
            if now < self._undo_lock_until:
                return InputResult(Action.IGNORED_UNDO_LOCKED)
            self._minus = False
            self._lock_until = 0.0
            self._undo_lock_until = now + self._undo_lock_seconds
            return InputResult(Action.UNDO)

        # 4) Modus wählen (auch während der Sperre erlaubt, siehe Moduldoku)
        if key is GameKey.MINUS:
            self._minus = True
            return InputResult(Action.MINUS_SELECTED)
        if key is GameKey.PLUS:
            self._minus = False
            return InputResult(Action.PLUS_SELECTED)

        # 5) Ziffer = Wertung (während der Sperrzeit wirkungslos)
        if key is GameKey.DIGIT:
            if now < self._lock_until:
                return InputResult(Action.IGNORED_LOCKED)
            if isinstance(digit, bool) or not isinstance(digit, int) or not 0 <= digit <= MAX_STROKE_POINTS:
                return InputResult(Action.IGNORED_INVALID)
            value = -digit if (self._minus and digit) else digit
            self._minus = False                      # danach automatisch wieder Plus
            self._lock_until = now + self._lock_seconds
            return InputResult(Action.SCORE, value=value)

        raise ValueError(f"Unbekannte Taste: {key!r}")
