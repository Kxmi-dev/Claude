"""
Datenmodelle des BK-Scoreboards.

Enthält ausschließlich reine Python-Datenklassen ohne GUI-Abhängigkeit:

* ``GameMode``  – Beschreibung einer Spielart (z. B. BK 100, BK 50)
* ``GameStatus`` – Zustand einer Partie (läuft / beendet / abgebrochen)
* ``GameState`` – vollständiger, speicherbarer Zustand einer Partie

Alles, was zur Wiederherstellung einer Partie nötig ist, steckt in
``GameState`` und lässt sich verlustfrei nach JSON (``to_dict``) und
zurück (``from_dict``) wandeln.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# Wertung je Stoß: -7 bis +7 (verbindliche Vorgabe der Spezifikation).
# Dieser Wert wird bewusst NICHT in config.py angeboten, weil er Teil der
# Wertungslogik ist und nicht versehentlich verändert werden soll.
MAX_STROKE_POINTS = 7


class GameStatus(str, Enum):
    """Lebenszyklus einer Partie."""

    RUNNING = "running"
    FINISHED = "finished"
    ABORTED = "aborted"


@dataclass(frozen=True)
class GameMode:
    """Eine Spielart.

    key             Kurzbezeichnung, gleichzeitig Präfix für Dateinamen (z. B. "BK100")
    title           Anzeigename im Menü (z. B. "100 Stoß")
    strokes         Anzahl der Stöße der Partie
    halftime_after  Nach diesem Stoß wird der Halbzeitstand festgehalten
    grid_columns    Spaltenanzahl des Stoß-Rasters in der Zählansicht
    highlight_last  Anzahl der letzten Stöße, die im Raster hervorgehoben werden
    available       False = wird im Menü angezeigt, ist aber (noch) nicht spielbar
    note            Hinweistext für nicht verfügbare Spielarten
    """

    key: str
    title: str
    strokes: int = 0
    halftime_after: int | None = None
    grid_columns: int = 10
    highlight_last: int = 5
    available: bool = True
    note: str = ""

    def __post_init__(self) -> None:
        if not self.key or not self.title:
            raise ValueError("Spielart benötigt 'key' und 'title'.")
        if not self.available:
            return
        if not isinstance(self.strokes, int) or self.strokes <= 0:
            raise ValueError(f"Spielart {self.key}: 'strokes' muss > 0 sein.")
        if self.halftime_after is not None and not (0 < self.halftime_after < self.strokes):
            raise ValueError(f"Spielart {self.key}: 'halftime_after' liegt außerhalb der Partie.")
        if self.grid_columns <= 0:
            raise ValueError(f"Spielart {self.key}: 'grid_columns' muss > 0 sein.")
        if not (0 <= self.highlight_last <= self.strokes):
            raise ValueError(f"Spielart {self.key}: 'highlight_last' ist ungültig.")

    @property
    def grid_rows(self) -> int:
        """Zeilenanzahl des Stoß-Rasters (aufgerundet)."""
        return max(1, -(-self.strokes // self.grid_columns))

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "strokes": self.strokes,
            "halftime_after": self.halftime_after,
            "grid_columns": self.grid_columns,
            "highlight_last": self.highlight_last,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameMode":
        if not isinstance(data, dict):
            raise ValueError("Spielart-Daten fehlen oder sind ungültig.")
        halftime = data.get("halftime_after")
        return cls(
            key=str(data["key"]),
            title=str(data["title"]),
            strokes=_strict_int(data["strokes"], "strokes"),
            halftime_after=None if halftime is None else _strict_int(halftime, "halftime_after"),
            grid_columns=_strict_int(data.get("grid_columns", 10), "grid_columns"),
            highlight_last=_strict_int(data.get("highlight_last", 5), "highlight_last"),
            available=True,
        )


def _corrections(value: Any) -> int | None:
    """Korrekturzähler (fehlt bei älteren Spielständen → None)."""
    if value is None:
        return None
    number = _strict_int(value, "corrections")
    if number < 0:
        raise ValueError("Ungültige Anzahl Korrekturen.")
    return number


def _strict_int(value: Any, name: str) -> int:
    """Akzeptiert nur echte Ganzzahlen (kein bool, kein float, kein Text)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Feld '{name}' muss eine Ganzzahl sein, erhalten: {value!r}")
    return value


def now_iso() -> str:
    """Aktuelle lokale Zeit als ISO-Zeichenkette (sekundengenau)."""
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class GameState:
    """Vollständiger, speicherbarer Zustand einer Partie."""

    game_id: str
    mode: GameMode
    started_at: str
    strokes: list[int] = field(default_factory=list)
    status: GameStatus = GameStatus.RUNNING
    finished_at: str | None = None
    elapsed_seconds: float = 0.0
    revision: int = 0
    corrections: int | None = None   # Anzahl Korrekturen mit [/]; None = alte Partie (nicht gezählt)

    # ------------------------------------------------------------------ Fabrik
    @classmethod
    def new(cls, mode: GameMode, started_at: str | None = None) -> "GameState":
        if not mode.available:
            raise ValueError(f"Spielart '{mode.title}' ist nicht verfügbar.")
        return cls(
            game_id=uuid.uuid4().hex,
            mode=mode,
            started_at=started_at or now_iso(),
            corrections=0,
        )

    # ------------------------------------------------------ Serialisierung
    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "mode": self.mode.to_dict(),
            "started_at": self.started_at,
            "strokes": list(self.strokes),
            "status": self.status.value,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(float(self.elapsed_seconds), 1),
            "revision": self.revision,
            "corrections": self.corrections,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        """Erzeugt einen Zustand aus gespeicherten Daten und prüft ihn streng.

        Wirft ``ValueError`` bei jeder Unstimmigkeit, damit ein beschädigter
        Spielstand niemals unbemerkt weiterverwendet wird. Unbekannte Felder
        (z. B. ``player_name`` aus älteren Versionen) werden ignoriert.
        """
        if not isinstance(data, dict):
            raise ValueError("Spielstand ist kein Objekt.")
        try:
            mode = GameMode.from_dict(data["mode"])
            strokes_raw = data["strokes"]
            if not isinstance(strokes_raw, list):
                raise ValueError("'strokes' ist keine Liste.")
            strokes = [_strict_int(v, "strokes[]") for v in strokes_raw]
            for v in strokes:
                if not -MAX_STROKE_POINTS <= v <= MAX_STROKE_POINTS:
                    raise ValueError(f"Ungültige Wertung im Spielstand: {v}")
            if len(strokes) > mode.strokes:
                raise ValueError("Mehr Wertungen als Stöße in der Partie.")
            status = GameStatus(data["status"])
            started_at = str(data["started_at"])
            datetime.fromisoformat(started_at)  # Formatprüfung
            finished_at = data.get("finished_at")
            if finished_at is not None:
                finished_at = str(finished_at)
                datetime.fromisoformat(finished_at)
            elapsed = data.get("elapsed_seconds", 0.0)
            if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
                raise ValueError("Ungültige Spieldauer.")
            if status is GameStatus.FINISHED and len(strokes) != mode.strokes:
                raise ValueError("Als beendet markierte Partie ist unvollständig.")
            return cls(
                game_id=str(data["game_id"]),
                mode=mode,
                started_at=started_at,
                strokes=strokes,
                status=status,
                finished_at=finished_at,
                elapsed_seconds=float(elapsed),
                revision=_strict_int(data.get("revision", 0), "revision"),
                corrections=_corrections(data.get("corrections")),
            )
        except KeyError as exc:
            raise ValueError(f"Pflichtfeld fehlt im Spielstand: {exc}") from exc
