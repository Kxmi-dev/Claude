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

from .keys import KeyBindings
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
    celebration_minus_values: tuple[int, ...] = (-6, -7)
    celebration_seconds: float = 3.0
    sounds_dir: Path = Path("sounds")
    images_dir: Path = Path("bilder")
    key_bindings: KeyBindings = KeyBindings()
    # über das Einstellungsmenü änderbar (einstellungen.json)
    window_size: tuple[int, int] = (1280, 800)
    theme_mode: str = "klassisch"                       # "klassisch" oder "eigen"
    primary_color: tuple[int, int, int] = (223, 222, 202)
    secondary_color: tuple[int, int, int] = (192, 192, 192)
    end_sound: str = ""
    celebration_sound: str = ""                          # Ton bei +6 / +7 (CELEBRATION_VALUES)
    sound_volume: int = 80                               # 0 … 100 %
    printer_name: str = ""                               # "" = Windows-Standarddrucker
    pdf_save_dir: str = ""                               # "" = Ordner „Dokumente“
    disabled_images: tuple[str, ...] = ()                # z. B. "plus/bild.gif" – ausgeschaltete Bilder
    settings_file: Path = Path("einstellungen.json")
    club_logo_dir: Path = Path("vereinslogo")
    club_logo: str = ""                                  # Dateiname im Ordner „vereinslogo“, "" = kein Logo
    font_scale: int = 100                                # Schriftgröße in % (80 … 130)
    show_history: bool = True                            # Feld „Letzte Stöße“ anzeigen
    show_input_status: bool = True                       # Feld „Eingabe“ anzeigen
    result_lock_seconds: float = 5.0                     # Sperre der Auswertung nach Partie-Ende
    enter_skips_lock: bool = True                        # [Enter] beendet die Sperre nach einer Wertung
    grid_running_total: bool = True                      # Raster zeigt Gesamtpunkte (3, 6, 9) statt Einzelstoß

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
            celebration_minus_values=tuple(int(v) for v in getattr(cfg, "CELEBRATION_MINUS_VALUES", (-6, -7))),
            celebration_seconds=float(getattr(cfg, "CELEBRATION_SECONDS", 3)),
            sounds_dir=Path(getattr(cfg, "SOUNDS_DIR", Path(cfg.ASSETS_DIR).parent / "sounds")),
            images_dir=Path(getattr(cfg, "IMAGES_DIR", Path(cfg.ASSETS_DIR).parent / "bilder")),
            key_bindings=KeyBindings.from_config(cfg),
            window_size=_size(getattr(cfg, "WINDOW_SIZE", (1280, 800))),
            end_sound=str(getattr(cfg, "END_SOUND", "") or ""),
            celebration_sound=str(getattr(cfg, "CELEBRATION_SOUND", "") or ""),
            sound_volume=int(getattr(cfg, "SOUND_VOLUME", 80)),
            settings_file=Path(getattr(cfg, "SETTINGS_FILE", Path(cfg.DATA_DIR).parent / "einstellungen.json")),
            club_logo_dir=Path(getattr(cfg, "CLUB_LOGO_DIR", Path(cfg.ASSETS_DIR).parent / "vereinslogo")),
            club_logo=str(getattr(cfg, "CLUB_LOGO", "") or ""),
            font_scale=int(getattr(cfg, "FONT_SCALE", 100)),
            show_history=bool(getattr(cfg, "SHOW_HISTORY", True)),
            show_input_status=bool(getattr(cfg, "SHOW_INPUT_STATUS", True)),
            result_lock_seconds=float(getattr(cfg, "RESULT_LOCK_SECONDS", 5)),
            enter_skips_lock=bool(getattr(cfg, "ENTER_SKIPS_LOCK", True)),
            grid_running_total=bool(getattr(cfg, "GRID_RUNNING_TOTAL", True)),
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
        if any(not -7 <= v <= 7 for v in self.celebration_values + self.celebration_minus_values):
            raise ValueError("CELEBRATION_VALUES und CELEBRATION_MINUS_VALUES dürfen nur Werte von -7 bis 7 enthalten.")
        if not 0 <= self.sound_volume <= 100:
            raise ValueError("SOUND_VOLUME muss zwischen 0 und 100 liegen.")
        if any(not 320 <= v <= 10000 for v in self.window_size):
            raise ValueError("WINDOW_SIZE ist ungültig (Breite/Höhe 320 bis 10000).")
        if self.theme_mode not in THEME_MODES:
            raise ValueError("Farbschema muss „klassisch“ oder „eigen“ sein.")
        for color in (self.primary_color, self.secondary_color):
            if len(color) != 3 or any(not 0 <= int(c) <= 255 for c in color):
                raise ValueError("Farben bestehen aus drei Werten von 0 bis 255 (R, G, B).")
        if not 0 <= self.result_lock_seconds <= 30:
            raise ValueError("RESULT_LOCK_SECONDS muss zwischen 0 und 30 liegen.")
        if self.font_scale not in FONT_SCALES:
            raise ValueError(f"FONT_SCALE muss einer dieser Werte sein: {', '.join(map(str, FONT_SCALES))}.")
        if self.history_length < 1 or self.history_length > 10:
            raise ValueError("HISTORY_LENGTH muss zwischen 1 und 10 liegen.")
        self.key_bindings.validate()

    @property
    def images_plus_dir(self) -> Path:
        return self.images_dir / "plus"

    @property
    def images_minus_dir(self) -> Path:
        return self.images_dir / "minus"

    @property
    def club_logo_path(self) -> Path | None:
        """Gewähltes Vereinslogo oder None (keins gewählt)."""
        return self.club_logo_dir / self.club_logo if self.club_logo else None


THEME_MODES = ("klassisch", "eigen")
FONT_SCALES = (80, 90, 100, 110, 120, 130)


def _size(value) -> tuple[int, int]:
    width, height = value
    return int(width), int(height)

