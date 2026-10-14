"""
Absturzsichere Speicherung des aktiven Spielstands.

Dateien im Datenordner (``data/``)
----------------------------------
active_game.json       aktueller Spielstand (Hauptdatei)
active_game.json.bak   vorheriger Stand (eine Wertung älter) als Rückfallebene
active_game.json.tmp   existiert nur kurz während des Schreibens
archive/               abgeschlossene, abgebrochene oder verworfene Partien
corrupt/               nicht lesbare Spielstände (werden nie gelöscht)

Schreibvorgang (atomar)
-----------------------
1. Neuen Stand in ``.tmp`` schreiben, ``flush`` + ``fsync``
2. Bisherige Hauptdatei nach ``.bak`` kopieren
3. ``.tmp`` per ``os.replace`` atomar zur Hauptdatei machen

Ein Absturz in jedem dieser Schritte hinterlässt immer mindestens eine
vollständige, gültige Datei. Jede Datei trägt eine SHA-256-Prüfsumme; beim
Laden wird unter allen gültigen Kandidaten der neueste (höchste Revision)
verwendet.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .models import GameState, GameStatus

log = logging.getLogger(__name__)

FORMAT_VERSION = 1
APP_MARKER = "BK-Scoreboard"


class StorageError(Exception):
    """Speichern oder Laden ist fehlgeschlagen."""


class LoadStatus(Enum):
    NONE = "none"                # keine aktive Partie vorhanden
    OK = "ok"                    # Hauptdatei gültig
    RECOVERED = "recovered"      # aus .tmp oder .bak wiederhergestellt
    CORRUPT = "corrupt"          # Dateien vorhanden, aber keine gültig


@dataclass
class ArchiveEntry:
    """Eine archivierte Partie (beendet, abgebrochen oder unterbrochen)."""

    path: Path
    state: GameState

    @property
    def status_label(self) -> str:
        if self.state.status is GameStatus.FINISHED:
            return "beendet"
        if self.state.status is GameStatus.ABORTED:
            return "abgebrochen"
        return "unterbrochen"

    @property
    def can_continue(self) -> bool:
        """Nur nicht beendete Partien können weitergespielt werden."""
        return self.state.status is not GameStatus.FINISHED


@dataclass
class LoadResult:
    status: LoadStatus
    state: GameState | None = None
    source: Path | None = None
    message: str = ""


def _checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def encode_state(state: GameState) -> bytes:
    payload = state.to_dict()
    envelope = {
        "app": APP_MARKER,
        "format_version": FORMAT_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "sha256": _checksum(payload),
        "state": payload,
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")


def decode_state(raw: bytes) -> GameState:
    """Liest und prüft einen gespeicherten Spielstand. Wirft ``ValueError``."""
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Datei ist kein gültiges JSON: {exc}") from exc
    if not isinstance(envelope, dict) or envelope.get("app") != APP_MARKER:
        raise ValueError("Datei ist kein BK-Scoreboard-Spielstand.")
    if envelope.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Unbekannte Formatversion: {envelope.get('format_version')!r}")
    payload = envelope.get("state")
    if not isinstance(payload, dict):
        raise ValueError("Spielstand-Daten fehlen.")
    if envelope.get("sha256") != _checksum(payload):
        raise ValueError("Prüfsumme stimmt nicht – Datei ist beschädigt.")
    return GameState.from_dict(payload)


def _fsync_dir(directory: Path) -> None:
    """Verzeichniseintrag auf Platte schreiben (nur POSIX möglich)."""
    if os.name != "posix":
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def atomic_write_bytes(target: Path, data: bytes, retries: int = 5) -> None:
    """Schreibt ``data`` atomar nach ``target`` (tmp + fsync + replace).

    Unter Windows kann ``os.replace`` kurzzeitig scheitern, wenn z. B. ein
    Virenscanner die Datei geöffnet hat – daher einige Wiederholungen.
    """
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            os.replace(tmp, target)
            _fsync_dir(target.parent)
            return
        except PermissionError as exc:  # Datei kurzzeitig gesperrt (Windows)
            last_error = exc
            time.sleep(0.05 * (attempt + 1))
    raise StorageError(f"Datei konnte nicht ersetzt werden: {target} ({last_error})")


class GameStorage:
    """Verwaltet Spielstand-, Archiv- und Ergebnisdateien."""

    def __init__(self, data_dir: Path, results_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.results_dir = Path(results_dir)
        self.active_path = self.data_dir / "active_game.json"
        self.backup_path = self.data_dir / "active_game.json.bak"
        self.tmp_path = self.data_dir / "active_game.json.tmp"
        self.archive_dir = self.data_dir / "archive"
        self.corrupt_dir = self.data_dir / "corrupt"

    # --------------------------------------------------------- Verzeichnisse
    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.results_dir, self.archive_dir, self.corrupt_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ Speichern
    def save_active(self, state: GameState) -> None:
        """Speichert den aktiven Spielstand sicher. Wirft ``StorageError``."""
        try:
            self.ensure_directories()
            state.revision += 1
            data = encode_state(state)
            # 1) neuen Stand vollständig und synchron in .tmp schreiben
            with open(self.tmp_path, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            # 2) bisherigen Stand als Rückfallebene sichern
            if self.active_path.exists():
                try:
                    shutil.copyfile(self.active_path, self.backup_path)
                except OSError as exc:  # Backup ist optional, Hauptdatei nicht
                    log.warning("Backup-Kopie fehlgeschlagen: %s", exc)
            # 3) atomar ersetzen
            for attempt in range(5):
                try:
                    os.replace(self.tmp_path, self.active_path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
            _fsync_dir(self.data_dir)
        except (OSError, ValueError, TypeError) as exc:
            log.exception("Spielstand konnte nicht gespeichert werden")
            raise StorageError(str(exc)) from exc

    # --------------------------------------------------------------- Laden
    def has_active_files(self) -> bool:
        return any(p.exists() for p in (self.active_path, self.tmp_path, self.backup_path))

    def load_active(self) -> LoadResult:
        """Lädt den neuesten gültigen Spielstand (Haupt-, Temp- oder Backup-Datei)."""
        if not self.has_active_files():
            return LoadResult(LoadStatus.NONE)
        candidates: list[tuple[int, int, Path, GameState]] = []
        errors: list[str] = []
        # Priorität bei gleicher Revision: Hauptdatei > tmp > bak
        for priority, path in enumerate((self.active_path, self.tmp_path, self.backup_path)):
            if not path.exists():
                continue
            try:
                state = decode_state(path.read_bytes())
                candidates.append((state.revision, -priority, path, state))
            except (OSError, ValueError) as exc:
                errors.append(f"{path.name}: {exc}")
                log.warning("Spielstand-Datei ungültig: %s – %s", path, exc)
        if not candidates:
            return LoadResult(LoadStatus.CORRUPT, message="; ".join(errors))
        candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
        _, _, path, state = candidates[0]
        if path == self.active_path:
            return LoadResult(LoadStatus.OK, state, path)
        log.warning("Spielstand aus %s wiederhergestellt", path.name)
        return LoadResult(LoadStatus.RECOVERED, state, path, "; ".join(errors))

    # ------------------------------------------------ Archiv / Aufräumen
    def archive_active(self, state: GameState | None, reason: str) -> Path | None:
        """Verschiebt den aktiven Spielstand ins Archiv und räumt auf.

        Es wird nie etwas gelöscht, das nicht vorher sicher archiviert wurde.
        """
        self.ensure_directories()
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"{stamp}_{reason}"
        if state is not None:
            base = f"{stamp}_{state.mode.key}_{reason}"
        target = _unique_path(self.archive_dir / f"{base}.json")
        try:
            if state is not None:
                atomic_write_bytes(target, encode_state(state))
            elif self.active_path.exists():
                shutil.copyfile(self.active_path, target)
            else:
                target = None
            for path in (self.active_path, self.backup_path, self.tmp_path):
                if path.exists():
                    path.unlink()
            _fsync_dir(self.data_dir)
            return target
        except OSError as exc:
            log.exception("Archivieren fehlgeschlagen")
            raise StorageError(str(exc)) from exc

    def list_archive(self) -> list[ArchiveEntry]:
        """Alle lesbaren Partien aus ``data/archive`` (neueste zuerst).

        Beschädigte Dateien werden übersprungen und protokolliert, nie gelöscht.
        """
        entries: list[ArchiveEntry] = []
        if not self.archive_dir.is_dir():
            return entries
        for path in self.archive_dir.glob("*.json"):
            try:
                entries.append(ArchiveEntry(path, decode_state(path.read_bytes())))
            except (OSError, ValueError) as exc:
                log.warning("Archivdatei nicht lesbar, übersprungen: %s – %s", path.name, exc)
        entries.sort(key=lambda e: (e.state.started_at, e.path.name), reverse=True)
        return entries

    def restore_from_archive(self, entry: ArchiveEntry) -> GameState:
        """Macht eine abgebrochene/unterbrochene Partie wieder zur aktiven Partie.

        Reihenfolge absturzsicher: erst als aktive Partie speichern, dann die
        Archivdatei entfernen (sonst gäbe es sie später doppelt im Archiv).
        """
        if self.has_active_files():
            raise StorageError("Es gibt bereits eine aktive Partie.")
        try:
            state = decode_state(entry.path.read_bytes())
        except (OSError, ValueError) as exc:
            raise StorageError(f"Archivdatei nicht lesbar: {exc}") from exc
        if state.status is GameStatus.FINISHED:
            raise StorageError("Beendete Partien können nicht weitergespielt werden.")
        state.status = GameStatus.RUNNING
        state.finished_at = None
        self.save_active(state)
        try:
            entry.path.unlink()
        except OSError:
            log.warning("Archivdatei konnte nach dem Weiterspielen nicht entfernt werden: %s", entry.path)
        return state

    def quarantine_corrupt(self) -> list[Path]:
        """Verschiebt unlesbare Spielstand-Dateien nach ``data/corrupt``."""
        self.ensure_directories()
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        moved: list[Path] = []
        for path in (self.active_path, self.tmp_path, self.backup_path):
            if path.exists():
                target = _unique_path(self.corrupt_dir / f"{stamp}_{path.name}")
                try:
                    shutil.move(str(path), str(target))
                    moved.append(target)
                except OSError:
                    log.exception("Beschädigte Datei konnte nicht verschoben werden: %s", path)
        return moved

    # ------------------------------------------------------------ Ergebnis
    def save_result(self, state: GameState, base_name: str) -> Path:
        """Speichert das Endergebnis als JSON neben dem PDF (``results/``)."""
        self.ensure_directories()
        target = _unique_path(self.results_dir / f"{base_name}.json")
        try:
            atomic_write_bytes(target, encode_state(state))
        except OSError as exc:
            raise StorageError(str(exc)) from exc
        return target


def _unique_path(path: Path) -> Path:
    """Hängt _2, _3 … an, falls die Datei schon existiert."""
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
