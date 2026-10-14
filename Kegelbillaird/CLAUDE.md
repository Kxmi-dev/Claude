# CLAUDE.md – Übergabe BK-Scoreboard (Stand 14.10.2026)

Kontext für Claude Code. Antworten und Kommentare auf **Deutsch**. Ausführliche Doku: `README.md`.

## Was ist das?
Digitale Zähltafel für **Kegelbillard** (BKV-Regeln BK 50 / BK 100) für den Verein
**SG Grün-Weiß Schlepzig e.V.** – KEIN Billard-Simulator. Der Bediener steht am echten Tisch
und gibt jede Wertung am **Nummernblock** ein. Zielplattform: **Windows**, Vollbild,
Auslieferung als **.exe** (PyInstaller, onedir) ohne Python-Installation auf dem Vereins-PC.

Technik: Python 3.10+ (entwickelt mit 3.12), **PySide6** (Qt 6, inkl. QtPdf/QtPrintSupport),
**reportlab** (PDF), Pillow (kommt mit reportlab). Tests: `unittest`.

## Designvorgaben (verbindlich)
Nachgebaut nach zwei Screenshots des Altprogramms (Hauptmenü + Zählansicht, 1024×768):
silbergrau gewolkter Hintergrund, Titel-/Fußleiste `#dfdeca`, weiße Anzeigefelder mit grauem
Rahmen `#c0c0c0` und hellgrauer Beschriftungsplatte `#ebebeb` darunter, Menüknöpfe grau
`#d2d2d2` / gewählt `#fffff5` mit Schatten, Trennstrich `|` in Fußleiste `#9c2f1f`,
gelbe Rasterfelder `#ffffe1`. Logo `assets/logo.png` ist aus dem Screenshot ausgeschnitten.
Kein generisches Standard-GUI-Design einführen. Layout skaliert proportional
(Referenz 1024×768, `theme.ui_unit`), Zählansicht per Layout-Streckfaktoren.

## Verzeichnis
```
main.py              Einstieg: CLI (--windowed, --selftest, --pdf FILE), Datei-/Paketprüfung,
                     QLockFile (Einzelinstanz), lädt in der .exe die config.py NEBEN der .exe
config.py            Grundwerte (Nutzer braucht sie normalerweise nicht mehr – Einstellungsmenü)
einstellungen.json   Werte aus dem Einstellungsmenü (Vorrang vor config.py), atomar + .bak
build_exe.py/.bat    Selftest + PyInstaller → dist\BK-Scoreboard\ (bricht ab, wenn dort Spieldaten liegen)
install_windows.bat  .venv anlegen, requirements, Selftest
bk/models.py         GameMode, GameState (kein Spielername mehr!), GameStatus; strenge Prüfung beim Laden
bk/game.py           Engine: record/undo/finish/abort, total, minus_total, halftime, prognosis, value_counts
bk/input_logic.py    Eingabe-Zustandsautomat (Qt-frei, Uhr injizierbar)
bk/storage.py        atomar speichern (tmp→fsync→replace, .bak, SHA-256, Revision), Archiv, Wiederherstellen
bk/pdf_report.py     Spielbericht (PDF) – Raster in ganzen Punkten, Seitengröße 596×842
bk/maintenance.py    Löschen alter Archiv-/Log-/Ergebnisdateien
bk/numlock.py        Windows: GetKeyState + SendInput (Fallback keybd_event)
bk/settings.py       AppSettings aus config.py (neue Einträge per getattr mit Default → alte config.py bleibt gültig)
bk/logging_setup.py  logs/application.log (täglich neu), crash.log (faulthandler)
bk/ui/main_window.py Bildschirmwechsel, Startprüfung, Abschluss, Archiv-Aktionen, NumLockGuard, Cleanup-Timer
bk/ui/menu_screen.py Hauptmenü: 100 Stoß, 50 Stoß, Billiard vs Fußball (25 Stoß), Archiv, Einstellungen,
                     Beenden, Beenden & Herunterfahren (2× Enter innerhalb 5 s)
bk/ui/game_screen.py Zählansicht + Wiedergabe-Modus
bk/ui/archive_screen.py  Archivliste
bk/ui/result_screen.py   Auswertung im Hauptfenster (Kennzahlen, Raster, Anzahl je Wertung, Knöpfe)
bk/ui/report_output.py   PDF speichern (ohne Nachfrage) + drucken (ohne Dialog), gleiche Bytes wie results-PDF
bk/ui/overlays.py    Abfrage-Karten (Fortsetzen, Abbruch, Archiv-Auswahl, Fehler)
bk/ui/celebration.py Bild-/GIF-Einblendung bei CELEBRATION_VALUES
bk/user_settings.py  UserSettingsStore: einstellungen.json laden/prüfen/speichern, FIELDS = im Menü änderbare Felder
bk/ui/settings_screen.py Einstellungsmenü (Bereiche → Einträge, [4]/[6] ändern, Enter: Eingabe/Tastenaufnahme)
bk/keys.py           Tastenbelegung (Qt-frei): Namen prüfen, Doppelbelegung, Legenden-Beschriftung
bk/autostart.py      Autostart: HKCU\...\Run „BK-Scoreboard“ (winreg), Zustand immer aus Registry, refresh() beim Start
bk/power.py          Herunterfahren: `shutdown /s /t 0 /f`, CREATE_NO_WINDOW, nur Windows (sonst nur beenden)
bk/media.py          Ton (winsound/Qt, fehlerfrei geschluckt) + Bildauswahl (1 Datei = immer, sonst zufällig)
bk/ui/widgets.py, theme.py, keymap.py
sounds/, bilder/     Ton- und Bilddateien neben der .exe (austauschbar, ohne Neubau)
vereinslogo/         Vereinslogo (beliebiges Bildformat), Auswahl im Einstellungsmenü
tests/               155 Tests (Logik, Speicherung, PDF, Cleanup, NumLock-Guard, Qt-Oberfläche offscreen)
```
Laufzeitordner: `data/` (active_game.json + .bak/.tmp, `archive/`, `corrupt/`), `results/` (PDF+JSON), `logs/`.

