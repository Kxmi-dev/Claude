"""Gemeinsame Test-Hilfen."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from bk.models import GameMode  # noqa: E402

BK100 = GameMode(key="BK100", title="100 Stoß", strokes=100, halftime_after=50, grid_columns=10, highlight_last=5)
BK50 = GameMode(key="BK50", title="50 Stoß", strokes=50, halftime_after=25, grid_columns=10, highlight_last=5)


class FakeClock:
    """Steuerbare Uhr: Sperrzeiten testen, ohne wirklich zu warten."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TempDir:
    """Temporäres Verzeichnis, das nach dem Test gelöscht wird."""

    def __init__(self) -> None:
        self.path = Path(tempfile.mkdtemp(prefix="bk_test_"))

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "TempDir":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()
