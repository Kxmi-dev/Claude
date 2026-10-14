"""
Erstellt die eigenständige Windows-Programmversion (.exe) des BK-Scoreboards.

Aufruf im Programmordner (Pakete aus requirements.txt + PyInstaller installiert):
    python build_exe.py              Selbsttest ausführen, dann .exe erstellen
    python build_exe.py --skip-tests nur .exe erstellen

Am einfachsten per Doppelklick auf build_exe.bat.

Ergebnis: dist\\BK-Scoreboard\\
    BK-Scoreboard.exe   das Programm (Doppelklick startet im Vollbild)
    _internal\\          Python, Qt, ReportLab … (nicht verändern)
    config.py           Einstellungen – editierbar, Programm danach neu starten
    assets\\             Logo und Symbol – austauschbar
    README.md

Dieser Ordner läuft auf jedem Windows-PC (64 Bit) OHNE Python- oder pip-Installation.
Zum Weitergeben den kompletten Ordner kopieren (nicht nur die .exe).
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "BK-Scoreboard"
DIST = ROOT / "dist"
TARGET = DIST / NAME
WORK = ROOT / "build"
USER_DIRS = ("data", "results", "logs")   # dürfen beim Neubau nie verloren gehen


def fail(text: str) -> int:
    print(f"\nFEHLER: {text}\n")
    return 1


def has_user_data(folder: Path) -> bool:
    """True, wenn im Ausgabeordner bereits Spielstände, Ergebnisse oder Logs liegen."""
    return any((folder / name).is_dir() and any((folder / name).iterdir()) for name in USER_DIRS)


def main() -> int:
    print(f"=== {NAME}: .exe erstellen ===")
    for package in ("PyInstaller", "PySide6", "reportlab"):
        if importlib.util.find_spec(package) is None:
            return fail(f"Paket '{package}' fehlt. Bitte ausführen:\n"
                        f"   {sys.executable} -m pip install -r requirements.txt pyinstaller")

    # PyInstaller leert den Ausgabeordner vollständig – echte Spieldaten schützen
    if has_user_data(TARGET):
        return fail(f"In {TARGET} liegen bereits Spielstände/Ergebnisse (data, results oder logs).\n"
                    "Der Ordner wird beim Erstellen komplett geleert. Bitte das Programm vorher an seinen\n"
                    "endgültigen Ort kopieren (z. B. C:\\BK-Scoreboard) und dist\\BK-Scoreboard löschen.")

    if "--skip-tests" not in sys.argv:
        print("\n--- Selbsttest ---")
        result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--selftest"], cwd=ROOT)
        if result.returncode != 0:
            return fail("Der Selbsttest ist fehlgeschlagen – es wird keine .exe erstellt.")

    print("\n--- PyInstaller ---")
    import PyInstaller.__main__

    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--onedir",               # Ordner-Variante: schneller Start, weniger Virenscanner-Fehlalarme
        "--windowed",             # kein Konsolenfenster
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(WORK),
        "--specpath", str(WORK),
        "--paths", str(ROOT),
        "--hidden-import", "config",     # eingebaute Standard-Einstellungen
    ]
    # Nicht benötigte Pakete ausschließen (sonst würden sie unnötig mitgepackt)
    for module in ("tkinter", "numpy", "yaml", "PIL.ImageQt", "PIL.ImageTk"):
        args += ["--exclude-module", module]
    icon = ROOT / "assets" / "app.ico"
    if icon.is_file():
        args += ["--icon", str(icon)]
    try:
        PyInstaller.__main__.run(args)
    except SystemExit as exc:          # PyInstaller beendet sich bei Fehlern per SystemExit
        if exc.code:
            return fail(f"PyInstaller ist fehlgeschlagen (Code {exc.code}).")

    exe = TARGET / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not exe.is_file():
        return fail(f"Die Programmdatei wurde nicht erstellt: {exe}")

    # Editierbare Dateien neben die .exe legen
    shutil.copy2(ROOT / "config.py", TARGET / "config.py")
    shutil.copytree(ROOT / "assets", TARGET / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "README.md", TARGET / "README.md")

    size_mb = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file() and not p.is_symlink()) / 1_000_000
    print(f"""
=== Fertig ===
Programmordner:  {TARGET}   ({size_mb:.0f} MB)
Programm:        {exe.name}

Diesen KOMPLETTEN Ordner an seinen endgültigen Ort kopieren, z. B. C:\\BK-Scoreboard
(nicht nach C:\\Programme – dort darf das Programm keine Spielstände speichern).
Auf dem Ziel-PC ist keine Python- oder pip-Installation nötig.
Einstellungen ändern: config.py neben der .exe bearbeiten, Programm neu starten.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