## Bedienung / fachliche Entscheidungen (mit dem Nutzer abgestimmt)
- **Plus ist voreingestellt**: Ziffer `0–7` allein = +n. `-` dann Ziffer = −n (gilt nur für EINEN Stoß,
  danach wieder Plus). `+` hebt gewähltes Minus auf. Wertebereich −7…+7, −0 = 0, 8/9 abgelehnt.
- **Keine Bestätigungstaste, kein Backspace.** Nur Nummernblock-Tasten (`NUMPAD_ONLY`), Autorepeat ignoriert.
- **Sperre** `INPUT_LOCK_SECONDS = 3` (oben in config.py) nach jeder Wertung, nicht blockierend (Timer/monotone Uhr).
  Ziffern gesperrt; `-`/`+` (Modusvorwahl) und `/` während der Sperre erlaubt.
- `/` = letzte Wertung komplett zurück (inkl. Speicherung), hebt Sperre auf, eigene Prellsperre 1 s.
- **Abbruch: `*` dann `-`** (statt Vorlage „[Num]&[-]“, weil NumLock-Taste mit Auto-NumLock kollidiert);
  jede andere Taste / 5 s Timeout = weiterspielen. Abbruch → Archiv, kein PDF.
- **Kein Spielername**, kein Spielerdaten-Fenster: Menüauswahl + Enter startet sofort.
  PDF-Name: `BK50_2026-09-29_15-42.pdf`. Alte Spielstände mit `player_name` laden weiterhin.
- Nach letztem Stoß läuft die Sperrzeit noch ab (Korrektur mit `/` möglich), dann automatisch:
  Ergebnis-JSON + PDF in `results/`, Archiv „beendet“, **Auswertung** im Hauptfenster (kein Extra-Fenster).
- Speichern nach JEDER Wertung/Rücknahme. Start: „Unterbrochene Partie gefunden“ →
  PARTIE FORTSETZEN / NEUE PARTIE (alte wird archiviert, nie gelöscht).
- „2x 50 Stoß“ und „Zweikampf“ wurden auf Wunsch des Nutzers entfernt. Dafür gibt es
  **„Billiard vs Fußball“** (Schlüssel BK25): 25 Stoß, keine Halbzeit, Raster 5 × 5.
