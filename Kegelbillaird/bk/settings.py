"""
Laufzeit-Einstellungen.

``config.py`` ist die Datei, die der Anwender bearbeitet. Beim Start wird
daraus ein unveränderliches ``AppSettings``-Objekt gebaut und an alle
Programmteile übergeben (statt überall ``config`` zu importieren). So
bleiben die Module testbar: Tests erzeugen einfach eigene Einstellungen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from .models import GameMode


@dataclass(frozen=True)
class AppSettings:
    app_title: str
    app_version: str
    club_name: str
    input_lock_seconds: float
    undo_lock_seconds: float
    abort_confirm_seconds: float
    numpad_only: bool
    fullscreen: bool
    auto_enable_numlock: bool
    numlock_check_seconds: float
    autosave_seconds: float
    history_length: int
    game_modes: tuple[GameMode, ...]
    show_unavailable_modes: bool
    pdf_rows_per_block: int
    pdf_blocks_per_row: int
    open_pdf_after_game: bool
    show_report_after_game: bool
    replay_seconds_per_stroke: float
    archive_retention_days: int
    log_retention_days: int
    results_retention_days: int
    data_dir: Path
    results_dir: Path
    logs_dir: Path
    assets_dir: Path
    sound_enabled: bool = True
    halftime_sound: str = ""
    celebration_enabled: bool = True
    celebration_values: tuple[int, ...] = (6, 7)
    celebration_images: tuple[str, ...] = ()
    celebration_seconds: float = 3.0
    sounds_dir: Path = Path("sounds")
    images_dir: Path = Path("bilder")

    @property
    def logo_path(self) -> Path:
        return self.assets_dir / "logo.png"

    @property
    def icon_path(self) -> Path:
        return self.assets_dir / "icon.png"

    @property
    def menu_modes(self) -> tuple[GameMode, ...]:
        if self.show_unavailable_modes:
            return self.game_modes
        return tuple(m for m in self.game_modes if m.available)

    @classmethod
    def from_config(cls, cfg: ModuleType) -> "AppSettings":
        settings = cls(
            app_title=str(cfg.APP_TITLE),
            app_version=str(cfg.APP_VERSION),
            club_name=str(cfg.CLUB_NAME),
            input_lock_seconds=float(cfg.INPUT_LOCK_SECONDS),
            undo_lock_seconds=float(cfg.UNDO_LOCK_SECONDS),
            abort_confirm_seconds=float(cfg.ABORT_CONFIRM_SECONDS),
            numpad_only=bool(cfg.NUMPAD_ONLY),
            fullscreen=bool(cfg.FULLSCREEN),
            auto_enable_numlock=bool(cfg.AUTO_ENABLE_NUMLOCK),
            numlock_check_seconds=float(cfg.NUMLOCK_CHECK_SECONDS),
            autosave_seconds=float(cfg.AUTOSAVE_SECONDS),
            history_length=int(cfg.HISTORY_LENGTH),
            game_modes=tuple(cfg.GAME_MODES),
            show_unavailable_modes=bool(cfg.SHOW_UNAVAILABLE_MODES),
            pdf_rows_per_block=int(cfg.PDF_ROWS_PER_BLOCK),
            pdf_blocks_per_row=int(cfg.PDF_BLOCKS_PER_ROW),
            open_pdf_after_game=bool(cfg.OPEN_PDF_AFTER_GAME),
            # neuere Einstellungen mit Standardwert, damit ältere config.py-Dateien weiter funktionieren
            show_report_after_game=bool(getattr(cfg, "SHOW_REPORT_AFTER_GAME", True)),
            replay_seconds_per_stroke=float(getattr(cfg, "REPLAY_SECONDS_PER_STROKE", 0.8)),
            archive_retention_days=int(getattr(cfg, "ARCHIVE_RETENTION_DAYS", 30)),
            log_retention_days=int(getattr(cfg, "LOG_RETENTION_DAYS", 30)),
            results_retention_days=int(getattr(cfg, "RESULTS_RETENTION_DAYS", 0)),
            data_dir=Path(cfg.DATA_DIR),
            results_dir=Path(cfg.RESULTS_DIR),
            logs_dir=Path(cfg.LOGS_DIR),
            assets_dir=Path(cfg.ASSETS_DIR),
            sound_enabled=bool(getattr(cfg, "SOUND_ENABLED", True)),
            halftime_sound=str(getattr(cfg, "HALFTIME_SOUND", "") or ""),
            celebration_enabled=bool(getattr(cfg, "CELEBRATION_ENABLED", True)),
            celebration_values=tuple(int(v) for v in getattr(cfg, "CELEBRATION_VALUES", (6, 7))),
            celebration_images=tuple(str(n) for n in (getattr(cfg, "CELEBRATION_IMAGES", ()) or ())),
            celebration_seconds=float(getattr(cfg, "CELEBRATION_SECONDS", 3)),
            sounds_dir=Path(getattr(cfg, "SOUNDS_DIR", Path(cfg.ASSETS_DIR).parent / "sounds")),
            images_dir=Path(getattr(cfg, "IMAGES_DIR", Path(cfg.ASSETS_DIR).parent / "bilder")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.input_lock_seconds < 0:
            raise ValueError("INPUT_LOCK_SECONDS darf nicht negativ sein.")
        if self.undo_lock_seconds < 0:
            raise ValueError("UNDO_LOCK_SECONDS darf nicht negativ sein.")
        if self.abort_confirm_seconds <= 0:
            raise ValueError("ABORT_CONFIRM_SECONDS muss größer als 0 sein.")
        if self.numlock_check_seconds <= 0 or self.autosave_seconds <= 0:
            raise ValueError("Intervall-Einstellungen müssen größer als 0 sein.")
        if not any(m.available for m in self.game_modes):
            raise ValueError("GAME_MODES enthält keine spielbare Spielart.")
        keys = [m.key for m in self.game_modes]
        if len(keys) != len(set(keys)):
            raise ValueError("GAME_MODES enthält doppelte Schlüssel.")
        if self.pdf_rows_per_block < 5 or self.pdf_blocks_per_row < 1:
            raise ValueError("PDF-Einstellungen sind ungültig.")
        if min(self.archive_retention_days, self.log_retention_days, self.results_retention_days) < 0:
            raise ValueError("Die *_RETENTION_DAYS-Werte dürfen nicht negativ sein (0 = nie löschen).")
        if not 0.05 <= self.replay_seconds_per_stroke <= 10:
            raise ValueError("REPLAY_SECONDS_PER_STROKE muss zwischen 0.05 und 10 liegen.")
        if not 0.5 <= self.celebration_seconds <= 30:
            raise ValueError("CELEBRATION_SECONDS muss zwischen 0.5 und 30 liegen.")
        if any(not -7 <= v <= 7 for v in self.celebration_values):
            raise ValueError("CELEBRATION_VALUES darf nur Werte von -7 bis 7 enthalten.")
