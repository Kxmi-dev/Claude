"""
=====================================================================
  BK-Scoreboard – ZENTRALE KONFIGURATION
=====================================================================
Alle Einstellungen, die man im Vereinsalltag ändern möchte, stehen hier.
Nach einer Änderung das Programm einfach neu starten.
"""

import sys
from pathlib import Path

from bk.models import GameMode

# ---------------------------------------------------------------------
#  EINGABE
# ---------------------------------------------------------------------

# Sperrzeit nach jeder Wertung in Sekunden (Schutz vor Doppeleingaben).
INPUT_LOCK_SECONDS = 3

# Kurze Sperre nach [/] (Rücknahme), damit ein prellender Tastendruck
# nicht zwei Wertungen auf einmal zurücknimmt.
UNDO_LOCK_SECONDS = 1.0

# So lange wartet die Abbruch-Frage ([*] und dann [-]) auf Bestätigung.
ABORT_CONFIRM_SECONDS = 5

# True  = während der Partie zählen nur Tasten des Nummernblocks.
# False = zusätzlich die Ziffern-/Zeichentasten der normalen Tastatur.
NUMPAD_ONLY = True

# ---------------------------------------------------------------------
#  ANZEIGE
# ---------------------------------------------------------------------

FULLSCREEN = True            # Start direkt im Vollbild
HISTORY_LENGTH = 5           # Anzahl der Einträge unter "Letzte Stöße"

APP_TITLE = "BK-Scoreboard"
APP_VERSION = "2.0"
CLUB_NAME = "SG Grün-Weiß Schlepzig e.V."

# ---------------------------------------------------------------------
#  NUMLOCK
# ---------------------------------------------------------------------

# True  = NumLock beim Start prüfen und bei Bedarf automatisch einschalten
#         (auch später, falls es während des Betriebs ausgeschaltet wird).
# False = nur prüfen und in der Fußleiste warnen.
AUTO_ENABLE_NUMLOCK = True
NUMLOCK_CHECK_SECONDS = 2    # Prüfintervall in Sekunden

# ---------------------------------------------------------------------
#  SPEICHERUNG
# ---------------------------------------------------------------------

# Gespeichert wird IMMER sofort nach jeder Wertung und Rücknahme.
# Zusätzlich wird die laufende Spieldauer in diesem Intervall gesichert.
AUTOSAVE_SECONDS = 15

# ---------------------------------------------------------------------
#  SPIELARTEN
# ---------------------------------------------------------------------
# Neue Spielart = neue Zeile. Reihenfolge = Reihenfolge im Hauptmenü.
#   key            Kürzel, auch Anfang des PDF-Dateinamens (BK100_...)
#   title          Text im Menü und in der Titelleiste
#   strokes        Anzahl Stöße
#   halftime_after Halbzeitstand wird nach diesem Stoß festgehalten
#   grid_columns   Spalten im Stoß-Raster (10 → 10 × 10 bei 100 Stoß)
#   highlight_last letzte Stöße, die im Raster gelb markiert werden
#   available      False = wird angezeigt, ist aber nicht startbar

GAME_MODES = (
    GameMode(key="BK100", title="100 Stoß", strokes=100, halftime_after=50,
             grid_columns=10, highlight_last=5),
    GameMode(key="BK50", title="50 Stoß", strokes=50, halftime_after=25,
             grid_columns=10, highlight_last=5),
    # Die folgenden Spielarten sind im BKV-Regelwerk (BK 50 / BK 100) nicht
    # definiert. Sie werden erst freigeschaltet, wenn ihre Regeln feststehen.
    GameMode(key="BK2x50", title="2x 50 Stoß", available=False,
             note="Regeln für „2x 50 Stoß“ sind noch nicht hinterlegt."),
    GameMode(key="ZWEIKAMPF", title="Zweikampf", available=False,
             note="Regeln für „Zweikampf“ sind noch nicht hinterlegt."),
)

# False = nicht verfügbare Spielarten im Menü ausblenden.
SHOW_UNAVAILABLE_MODES = True

# ---------------------------------------------------------------------
#  PDF
# ---------------------------------------------------------------------

PDF_ROWS_PER_BLOCK = 25      # Zeilen je Spaltenblock der Stoßliste
PDF_BLOCKS_PER_ROW = 4       # Spaltenblöcke nebeneinander (4 × 25 = 100 auf einer Seite)

# Das PDF wird nach jeder Partie IMMER automatisch in "results" gespeichert.
# True = danach das Statistik-Fenster öffnen (Spielbericht mit Speichern / Drucken / Schließen)
SHOW_REPORT_AFTER_GAME = True
# True = das PDF zusätzlich im PDF-Programm von Windows öffnen
OPEN_PDF_AFTER_GAME = False

# ---------------------------------------------------------------------
#  ARCHIV
# ---------------------------------------------------------------------

# Tempo der Wiedergabe in Sekunden pro Stoß (während der Wiedergabe mit [+] / [−] änderbar)
REPLAY_SECONDS_PER_STROKE = 0.8

# ---------------------------------------------------------------------
#  AUFRÄUMEN (damit die Festplatte nicht vollläuft)
# ---------------------------------------------------------------------
# Dateien, die älter sind als die angegebene Anzahl Tage, werden automatisch
# gelöscht – beim Programmstart und danach alle 6 Stunden. 0 = nie löschen.

ARCHIVE_RETENTION_DAYS = 30  # Archiv (data\archive) und beschädigte Spielstände (data\corrupt)
LOG_RETENTION_DAYS = 30      # Protokolldateien (logs)
RESULTS_RETENTION_DAYS = 0   # PDFs und Ergebnisse (results) – 0 = nie löschen (empfohlen)

# ---------------------------------------------------------------------
#  ORDNER (relativ zum Programmordner)
# ---------------------------------------------------------------------

if getattr(sys, "frozen", False):          # als .exe gepackt (z. B. PyInstaller)
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"        # aktiver Spielstand, Archiv
RESULTS_DIR = BASE_DIR / "results"  # PDF + JSON jeder beendeten Partie
LOGS_DIR = BASE_DIR / "logs"        # application.log
ASSETS_DIR = BASE_DIR / "assets"    # logo.png, icon.png