- Anzeigen: Stoß-Anzahl (nächster Stoß / max), Punktestand, Prognose, Halbzeit (nach 50 bzw. 25),
  Aktueller Stoß (rot getönt bei Minus-Modus), Letzte Stöße (5), Minus (Summe Minuspunkte),
  Eingabe (BEREIT / MINUS / GESPERRT + Countdown), Spieldauer, 10er-Raster mit Reihensumme rechts (Spalte Σ,
  auch in der Auswertung). Stoß-Anzahl zeigt NUR die Nummer (kein „/ 100“), Aktueller Stoß ohne „+“
  (nur Minus mit Vorzeichen). Logo: „Version 3.0“, APP_VERSION 3.0.

## Einstellungsmenü (mit dem Nutzer abgestimmt)
- Hauptmenü: … Archiv, **Einstellungen**, Beenden, Beenden & Herunterfahren. Nur außerhalb einer Partie erreichbar.
- Jede Änderung: `store.set()` prüft (AppSettings.validate) → speichert sofort → `MainWindow.apply_settings()`
  übernimmt live (keymap, theme.apply_colors, Titelleiste, GameScreen.set_settings, Fenster, NumLock-Guard).
- Bereiche: Anzeige (Vollbild, Fenstergröße-Presets, Schriftgröße 80–130 % (`theme.FONT_SCALE` wirkt in
  `fitted_font` auf die Höhe, Breite bleibt Grenze; große Zahlen per `base_font` unverändert), Vereinsname per
  QInputDialog, Vereinslogo aus `vereinslogo/` (Hauptmenü unter dem BK-Bild, NICHT im PDF), Letzte Stöße,
  Felder „Letzte Stöße“/„Eingabe“ ausblendbar (`show_history`/`show_input_status`, Nachbar spannt dann 2 Spalten),
  Beim Windows-Start öffnen (NICHT in einstellungen.json, sondern Registry)), Design
  (Klassisch / eigene Primär- + Sekundärfarbe RGB), Eingabe, Tasten (Aufnahme), Töne (Halbzeit/Ende aus sounds/,
  Lautstärke, probehören), Bilder (bilder/plus, bilder/minus automatisch, einzelne aus = `disabled_images`),
  Drucken & PDF (Drucker-Auswahl mit Fallback Standard, PDF-Speicherort ohne Nachfrage, eindeutiger Name `_2`),
  Archiv & Aufräumen, Alles zurücksetzen (2× Enter).
- Neue Menü-Einstellung = Feld in AppSettings + Eintrag in `user_settings.FIELDS` + Item im settings_screen.
- Ton: Windows → MCI (`mciSendStringW`, wav+mp3+Lautstärke), Rückfall winsound (nur wav). KEIN QMediaPlayer:
  der hängt ohne Audiogerät die Ereignisschleife auf (unter Linux nachgewiesen). Linux/Test: QSoundEffect nur wav,
  nur wenn `QMediaDevices.audioOutputs()` nicht leer.

## Tastenbelegung (frei wählbar)
- `KEY_PLUS/MINUS/UNDO/ABORT` (Partie) und `KEY_UP/DOWN/LEFT/RIGHT/ENTER/BACK` (Menüs, Archiv, Auswertung, Wiedergabe)
  in `config.py`, je eine Liste; die erste Taste steht in der Legende. Ziffern 0–7 fest. Abbruch-Bestätigung = `KEY_MINUS`.
- `bk/ui/keymap.py` hält die aktive Belegung (`keymap.configure` im MainWindow); ALLE Legenden/Hinweise nutzen
  `keymap.label(...)` / `label_all(...)` – nie wieder feste Tastennamen in Texte schreiben.
- Ungültig/doppelt belegt → Fehlermeldung beim Start (wie jeder config.py-Fehler).

## Ton & Bilder (reine Zugabe, stören die Partie nie)
- Halbzeit (nach `halftime_after`): Ton `halftime_sound` + Halbzeit-Feld leuchtet 4 s gelb (auch ohne Tonausgabe).
  Partie-Ende: `end_sound`. +6/+7 (`CELEBRATION_VALUES`): `celebration_sound` (auch wenn Bilder aus). Fehlende Datei/kein Audiogerät → nur Logeintrag.
