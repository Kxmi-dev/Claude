"""
Automatisches Aufräumen, damit die Festplatte nicht vollläuft.

Gelöscht werden Dateien, deren letzte Änderung länger zurückliegt als die in
``config.py`` eingestellte Anzahl Tage (0 = nie löschen):

    ARCHIVE_RETENTION_DAYS   data\\archive\\*.json   und  data\\corrupt\\*
    LOG_RETENTION_DAYS       logs\\application.log.*  (ältere Tagesdateien)
    RESULTS_RETENTION_DAYS   results\\*.pdf, *.json   (Standard 0 = nie)

Die laufende Partie (data\\active_game.json …) und die aktuelle Log-Datei werden
nie angefasst. Es wird nur in genau diesen Ordnern gesucht (keine Unterordner).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400


def delete_older_than(folder: Path, days: int, patterns: tuple[str, ...], now: float | None = None) -> list[Path]:
    """Löscht Dateien in ``folder`` (nicht rekursiv), die älter als ``days`` Tage sind."""
    if days <= 0 or not folder.is_dir():
        return []
    limit = (time.time() if now is None else now) - days * SECONDS_PER_DAY
    removed: list[Path] = []
    for pattern in patterns:
        for path in folder.glob(pattern):
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_mtime < limit:
                    path.unlink()
                    removed.append(path)
            except OSError as exc:   # z. B. gerade geöffnet – beim nächsten Durchlauf erneut
                log.warning("Alte Datei konnte nicht gelöscht werden: %s (%s)", path, exc)
    return removed


@dataclass
class CleanupResult:
    archive: int = 0
    logs: int = 0
    results: int = 0

    @property
    def total(self) -> int:
        return self.archive + self.logs + self.results


def run_cleanup(data_dir: Path, logs_dir: Path, results_dir: Path, archive_days: int, log_days: int,
                results_days: int, now: float | None = None) -> CleanupResult:
    """Einmal alle Ordner aufräumen. Fehler werden protokolliert, nie weitergereicht."""
    result = CleanupResult()
    try:
        result.archive = (len(delete_older_than(Path(data_dir) / "archive", archive_days, ("*.json",), now))
                          + len(delete_older_than(Path(data_dir) / "corrupt", archive_days, ("*",), now)))
        result.logs = len(delete_older_than(Path(logs_dir), log_days, ("application.log.*",), now))
        result.results = len(delete_older_than(Path(results_dir), results_days, ("*.pdf", "*.json"), now))
    except Exception:
        log.exception("Aufräumen fehlgeschlagen")
    if result.total:
        log.info("Aufgeräumt: %s Archivdateien, %s Log-Dateien, %s Ergebnisdateien gelöscht",
                 result.archive, result.logs, result.results)
    return result
