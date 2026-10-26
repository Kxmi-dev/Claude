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
build_exe.py/.bat    Selftest (abschaltbar: --skip-test / build_exe_ohne_test.bat) + PyInstaller → dist\BK-Scoreboard\ (bricht ab, wenn dort Spieldaten liegen)
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
                     Beenden, Beenden & Herunterfahren (ROTER Knopf, `danger=True`; 2× Enter innerhalb 5 s)
                     Rechts `BrandPanel` (widgets): Vereinslogo im weißen Kasten, gezeichneter grüner Billardtisch
                     mit Mini-Zähltafel/Kegeln/3 Kugeln, „BK-Scoreboard / Version {APP_VERSION}“ (3.0) und darunter „powered by Kimi&AP“ (Nutzerwunsch).
                     Vereinslogo zusätzlich klein rechts in der Titelleiste (`TitleBar.set_logo`).
bk/ui/game_screen.py Zählansicht + Wiedergabe-Modus
bk/ui/archive_screen.py  Archivliste
bk/ui/result_screen.py   Auswertung „Endergebnis“ im Hauptfenster (Kennzahlen, Spielanalyse, Statistik, Knöpfe, Sperre)
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
tests/               165 Tests (Logik, Speicherung, PDF, Cleanup, NumLock-Guard, Qt-Oberfläche offscreen)
```
Laufzeitordner: `data/` (active_game.json + .bak/.tmp, `archive/`, `corrupt/`), `results/` (PDF+JSON), `logs/`.

## Bedienung / fachliche Entscheidungen (mit dem Nutzer abgestimmt)
- **Plus ist voreingestellt**: Ziffer `0–7` allein = +n. `-` dann Ziffer = −n (gilt nur für EINEN Stoß,
  danach wieder Plus). `+` hebt gewähltes Minus auf. Wertebereich −7…+7, −0 = 0, 8/9 abgelehnt.
- **Keine Bestätigungstaste, kein Backspace.** Nur Nummernblock-Tasten (`NUMPAD_ONLY`), Autorepeat ignoriert.
- **Sperre** `INPUT_LOCK_SECONDS = 3` (oben in config.py) nach jeder Wertung, nicht blockierend (Timer/monotone Uhr).
  Ziffern gesperrt; `-`/`+` (Modusvorwahl) und `/` während der Sperre erlaubt.
- `/` = Korrekturfeld (Nutzerwunsch): NUR der letzte Stoß ist änderbar. Kästchen im Raster kräftig gelb, Overlay
  „Korrektur Stoß N“ mit „Alte Punktzahl“ / „Neue Punktzahl“; neue Zahl eintippen (`-`/`+` Vorzeichen, Ziffer
  überschreibt), `Enter` übernimmt (`Game.replace_last`, Speicherung, Sperre aufgehoben), `*`/`Esc` bricht ab,
  kein Zeitlimit. Controller: `correction_input=True`, Aktionen CORRECTION_*; Signal `correction_prompt`.
- `Enter` in der Partie (GameKey.ENTER über map_menu_key): während GESPERRT → sofort BEREIT (`enter_skips_lock`,
  Einstellungen → Eingabe); nach dem letzten Stoß → Partie abschließen + Auswertung.
- **Abbruch: `*` dann `-`** (statt Vorlage „[Num]&[-]“, weil NumLock-Taste mit Auto-NumLock kollidiert);
  jede andere Taste / 5 s Timeout = weiterspielen. Abbruch → Archiv, kein PDF.
- **Kein Spielername**, kein Spielerdaten-Fenster: Menüauswahl + Enter startet sofort.
  PDF-Name: `BK50_2026-09-29_15-42.pdf`. Alte Spielstände mit `player_name` laden weiterhin.
- Nach letztem Stoß bleibt die Zählansicht stehen („ENDE“, Korrektur weiter möglich); ERST `Enter` (Nutzerwunsch,
  nicht automatisch): Ergebnis-JSON + PDF in `results/`, Archiv „beendet“, **Auswertung** im Hauptfenster.
- Speichern nach JEDER Wertung/Rücknahme. Start: „Unterbrochene Partie gefunden“ →
  PARTIE FORTSETZEN / NEUE PARTIE (alte wird archiviert, nie gelöscht).
- „2x 50 Stoß“ und „Zweikampf“ wurden auf Wunsch des Nutzers entfernt. Dafür gibt es
  **„Billiard vs Fußball“** (Schlüssel BK25): 25 Stoß, keine Halbzeit, Raster 5 × 5.
- Anzeigen: Stoß-Anzahl (gespielte Stöße, Start 0), Punktestand, Prognose, Halbzeit (nach 50 bzw. 25),
  Aktueller Stoß (rot getönt bei Minus-Modus), Letzte Stöße (5), Minus (Summe Minuspunkte),
  Eingabe (BEREIT / MINUS / GESPERRT + Countdown / KORREKTUR / ENDE), Spieldauer, 10er-Raster: Kästchen zeigen
  den GESAMTSTAND nach dem Stoß (3, 6, 9; `grid_running_total`, umschaltbar auf Einzelstoß), Leerstoß = „X“,
  Minus-Stoß rot; rechts Punkte je Reihe fett schwarz OHNE Kästchen/weißen Hintergrund (direkt auf Grau). Halbzeit-Feld bleibt ab Halbzeit gelb.
  Aktueller Stoß ohne „Stoß N“-Untertext (dafür Prognose/Halbzeit größer). Stoß-Anzahl = Zahl der GESPIELTEN Stöße (Start 0, kein „/ 100“), Aktueller Stoß ohne „+“
  (nur Minus mit Vorzeichen). Logo: „Version 3.0“, APP_VERSION 3.0.

## Einstellungsmenü (mit dem Nutzer abgestimmt)
- Hauptmenü: … Archiv, **Einstellungen**, Beenden, Beenden & Herunterfahren. Nur außerhalb einer Partie erreichbar.
- Jede Änderung: `store.set()` prüft (AppSettings.validate) → speichert sofort → `MainWindow.apply_settings()`
  übernimmt live (keymap, theme.apply_colors, Titelleiste, GameScreen.set_settings, Fenster, NumLock-Guard).
- Bereiche: Anzeige (Vollbild, Fenstergröße-Presets, Schriftgröße 80–130 % (`theme.FONT_SCALE` wirkt in
  `fitted_font` auf die Höhe, Breite bleibt Grenze; große Zahlen per `base_font` unverändert), Vereinsname per
  QInputDialog, Vereinslogo aus `vereinslogo/` (Hauptmenü rechts groß, unverändert angezeigt – automatisches Freistellen
  wurde auf Wunsch WIEDER ENTFERNT, der Verein passt das Logo selbst an; BK-Scoreboard-Bild im Menü UND im PDF ENTFERNT, ohne Logo Menü mittig; im PDF-Kopf nur das Vereinslogo,
  max. 74×84 pt, Transparenz → weiß), Letzte Stöße,
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
- Halbzeit (nach `halftime_after`): Ton `halftime_sound`; Halbzeit-Feld bleibt ab dann gelb (auch ohne Tonausgabe).
  Partie-Ende: `end_sound`. +6/+7 (`CELEBRATION_VALUES`): `celebration_sound` (auch wenn Bilder aus). Fehlende Datei/kein Audiogerät → nur Logeintrag.
- +6/+7 (`CELEBRATION_VALUES`) → alle Bilder in `bilder/plus`; −6/−7 (`CELEBRATION_MINUS_VALUES`) → `bilder/minus`
  (leer = Plus-Bilder). Eine Datei = immer diese, mehrere = zufällig. Bestätigte Korrektur blendet es sofort aus.
- Hauptmenü-Lesbarkeit: Knopfschrift fett, dunkel `BUTTON_TEXT #333333`, größer; „Version …“ fett schwarz.

