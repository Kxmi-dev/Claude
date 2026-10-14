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
config.py            ALLE Einstellungen (vom Nutzer editierbar)
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
bk/ui/menu_screen.py Hauptmenü: 100 Stoß, 50 Stoß, 2x 50 (gesperrt), Zweikampf (gesperrt), Archiv, Ende
bk/ui/game_screen.py Zählansicht + Wiedergabe-Modus
bk/ui/archive_screen.py  Archivliste
bk/ui/report_dialog.py   Statistik-Fenster (PDF-Ansicht, Speichern, Drucken, Schließen)
bk/ui/overlays.py    Abfrage-Karten (Fortsetzen, Abbruch, Archiv-Auswahl, Fehler)
bk/ui/celebration.py Bild-/GIF-Einblendung bei CELEBRATION_VALUES
bk/keys.py           Tastenbelegung (Qt-frei): Namen prüfen, Doppelbelegung, Legenden-Beschriftung
bk/media.py          Ton (winsound/Qt, fehlerfrei geschluckt) + Bildauswahl (1 Datei = immer, sonst zufällig)
bk/ui/widgets.py, theme.py, keymap.py
sounds/, bilder/     Ton- und Bilddateien neben der .exe (austauschbar, ohne Neubau)
tests/               122 Tests (Logik, Speicherung, PDF, Cleanup, NumLock-Guard, Qt-Oberfläche offscreen)
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
  Ergebnis-JSON + PDF in `results/`, Archiv „beendet“, **Statistik-Fenster** öffnet sich.
- Speichern nach JEDER Wertung/Rücknahme. Start: „Unterbrochene Partie gefunden“ →
  PARTIE FORTSETZEN / NEUE PARTIE (alte wird archiviert, nie gelöscht).
- **2x 50 Stoß und Zweikampf** sind im BKV-Regelwerk nicht definiert → im Menü „in Vorbereitung“,
  nicht startbar. Erst freischalten, wenn der Nutzer die Regeln liefert (keine Regeln erfinden!).
- Anzeigen: Stoß-Anzahl (nächster Stoß / max), Punktestand, Prognose, Halbzeit (nach 50 bzw. 25),
  Aktueller Stoß (rot getönt bei Minus-Modus), Letzte Stöße (5), Minus (Summe Minuspunkte),
  Eingabe (BEREIT / MINUS / GESPERRT + Countdown), Spieldauer, 10er-Raster.

## Tastenbelegung (frei wählbar)
- `KEY_PLUS/MINUS/UNDO/ABORT` (Partie) und `KEY_UP/DOWN/LEFT/RIGHT/ENTER/BACK` (Menüs, Archiv, Statistik, Wiedergabe)
  in `config.py`, je eine Liste; die erste Taste steht in der Legende. Ziffern 0–7 fest. Abbruch-Bestätigung = `KEY_MINUS`.
- `bk/ui/keymap.py` hält die aktive Belegung (`keymap.configure` im MainWindow); ALLE Legenden/Hinweise nutzen
  `keymap.label(...)` / `label_all(...)` – nie wieder feste Tastennamen in Texte schreiben.
- Ungültig/doppelt belegt → Fehlermeldung beim Start (wie jeder config.py-Fehler).

## Ton & Bilder (reine Zugabe, stören die Partie nie)
- Halbzeit (nach `halftime_after`): Ton `HALFTIME_SOUND` (WAV in `sounds/`) + Halbzeit-Feld leuchtet 4 s gelb
  (geht auch ohne Tonausgabe). Fehlende Datei/kein Audiogerät → nur Logeintrag.
- Minus: `CELEBRATION_MINUS_VALUES` (Standard −6/−7) → `CELEBRATION_MINUS_IMAGES` (leer = Plus-Liste).
- Wertung in `CELEBRATION_VALUES` (Standard +6/+7) → Bild/GIF aus `CELEBRATION_IMAGES` (Ordner `bilder/`),
  eine Datei = immer diese, mehrere = zufällig. `/` blendet es sofort aus. Ton/Bilder sind unter Windows
  (winsound, GIF/Bild in der .exe) noch nicht auf dem echten PC geprüft.

## Statistik-Fenster & Archiv
- Statistik-Fenster zeigt den Bericht wie im PDF: Knöpfe **Als PDF speichern** (Dialog, Vorschlag Dokumente-Ordner),
  **Drucken** (sofort auf **Windows-Standarddrucker, kein Druckdialog**; ohne Standarddrucker Hinweistext),
  **Schließen**. Bedienung `4`/`6`, Enter, `8`/`2` blättern, `*`/Esc.
- PDF enthält „**Anzahl je Wertung**“ (wie oft −7…+7 gestoßen) und gleich dicke Tabellenlinien
  (`LINE_WIDTH`, alle Maße ganze Punkte). Bildschirmanzeige: eigene PDF-Variante über
  `screen_line_options(scale)`, Maßstäbe in 0,5-Schritten, `PathAliased` → jede Linie exakt 1 px.
  Druck mit 4 px/pt. Zählansicht-Raster nutzt kosmetische Stifte.
- Archiv (Hauptmenü): Liste aller Partien → STATISTIK ANZEIGEN / WIEDERGABE (Stoß für Stoß,
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
- NumLock-Automatik, Drucken auf echtem Drucker und die .exe wurden nur unter Linux/simuliert getestet –
  Rückmeldung vom Windows-PC des Nutzers steht aus.
- Regeln für „2x 50 Stoß“ und „Zweikampf“ fehlen noch.
