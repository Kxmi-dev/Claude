"""
BK-Scoreboard – digitale Zähltafel für Kegelbillard.

Start:
    python main.py              Vollbild (Normalbetrieb)
    python main.py --windowed   im Fenster (zum Einrichten/Testen)
    python main.py --selftest   automatische Tests der Wertungslogik ausführen
    python main.py --pdf FILE   PDF aus einer Ergebnisdatei (results/*.json) neu erzeugen

Als .exe (erstellt mit build_exe.py) gelten dieselben Optionen, z. B.
    BK-Scoreboard.exe --windowed
In der .exe wird die config.py NEBEN der .exe gelesen – sie bleibt also editierbar.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import unittest
from pathlib import Path
from types import ModuleType

# True, wenn das Programm als .exe (PyInstaller) läuft
FROZEN = bool(getattr(sys, "frozen", False))

# Quellcode-Ordner (bei der .exe: interner, gepackter Ordner)
BASE_DIR = Path(__file__).resolve().parent
# Ordner mit config.py, assets, data, results, logs (bei der .exe: Ordner der .exe)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else BASE_DIR

# Programmordner in den Suchpfad aufnehmen (Start aus beliebigem Verzeichnis)
if not FROZEN:
    sys.path.insert(0, str(BASE_DIR))

# Dateien, die neben main.py vorhanden sein müssen (Ordnerstruktur beachten!)
REQUIRED_FILES = (
    "config.py",
    "bk/__init__.py", "bk/models.py", "bk/game.py", "bk/input_logic.py", "bk/storage.py",
    "bk/pdf_report.py", "bk/numlock.py", "bk/settings.py", "bk/logging_setup.py", "bk/maintenance.py",
    "bk/media.py", "bk/power.py", "bk/autostart.py", "bk/keys.py", "bk/user_settings.py", "bk/ui/celebration.py", "bk/ui/settings_screen.py",
    "bk/ui/__init__.py", "bk/ui/theme.py", "bk/ui/widgets.py", "bk/ui/keymap.py",
    "bk/ui/menu_screen.py", "bk/ui/game_screen.py", "bk/ui/archive_screen.py",
    "bk/ui/report_output.py", "bk/ui/result_screen.py", "bk/ui/overlays.py", "bk/ui/main_window.py",
)


def show_message(text: str, error: bool = True) -> None:
    """Meldung ohne Qt anzeigen (Qt ist in diesem Moment evtl. nicht verfügbar).

    Ausgabe auf der Konsole; unter Windows zusätzlich als Hinweisfenster, weil die
    .exe kein Konsolenfenster besitzt.
    """
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        print(text, file=stream)
    if sys.platform == "win32" and (error or FROZEN):
        try:
            import ctypes
            title = "BK-Scoreboard – Fehler" if error else "BK-Scoreboard"
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)
        except Exception:
            pass


def show_startup_error(text: str) -> None:
    show_message(text, error=True)


def check_installation() -> bool:
    """Prüft, ob alle Programmdateien in der richtigen Ordnerstruktur vorliegen."""
    missing = [name for name in REQUIRED_FILES if not (BASE_DIR / name).is_file()]
    if not missing:
        return True
    shown = "\n".join("   " + name.replace("/", "\\") for name in missing[:8])
    if len(missing) > 8:
        shown += f"\n   … und {len(missing) - 8} weitere"
    hint = ""
    if (BASE_DIR / "models.py").is_file() or (BASE_DIR / "game_screen.py").is_file():
        hint = ("\nDie Programmdateien liegen offenbar ohne Unterordner direkt neben main.py.\n"
                "Die Dateien des Pakets gehören in den Ordner „bk“ bzw. „bk\\ui“.\n")
    show_startup_error(
        "Das BK-Scoreboard ist nicht vollständig installiert.\n\n"
        f"Im Ordner\n   {BASE_DIR}\nfehlen:\n{shown}\n{hint}\n"
        "Lösung: bk_scoreboard.zip vollständig entpacken (Rechtsklick → „Alle extrahieren…“).\n"
        "main.py, config.py und der Ordner „bk“ müssen im selben Ordner liegen.")
    return False


def check_packages(names: tuple[str, ...]) -> bool:
    """Prüft, ob die benötigten Python-Pakete installiert sind."""
    missing = [name for name in names if importlib.util.find_spec(name) is None]
    if not missing:
        return True
    show_startup_error(
        f"Benötigte Python-Pakete fehlen: {', '.join(missing)}\n\n"
        "Bitte install_windows.bat ausführen oder in der Eingabeaufforderung im Programmordner:\n"
        "   python -m pip install -r requirements.txt\n\n"
        f"Verwendetes Python: {sys.executable}")
    return False


if not FROZEN and not check_installation():   # in der .exe ist alles fest eingepackt
    sys.exit(2)

from bk.logging_setup import setup_logging  # noqa: E402
from bk.settings import AppSettings  # noqa: E402

log = logging.getLogger("main")


def load_config() -> ModuleType:
    """Lädt die Einstellungen.

    In der .exe hat die ``config.py`` neben der .exe Vorrang, damit Einstellungen
    ohne Neubau geändert werden können. Fehlt sie, gilt die eingebaute Fassung.
    """
    external = APP_DIR / "config.py"
    if FROZEN and external.is_file():
        spec = importlib.util.spec_from_file_location("config", external)
        if spec is None or spec.loader is None:
            raise ImportError(f"config.py kann nicht geladen werden: {external}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["config"] = module
        spec.loader.exec_module(module)
        return module
    import config
    return config


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BK-Scoreboard – Zähltafel für Kegelbillard")
    parser.add_argument("--windowed", action="store_true", help="im Fenster statt im Vollbild starten")
    parser.add_argument("--selftest", action="store_true", help="automatische Tests ausführen und beenden")
    parser.add_argument("--pdf", metavar="ERGEBNIS.json", help="PDF aus einer Ergebnisdatei neu erzeugen")
    return parser.parse_args(argv)


def run_selftest() -> int:
    """Führt alle Tests im Ordner ``tests`` aus (ohne die Oberfläche zu starten)."""
    tests_dir = Path(__file__).resolve().parent / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir), top_level_dir=str(tests_dir.parent))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def regenerate_pdf(settings: AppSettings, result_file: str) -> int:
    from bk.pdf_report import PdfError, write_report
    from bk.storage import decode_state

    try:
        state = decode_state(Path(result_file).read_bytes())
        path = write_report(state, settings.results_dir, settings.club_name, settings.app_title,
                            settings.logo_path, settings.pdf_rows_per_block, settings.pdf_blocks_per_row)
    except (OSError, ValueError, PdfError) as exc:
        show_message(f"PDF konnte nicht erstellt werden:\n{exc}", error=True)
        return 1
    show_message(f"PDF erstellt:\n{path}", error=False)
    return 0


def run_gui(settings: AppSettings, windowed: bool, store) -> int:
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    from bk.storage import GameStorage
    from bk.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_title)
    app.setApplicationVersion(settings.app_version)

    storage = GameStorage(settings.data_dir, settings.results_dir)
    try:
        storage.ensure_directories()
    except OSError as exc:
        log.critical("Datenordner nicht nutzbar: %s", exc)
        QMessageBox.critical(None, settings.app_title,
                             f"Die Datenordner können nicht angelegt werden:\n{exc}\n\n"
                             "Bitte Programm in einen beschreibbaren Ordner kopieren.")
        return 2

    # Nur eine Instanz darf gleichzeitig auf den Spielstand zugreifen
    lock = QLockFile(str(settings.data_dir / "bk_scoreboard.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.warning(None, settings.app_title, "Das BK-Scoreboard läuft bereits.")
        return 3

    window = MainWindow(settings, storage, store)
    window.show_window(force_windowed=windowed)
    log.info("Oberfläche gestartet (%s)", "Fenster" if windowed or not settings.fullscreen else "Vollbild")
    code = app.exec()
    lock.unlock()
    return code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config()
        settings = AppSettings.from_config(config)
    except Exception as exc:  # Tippfehler, Syntaxfehler, ungültige Werte …
        show_startup_error(f"Fehler in config.py:\n{type(exc).__name__}: {exc}")
        return 2
    log_file = setup_logging(settings.logs_dir, retention_days=settings.log_retention_days)
    log.info("=== %s %s startet (%s, Einstellungen: %s, Log: %s) ===", settings.app_title,
             settings.app_version, "exe" if FROZEN else "Python", getattr(config, "__file__", "?"), log_file)
    # Werte aus dem Einstellungsmenü (einstellungen.json) haben Vorrang vor config.py.
    # Eine beschädigte Datei verhindert nie den Start (dann gelten Sicherung bzw. Standard).
    from bk.user_settings import UserSettingsStore
    store = UserSettingsStore(settings)
    settings = store.load()
    log.info("Einstellungen aus dem Menü: %s", store.path)

    if not FROZEN:   # in der .exe sind alle Pakete enthalten
        needed = ("reportlab",) if args.pdf else ("PySide6", "reportlab")
        if not check_packages(needed):
            log.critical("Python-Pakete fehlen (%s)", sys.executable)
            return 2

    if args.selftest:
        if FROZEN:
            show_message("Der Selbsttest ist nur in der Python-Fassung verfügbar "
                         "(python main.py --selftest).\nBeim Erstellen der .exe wurde er bereits "
                         "automatisch ausgeführt.", error=False)
            return 0
        return run_selftest()
    if args.pdf:
        return regenerate_pdf(settings, args.pdf)
    try:
        return run_gui(settings, args.windowed, store)
    except Exception:
        log.critical("Unerwarteter Fehler – Programm wird beendet", exc_info=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
