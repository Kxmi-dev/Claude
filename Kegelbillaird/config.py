"""
=====================================================================
  BK-Scoreboard – ZENTRALE KONFIGURATION
=====================================================================
Fast alles lässt sich bequem im Programm einstellen: Hauptmenü → „Einstellungen“.
Was dort geändert wird, steht in „einstellungen.json“ und hat Vorrang vor
dieser Datei. Diese Datei liefert nur die Grundwerte (bzw. Werte, die es im
Menü nicht gibt) und muss im Normalfall nicht mehr bearbeitet werden.
Nach einer Änderung hier das Programm neu starten.
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

# So lange sind [Enter]/[*] in der Auswertung nach Partie-Ende gesperrt (Schutz vor
# versehentlichem Doppeldruck direkt ins Hauptmenü). 0 = keine Sperre.
RESULT_LOCK_SECONDS = 5

# True = [Enter] beendet die Sperrzeit nach einer Wertung sofort (GESPERRT -> BEREIT).
ENTER_SKIPS_LOCK = True

# True  = während der Partie zählen nur Tasten des Nummernblocks.
# False = zusätzlich die Ziffern-/Zeichentasten der normalen Tastatur.
NUMPAD_ONLY = True

# ---------------------------------------------------------------------
#  ANZEIGE
# ---------------------------------------------------------------------

FULLSCREEN = True            # Start direkt im Vollbild
WINDOW_SIZE = (1280, 800)    # Fenstergröße, wenn FULLSCREEN = False
HISTORY_LENGTH = 5           # Anzahl der Einträge unter "Letzte Stöße"

APP_TITLE = "BK-Scoreboard"
APP_VERSION = "3.0.0"
CLUB_NAME = "SG Grün-Weiß Schlepzig e.V."

# Vereinslogo im Hauptmenü (unter dem BK-Bild): Dateiname im Ordner „vereinslogo“,
# "" = kein Logo. Bequemer: im Einstellungsmenü unter „Anzeige“ auswählen.
CLUB_LOGO = ""

# Schriftgröße in Prozent: 80, 90, 100, 110, 120 oder 130
FONT_SCALE = 100

# Felder in der Zählansicht ein-/ausblenden (auch im Einstellungsmenü unter „Anzeige“)
SHOW_HISTORY = True          # „Letzte Stöße“
SHOW_INPUT_STATUS = True     # „Eingabe“ (BEREIT / MINUS / GESPERRT)

# Raster: True = jedes Kästchen zeigt den Gesamtstand (3, 6, 9 …), False = den einzelnen Stoß.
# Leerstöße (0) stehen in beiden Fällen als „X“ im Raster.
GRID_RUNNING_TOTAL = True

# ---------------------------------------------------------------------
#  TASTENBELEGUNG
# ---------------------------------------------------------------------
# Hier legst du fest, mit welchen Tasten das Programm bedient wird. Die
# Legende in der Fußleiste und alle Hinweise im Programm passen sich an.
# Pro Aktion eine Liste: Die ERSTE Taste steht in der Legende, weitere sind
# zusätzliche Möglichkeiten.
#
# Erlaubte Namen:
#   Zeichen        +  -  /  *  .  ,        Ziffern 0-9        Buchstaben A-Z
#   Sondertasten   Enter  Esc  Space  Tab  Backspace  Delete  Insert  Home  End
#                  PageUp  PageDown  Up  Down  Left  Right      F1 ... F12
# Die Ziffern 0-7 für die Wertung selbst sind fest und nicht änderbar.
# Eine Taste darf nicht doppelt belegt sein (das Programm meldet das beim Start).
# Tasten, die es nicht auf dem Nummernblock gibt (Buchstaben, F-Tasten, Esc ...),
# funktionieren in der Partie auch bei NUMPAD_ONLY = True.

# --- In der Partie ---
KEY_PLUS = ["+"]             # Plus wählen (Plus ist ohnehin voreingestellt; hebt ein gewähltes Minus auf)
KEY_MINUS = ["-"]            # Minus wählen; ist auch das „Ja“ bei der Abbruch-Frage
KEY_UNDO = ["/"]             # letzte Wertung zurücknehmen
KEY_ABORT = ["*"]            # Partie beenden/abbrechen (danach mit KEY_MINUS bestätigen)

# --- In Menüs, Archiv, Auswertung und Wiedergabe ---
KEY_UP = ["8", "Up"]         # nach oben (im Bericht: hoch blättern)
KEY_DOWN = ["2", "Down"]     # nach unten (im Bericht: runter blättern)
KEY_LEFT = ["4", "Left"]     # Auswertung: Knopf links
KEY_RIGHT = ["6", "Right"]   # Auswertung: Knopf rechts
KEY_ENTER = ["Enter"]        # bestätigen; in der Wiedergabe Pause/Weiter
KEY_BACK = ["*", "Esc"]      # zurück / Fenster schließen / Wiedergabe beenden

# ---------------------------------------------------------------------
#  TON UND BILDER (reine Zugabe – fehlt etwas, läuft die Partie normal weiter)
# ---------------------------------------------------------------------

# Töne: .wav oder .mp3 im Ordner "sounds" neben der .exe (werden im Menü automatisch angeboten).
# Halbzeit = nach Stoß 25 bei 50 Stoß bzw. nach Stoß 50 bei 100 Stoß. Leer = kein Ton.
# Hat der PC/Monitor keine Tonausgabe, blinkt das Halbzeit-Feld trotzdem.
SOUND_ENABLED = True
HALFTIME_SOUND = "halbzeit.wav"
END_SOUND = ""               # Ton am Partie-Ende
CELEBRATION_SOUND = ""       # Ton bei +6 / +7 (Datei im Ordner sounds), "" = kein Ton
SOUND_VOLUME = 80            # Lautstärke 0 … 100 %

# Bilder/GIFs: ALLE Bilder in "bilder\\plus" erscheinen bei CELEBRATION_VALUES,
# alle in "bilder\\minus" bei CELEBRATION_MINUS_VALUES (Ordner leer -> Plus-Bilder).
# Eine Datei = immer diese, mehrere = zufällig (nie zweimal hintereinander dieselbe).
# Einzelne Bilder lassen sich im Menü ausschalten. () schaltet die Bilder für diese Werte ab.
CELEBRATION_ENABLED = True
CELEBRATION_VALUES = (6, 7)
CELEBRATION_MINUS_VALUES = (-6, -7)
CELEBRATION_SECONDS = 3      # So lange bleibt das Bild stehen

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
    GameMode(key="BK25", title="Billiard vs Fußball", strokes=25, halftime_after=None,
             grid_columns=5, highlight_last=5),
)

# False = nicht verfügbare Spielarten im Menü ausblenden.
SHOW_UNAVAILABLE_MODES = True

# ---------------------------------------------------------------------
#  PDF
# ---------------------------------------------------------------------

PDF_ROWS_PER_BLOCK = 25      # Zeilen je Spaltenblock der Stoßliste
PDF_BLOCKS_PER_ROW = 4       # Spaltenblöcke nebeneinander (4 × 25 = 100 auf einer Seite)

# Das PDF wird nach jeder Partie IMMER automatisch in "results" gespeichert.
# True = danach die Auswertung zeigen (mit Als PDF speichern / Drucken / Weiter)
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
SOUNDS_DIR = BASE_DIR / "sounds"    # Töne (WAV)
IMAGES_DIR = BASE_DIR / "bilder"    # Bilder und GIFs (Unterordner plus und minus)
SETTINGS_FILE = BASE_DIR / "einstellungen.json"   # Werte aus dem Einstellungsmenü
CLUB_LOGO_DIR = BASE_DIR / "vereinslogo"   # Vereinslogo (Bild hineinziehen, in den Einstellungen wählen)