## Auswertung & Archiv
- **Kein Extra-Fenster** (Nutzerwunsch): `ResultScreen` im Stack, alles auf einem Bildschirm ohne Scrollen
  (Referenz 1024×702). Aufbau nach Nutzer-Foto („Endergebnis“): Halbzeit · Ergebnis · Spielzeit/Minus · LogoBox;
  Spielanalyse 1er–7er/Leer/Minus (Anzahl); Statistik 3 Spalten (`StatsTable`, gemeinsame große Schrift);
  Knöpfe Partie speichern / Partie drucken / Neue Partie (nur nach Partie, gleiche Spielart) / Hauptmenü
  (Archiv: Zurück) + **Tabelle ansehen** (Raster statt Kennzahlen, `*` zurück zur Auswertung). „Partie bearbeiten“ bewusst weggelassen.
- **Sperre nach Partie-Ende** `result_lock_seconds` (Standard 5, Einstellungen → Eingabe): Enter/Back/Klick wirkungslos.
- **Korrekturen** werden in `GameState.corrections` gezählt (`Game.undo` / `Game.replace_last`, nur bei geändertem Wert); alte Spielstände ohne Feld → None → „–“.
- **Das PDF bleibt unverändert** (Nutzer: „so wie es jetzt ist“) – Formatierung nur auf ausdrücklichen Wunsch ändern.
  Einzige gewünschte Änderung bisher: Logo oben rechts = Vereinslogo statt BK-Scoreboard-Bild.