- +6/+7 (`CELEBRATION_VALUES`) → alle Bilder in `bilder/plus`; −6/−7 (`CELEBRATION_MINUS_VALUES`) → `bilder/minus`
  (leer = Plus-Bilder). Eine Datei = immer diese, mehrere = zufällig. `/` blendet es sofort aus.

## Auswertung & Archiv
- **Kein Extra-Fenster** (Nutzerwunsch): `ResultScreen` im Stack, alles auf einem Bildschirm ohne Scrollen
  (Referenz 1024×702 wie Menü/Archiv). Kennzahlen-Reihe, ScoreGrid (show_current=False), DistributionBox,
  Knöpfe **Als PDF speichern** (ohne Nachfrage in `pdf_save_dir`, Standard Dokumente) / **Drucken** (gewählter
  bzw. Standarddrucker, kein Dialog) / **Weiter** (Archiv: „Zurück“). `4`/`6`, Enter, `*`/Esc.
- **Das PDF bleibt unverändert** (Nutzer: „so wie es jetzt ist“) – Formatierung nur auf ausdrücklichen Wunsch ändern.
- PDF enthält „**Anzahl je Wertung**“ (wie oft −7…+7 gestoßen) und gleich dicke Tabellenlinien
  (`LINE_WIDTH`, alle Maße ganze Punkte). Druck mit 4 px/pt. Zählansicht-Raster nutzt kosmetische Stifte.
- Archiv (Hauptmenü): Liste aller Partien → AUSWERTUNG ANZEIGEN / WIEDERGABE (Stoß für Stoß,
  speichert nie etwas) / WEITERSPIELEN (nur abgebrochene/unterbrochene).
- **Aufräumen** beim Start + alle 6 h: `ARCHIVE_RETENTION_DAYS = 30`, `LOG_RETENTION_DAYS = 30`,
  `RESULTS_RETENTION_DAYS = 0` (PDFs nie löschen). Aktive Partie / aktuelles Log nie.

## Wichtige config.py-Schalter
KEY_*, SOUND_ENABLED, HALFTIME_SOUND, CELEBRATION_*, INPUT_LOCK_SECONDS, UNDO_LOCK_SECONDS, ABORT_CONFIRM_SECONDS, NUMPAD_ONLY, FULLSCREEN, HISTORY_LENGTH,
APP_TITLE, APP_VERSION, CLUB_NAME, AUTO_ENABLE_NUMLOCK, NUMLOCK_CHECK_SECONDS, AUTOSAVE_SECONDS,
GAME_MODES, SHOW_UNAVAILABLE_MODES, PDF_ROWS_PER_BLOCK/BLOCKS_PER_ROW, SHOW_REPORT_AFTER_GAME,
OPEN_PDF_AFTER_GAME, REPLAY_SECONDS_PER_STROKE, *_RETENTION_DAYS, Ordnerpfade (exe-aware).
Neue Einstellungen in `settings.py` immer mit `getattr(cfg, NAME, default)` lesen.

## Arbeitsweise
- Tests: `python main.py --selftest` (oder `python -m unittest discover -s tests -t .`);
  UI-Tests laufen mit `QT_QPA_PLATFORM=offscreen`. Vor Auslieferung immer alle Tests grün + `pyflakes`.
- .exe bauen: `build_exe.bat` (auf Windows). Nutzer-Update: nur `BK-Scoreboard.exe` + `_internal` ersetzen,
  `config.py`, `data`, `results` bleiben.
- Prioritäten des Nutzers: korrekte Funktion > zuverlässige Eingabe > Absturzsicherheit > Wertung >
  PDF > responsiv > Optik. Keine unnötigen Features, keine Maussteuerung im Spiel nötig.

## Offen / nicht verifiziert
- NumLock-Automatik, Drucken auf echtem Drucker, Ton (MCI), Druckerauswahl und die .exe wurden nur unter
  Linux/simuliert getestet –
  Rückmeldung vom Windows-PC des Nutzers steht aus.
