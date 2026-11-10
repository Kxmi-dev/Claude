"""
Protokollierung nach ``logs/application.log``.

* Jeden Tag beginnt eine neue Datei; die Vortage heißen
  ``application.log.JJJJ-MM-TT``. Dateien älter als LOG_RETENTION_DAYS
  löscht ``bk.maintenance`` automatisch.
* nicht abgefangene Python-Ausnahmen werden ins Log geschrieben
* harte Abstürze (z. B. im Grafiktreiber) landen per ``faulthandler``
  in ``logs/crash.log``; ist diese Datei älter als LOG_RETENTION_DAYS,
  wird sie beim Start geleert.
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_crash_file = None  # muss offen bleiben, solange das Programm läuft


def crash_log_mode(path: Path, retention_days: int, now: float | None = None) -> str:
    """"w" (leeren), wenn crash.log älter als ``retention_days`` ist, sonst "a" (anhängen)."""
    if retention_days <= 0 or not path.exists():
        return "a"
    age = (time.time() if now is None else now) - path.stat().st_mtime
    return "w" if age > retention_days * 86_400 else "a"


def setup_logging(logs_dir: Path, level: int = logging.INFO, retention_days: int = 30) -> Path:
    global _crash_file
    logs_dir = Path(logs_dir)
    log_file = logs_dir / "application.log"
    handlers: list[logging.Handler] = []
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        # neue Datei um Mitternacht; alte Tagesdateien löscht bk.maintenance nach Alter
        file_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=0, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
        handlers.append(file_handler)
        crash_path = logs_dir / "crash.log"
        _crash_file = open(crash_path, crash_log_mode(crash_path, retention_days), encoding="utf-8")
        faulthandler.enable(file=_crash_file, all_threads=True)
    except OSError as exc:  # Logging darf das Programm nie verhindern
        print(f"Warnung: Log-Datei nicht nutzbar ({exc})", file=sys.stderr)
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handlers.append(console)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)

    def excepthook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.getLogger("uncaught").critical("Nicht abgefangener Fehler", exc_info=(exc_type, exc, tb))

    sys.excepthook = excepthook
    threading.excepthook = lambda args: excepthook(args.exc_type, args.exc_value, args.exc_traceback)
    return log_file