- PDF enthält „**Anzahl je Wertung**“ (wie oft −7…+7 gestoßen) und gleich dicke Tabellenlinien
  (`LINE_WIDTH`, alle Maße ganze Punkte). Druck mit 4 px/pt. Zählansicht-Raster nutzt kosmetische Stifte.
- Archiv (Hauptmenü): oben grün „Letzte abgeschlossene Partien“ (3, nur beendet), darunter alle Partien;
  Auswahl läuft mit 8/2 durch beide Listen (Start oben) → AUSWERTUNG ANZEIGEN / WIEDERGABE (Stoß für Stoß,
  speichert nie etwas) / WEITERSPIELEN (nur abgebrochene/unterbrochene).
- **Aufräumen** beim Start + alle 6 h: `ARCHIVE_RETENTION_DAYS = 30`, `LOG_RETENTION_DAYS = 30`,
  `RESULTS_RETENTION_DAYS = 0` (PDFs nie löschen). Aktive Partie / aktuelles Log nie.

## Wichtige config.py-Schalter
KEY_*, SOUND_ENABLED, HALFTIME_SOUND, CELEBRATION_*, INPUT_LOCK_SECONDS, UNDO_LOCK_SECONDS, ABORT_CONFIRM_SECONDS, NUMPAD_ONLY, FULLSCREEN, HISTORY_LENGTH,
STAY_ON_TOP (Fenster immer oben; `_open_external` setzt es aus, bis das Scoreboard wieder aktiv ist),
HIDE_MOUSE_CURSOR (Override-Cursor BlankCursor, beim Schließen zurück), APP_TITLE, APP_VERSION, CLUB_NAME, AUTO_ENABLE_NUMLOCK, NUMLOCK_CHECK_SECONDS, AUTOSAVE_SECONDS,
GAME_MODES, SHOW_UNAVAILABLE_MODES, PDF_ROWS_PER_BLOCK/BLOCKS_PER_ROW, SHOW_REPORT_AFTER_GAME,
OPEN_PDF_AFTER_GAME, REPLAY_SECONDS_PER_STROKE, *_RETENTION_DAYS, Ordnerpfade (exe-aware).
Neue Einstellungen in `settings.py` immer mit `getattr(cfg, NAME, default)` lesen.

## Arbeitsweise
- **WICHTIG (ausdrücklicher Nutzerwunsch): Bei JEDER Änderung zuerst schreiben, WAS gebaut werden soll
  (kurzer Plan), und erst nach dem „ja“ des Nutzers umsetzen.** Auch bei kleinen Wünschen nie direkt loslegen.
- **Nie einen Windows-/GitHub-Build starten** (Nutzerwunsch) – der Nutzer baut selbst mit `build_exe.bat`.
- **Nicht die ganze Testsuite laufen lassen** (Nutzerwunsch) – nur die Tests, die zu den geänderten Stellen gehören (z. B. einzelne Testklassen/-methoden).
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
