"""
Spiel-Engine: verwaltet Wertungen, Stoßzähler und Punktestand einer Partie.

Die Engine kennt weder GUI noch Dateien. Sie arbeitet ausschließlich auf
einem ``GameState`` und stellt sicher, dass dieser jederzeit gültig ist:

* nur Wertungen von -7 bis +7
* nie mehr Wertungen als Stöße der Spielart
* Änderungen nur, solange die Partie läuft

Zustandsautomat einer Partie::

    RUNNING --(letzter Stoß + Abschluss)--> FINISHED
    RUNNING --(Abbruch)-------------------> ABORTED
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import MAX_STROKE_POINTS, GameState, GameStatus, now_iso


class GameError(Exception):
    """Ungültige Operation auf einer Partie (z. B. Wertung nach Partieende)."""


@dataclass(frozen=True)
class StrokeEntry:
    """Eine Zeile der Stoßliste."""

    number: int  # 1-basiert
    value: int
    running_total: int


def validate_points(value: object) -> int:
    """Prüft eine Wertung und gibt sie als int zurück.

    Erlaubt sind ausschließlich echte Ganzzahlen von -7 bis +7.
    ``bool`` wird ausdrücklich abgelehnt (in Python ist True == 1).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise GameError(f"Wertung muss eine Ganzzahl sein, erhalten: {value!r}")
    if not -MAX_STROKE_POINTS <= value <= MAX_STROKE_POINTS:
        raise GameError(f"Wertung {value} liegt außerhalb von -{MAX_STROKE_POINTS} bis +{MAX_STROKE_POINTS}.")
    return value


class Game:
    """Fachlogik einer einzelnen Partie."""

    def __init__(self, state: GameState) -> None:
        self._state = state

    # ------------------------------------------------------------ Zugriff
    @property
    def state(self) -> GameState:
        return self._state

    @property
    def max_strokes(self) -> int:
        return self._state.mode.strokes

    @property
    def played(self) -> int:
        """Anzahl der bereits gewerteten Stöße."""
        return len(self._state.strokes)

    @property
    def total(self) -> int:
        """Aktueller Gesamtpunktestand."""
        return sum(self._state.strokes)

    @property
    def is_running(self) -> bool:
        return self._state.status is GameStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """Alle Stöße gewertet (Partie kann abgeschlossen werden)."""
        return self.played >= self.max_strokes

    @property
    def current_stroke_number(self) -> int:
        """Nummer des Stoßes, der als nächstes gewertet wird (1 … max)."""
        return min(self.played + 1, self.max_strokes)

    @property
    def last_value(self) -> int | None:
        return self._state.strokes[-1] if self._state.strokes else None

    @property
    def minus_total(self) -> int:
        """Summe aller Minuspunkte (≤ 0)."""
        return sum(v for v in self._state.strokes if v < 0)

    @property
    def halftime_score(self) -> int | None:
        """Punktestand nach dem Halbzeit-Stoß, sobald dieser gespielt ist."""
        half = self._state.mode.halftime_after
        if half is None or self.played < half:
            return None
        return sum(self._state.strokes[:half])

    @property
    def prognosis(self) -> int | None:
        """Hochrechnung des aktuellen Schnitts auf die volle Stoßzahl."""
        if self.played == 0:
            return None
        return round(self.total / self.played * self.max_strokes)

    def value_counts(self) -> list[tuple[int, int]]:
        """Wie oft jede Wertung vorkam: [(-7, n), (-6, n), … (0, n), … (7, n)]."""
        counts = {value: 0 for value in range(-MAX_STROKE_POINTS, MAX_STROKE_POINTS + 1)}
        for value in self._state.strokes:
            counts[value] += 1
        return list(counts.items())

    def entries(self) -> list[StrokeEntry]:
        """Vollständige Stoßliste mit laufendem Gesamtstand."""
        result: list[StrokeEntry] = []
        running = 0
        for index, value in enumerate(self._state.strokes, start=1):
            running += value
            result.append(StrokeEntry(index, value, running))
        return result

    def history(self, count: int) -> list[StrokeEntry]:
        """Die letzten ``count`` Stöße (älteste zuerst)."""
        if count <= 0:
            return []
        return self.entries()[-count:]

    # ---------------------------------------------------------- Änderungen
    def record(self, value: int) -> StrokeEntry:
        """Wertet den nächsten Stoß. Gibt den neuen Listeneintrag zurück."""
        points = validate_points(value)
        if not self.is_running:
            raise GameError("Die Partie läuft nicht mehr.")
        if self.is_complete:
            raise GameError("Alle Stöße dieser Partie sind bereits gewertet.")
        self._state.strokes.append(points)
        return StrokeEntry(self.played, points, self.total)

    def undo(self) -> StrokeEntry | None:
        """Nimmt die zuletzt gewertete Wertung vollständig zurück.

        Gibt den entfernten Eintrag zurück oder ``None``, wenn es nichts
        zurückzunehmen gibt.
        """
        if not self.is_running:
            raise GameError("Die Partie läuft nicht mehr.")
        if not self._state.strokes:
            return None
        number = self.played
        total_before = self.total
        value = self._state.strokes.pop()
        if self._state.corrections is not None:
            self._state.corrections += 1
        return StrokeEntry(number, value, total_before)

    def finish(self, finished_at: str | None = None) -> None:
        """Schließt eine vollständige Partie ab."""
        if not self.is_running:
            raise GameError("Die Partie läuft nicht mehr.")
        if not self.is_complete:
            raise GameError("Die Partie kann erst nach dem letzten Stoß abgeschlossen werden.")
        self._state.status = GameStatus.FINISHED
        self._state.finished_at = finished_at or now_iso()

    def abort(self, aborted_at: str | None = None) -> None:
        """Bricht eine laufende Partie ab."""
        if not self.is_running:
            raise GameError("Die Partie läuft nicht mehr.")
        self._state.status = GameStatus.ABORTED
        self._state.finished_at = aborted_at or now_iso()
