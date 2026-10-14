# BK-Scoreboard 2.0 – Digitale Zähltafel für Kegelbillard

Elektronische Zähltafel und Spielverwaltung für das **reale** Kegelbillardspiel
(BKV-Disziplinen **BK 50** und **BK 100**). Es gibt keine Simulation, keine Kugeln und
keinen virtuellen Tisch – der Bediener gibt jede Wertung am Nummernblock ein, das
Programm übernimmt den Rest:

**Wertung → Punktestand → Stoßzähler → Speicherung → Sperrzeit → nächste Eingabe**

Bei einem Fehler: **`/`** nimmt die letzte Wertung vollständig zurück.
Bei einem Absturz: **Programm neu starten → Partie fortsetzen.**
Nach dem letzten Stoß: **automatischer Abschluss mit druckfertigem PDF und Statistik-Fenster.**
Im **Archiv**: jede frühere Partie ansehen, drucken, Stoß für Stoß wiedergeben oder weiterspielen.

---

## 1. Installation (Windows)

> **Ohne Python auf dem Vereins-PC?** Dann einmalig auf einem PC mit Python die
> `.exe` erstellen (Abschnitt 10) und nur den fertigen Programmordner weitergeben.

**Voraussetzung:** Python 3.10 oder neuer (empfohlen 3.12) von <https://www.python.org>.
Bei der Python-Installation **„Add python.exe to PATH“** anhaken.

Den Ordner `bk_scoreboard` an einen **beschreibbaren** Ort kopieren, z. B.
`C:\BK-Scoreboard` oder in die Dokumente – **nicht** nach `C:\Programme`, denn das
Programm legt dort seine Ordner `data`, `results` und `logs` an.

**Variante A – per Doppelklick (empfohlen):**
`install_windows.bat` ausführen. Das legt eine eigene Python-Umgebung (`.venv`) an,
installiert die Pakete und führt den Selbsttest aus.

**Variante B – manuell in der Eingabeaufforderung:**

```
cd C:\BK-Scoreboard
python -m pip install -r requirements.txt
```

| Paket      | Zweck                                                   |
|------------|---------------------------------------------------------|
| PySide6    | Oberfläche (Qt 6): Vollbild, Layouts, Tastatur, Timer   |
| reportlab  | PDF-Spielbericht (installiert Pillow automatisch mit)   |
| *pypdf*    | *optional – nur für erweiterte Inhaltsprüfung der PDF-Tests* |

## 2. Start

* Doppelklick auf **`start_bk_scoreboard.bat`** (startet im Vollbild, ohne Konsolenfenster)
* oder in der Eingabeaufforderung: `python main.py`

| Aufruf                              | Wirkung                                             |
|-------------------------------------|-----------------------------------------------------|
| `python main.py`                    | Normalbetrieb im Vollbild                           |
| `python main.py --windowed`         | im Fenster (zum Einrichten / Testen)                |
| `python main.py --selftest`         | Testmodus: alle automatischen Tests ausführen       |
| `python main.py --pdf results\X.json` | PDF aus einer Ergebnisdatei neu erzeugen          |

Beenden: im Hauptmenü **„Ende“**. Wird das Programm während einer Partie geschlossen
(z. B. Alt+F4), wird der Spielstand gesichert und beim nächsten Start angeboten.

Tipp für den Vereins-PC: Eine Verknüpfung auf `start_bk_scoreboard.bat` in den
Autostart-Ordner legen (Windows-Taste + R → `shell:startup`).

## 3. Bedienung

### Hauptmenü und Abfragen
| Taste                        | Funktion      |
|------------------------------|---------------|
| `8` / `2` (oder Pfeiltasten) | Auswahl hoch / runter |
| `Enter`                      | bestätigen    |

Die gewählte Spielart startet mit **`Enter`** sofort – ein Spielername wird nicht benötigt.
Datum und Uhrzeit werden automatisch erfasst und stehen im PDF.

### Während der Partie – nur Nummernblock
| Eingabe            | Ergebnis                                                  |
|--------------------|-----------------------------------------------------------|
| `0`–`7`            | Plus-Wertung +0 … +7 (z. B. `5` → **+5**) – Plus ist immer voreingestellt |
| `-` dann `0`–`7`   | Minus-Wertung −0 … −7 (z. B. `-` `3` → **−3**; −0 zählt als 0) |
| `+`                | hebt einen versehentlich gewählten Minus-Modus wieder auf  |
| `/`                | letzte Wertung vollständig zurücknehmen (mehrfach möglich) |
| `*` dann `-`       | Partie abbrechen (jede andere Taste = weiterspielen)       |

* Es gibt **keine Bestätigungstaste** und **kein Backspace**: Die Ziffer schließt die Eingabe ab.
* Nach jeder Wertung ist die Eingabe **3 Sekunden gesperrt** („GESPERRT“ mit Countdown,
  danach „BEREIT“). `/` bleibt während der Sperre erlaubt, damit ein Fehler sofort
  korrigiert werden kann.
* **Minus gilt immer nur für den nächsten Stoß** – danach steht der Modus automatisch
  wieder auf Plus. Ein gewähltes Minus erkennt man am rot hinterlegten Feld
  „Aktueller Stoß“ und an „MINUS“ im Feld „Eingabe“.
* `-` darf schon während der Sperrzeit gedrückt werden und gilt dann für den nächsten Stoß.
  Ziffern bleiben während der Sperrzeit wirkungslos.
* `8` und `9` werden abgelehnt. Gedrückt gehaltene Tasten (Tastenwiederholung) werden nie
  mehrfach gezählt.
* Hinweise und Fehlermeldungen erscheinen kurz in der Fußleiste.

### Anzeigen der Zählansicht
| Anzeige         | Bedeutung |
|-----------------|-----------|
| Stoß - Anzahl   | Nummer des nächsten Stoßes / Gesamtzahl (z. B. `26 / 100`) |
| Punktestand     | aktueller Gesamtstand |
| Prognose        | aktueller Schnitt hochgerechnet auf die volle Stoßzahl |
| Halbzeit        | Stand nach Stoß 50 (BK 100) bzw. 25 (BK 50) |
| Aktueller Stoß  | letzte Wertung groß; nach `-` rot hinterlegt mit „Minus: Zahl 0 – 7“ |
| Letzte Stöße    | die letzten fünf Wertungen („Stoß 47  +1“) |
| Minus           | Summe aller Minuspunkte |
| Eingabe         | BEREIT (Plus) / MINUS / GESPERRT mit Countdown-Balken |
| Spieldauer      | Laufzeit der Partie |
| Stoß-Raster     | ein Feld pro Stoß; **blauer Rahmen** = nächster Stoß, **gelb** = Halbzeit und letzte 5 Stöße, kleine Zahl = Zwischenstand |

### Partieende und Statistik-Fenster
Nach dem letzten Stoß läuft noch die normale Sperrzeit ab – in dieser Zeit kann ein
Tippfehler beim letzten Stoß mit `/` korrigiert werden. Danach wird die Partie
automatisch abgeschlossen: Ergebnis speichern, **PDF automatisch in `results` ablegen**,
Spielstand archivieren – und das **Statistik-Fenster** öffnet sich.

Das Statistik-Fenster zeigt den Spielbericht genau so, wie er im PDF steht
(„ENDRESULTAT“, Kennzahlen, **Anzahl je Wertung** – wie oft −7 … +7 gestoßen wurde –
und die komplette Stoßliste) und bietet drei Knöpfe:

| Knopf | Wirkung |
|-------|---------|
| **Als PDF speichern** | Speichern-Dialog, z. B. auf einen USB-Stick (vorgeschlagen: Ordner „Dokumente“, weil das PDF in `results` schon automatisch liegt) |
| **Drucken** | druckt sofort auf dem **Windows-Standarddrucker** – ohne Druckdialog |
| **Schließen** | zurück (nach einer Partie ins Hauptmenü, sonst ins Archiv) |

Bedienung im Fenster: `4` / `6` Knopf wählen, `Enter` ausführen, `8` / `2` im Bericht
blättern, `*` oder `Esc` schließen – oder einfach mit der Maus.

### Archiv
Hauptmenü → **Archiv** zeigt alle gespeicherten Partien (neueste oben) mit Datum, Uhrzeit,
Spielart, Status (beendet / abgebrochen / unterbrochen), Stoßzahl und Ergebnis.
`8` / `2` wählen, `Enter` öffnet die Partie, `*` oder `Esc` führt zurück. Zur Auswahl stehen:

* **STATISTIK ANZEIGEN** – das Statistik-Fenster (Speichern, Drucken, Schließen)
* **WIEDERGABE** – die Partie läuft Stoß für Stoß noch einmal auf der Zähltafel ab
  (`Enter` Pause/Weiter, `+` / `−` schneller/langsamer, `*` oder `Esc` beenden;
  am Ende öffnet `Enter` die Statistik). Eine Wiedergabe verändert und speichert nichts.
* **WEITERSPIELEN** – nur bei abgebrochenen oder unterbrochenen Partien: Die Partie wird
  wieder zur laufenden Partie und genau dort fortgesetzt, wo sie aufgehört hat.

## 4. Konfiguration (`config.py`)

Alle Einstellungen stehen zentral in `config.py`. Nach einer Änderung das Programm neu starten.

| Einstellung | Standard | Bedeutung |
|-------------|----------|-----------|
| `INPUT_LOCK_SECONDS` | `3` | Sperrzeit nach jeder Wertung in Sekunden (0 = keine Sperre) |
| `UNDO_LOCK_SECONDS` | `1.0` | kurze Sperre nach `/`, damit ein prellender Tastendruck nicht zwei Wertungen zurücknimmt |
| `ABORT_CONFIRM_SECONDS` | `5` | so lange wartet die Abbruch-Frage auf `-` |
| `NUMPAD_ONLY` | `True` | `True` = im Spiel zählen nur Nummernblock-Tasten; `False` = auch die normale Tastatur |
| `FULLSCREEN` | `True` | Start im Vollbild |
| `HISTORY_LENGTH` | `5` | Einträge unter „Letzte Stöße“ |
| `APP_TITLE`, `APP_VERSION`, `CLUB_NAME` | | Texte in Titelleiste und PDF |
| `SOUND_ENABLED`, `HALFTIME_SOUND` | `True`, `"halbzeit.wav"` | Ton zur Halbzeit (WAV im Ordner `sounds`). Leerer Name = kein Ton. Ohne Tonausgabe läuft alles weiter, das Halbzeit-Feld leuchtet zusätzlich ca. 4 s gelb auf |
| `CELEBRATION_ENABLED`, `CELEBRATION_VALUES` | `True`, `(6, 7)` | bei diesen Wertungen erscheint ein Bild/GIF (`(6, 7, -6, -7)` = auch bei Minus) |
| `CELEBRATION_IMAGES` | `[]` | Liste der Dateien im Ordner `bilder`. Eine Datei = immer diese, mehrere = zufällig (nie zweimal hintereinander dieselbe). Leer = keine Bilder |
| `CELEBRATION_SECONDS` | `3` | Anzeigedauer des Bildes; verschwindet auch bei `/` und der nächsten Wertung |
| `AUTO_ENABLE_NUMLOCK` | `True` | NumLock prüfen und automatisch einschalten (`False` = nur warnen) |
| `NUMLOCK_CHECK_SECONDS` | `2` | Prüfintervall für NumLock |
| `AUTOSAVE_SECONDS` | `15` | zusätzliche Sicherung der Spieldauer (Wertungen werden **immer sofort** gespeichert) |
| `GAME_MODES` | BK 100, BK 50, … | Spielarten (siehe unten) |
| `SHOW_UNAVAILABLE_MODES` | `True` | nicht freigeschaltete Spielarten im Menü anzeigen |
| `PDF_ROWS_PER_BLOCK`, `PDF_BLOCKS_PER_ROW` | `25`, `4` | Aufteilung der Stoßliste im PDF (4 × 25 = 100 Stöße auf einer Seite) |
| `SHOW_REPORT_AFTER_GAME` | `True` | nach jeder Partie das Statistik-Fenster öffnen (das PDF wird in jedem Fall gespeichert) |
| `OPEN_PDF_AFTER_GAME` | `False` | PDF zusätzlich im PDF-Programm von Windows öffnen |
| `REPLAY_SECONDS_PER_STROKE` | `0.8` | Tempo der Wiedergabe aus dem Archiv (Sekunden pro Stoß) |
| `ARCHIVE_RETENTION_DAYS` | `30` | Archiv (`data\archive`) und beschädigte Spielstände (`data\corrupt`) nach so vielen Tagen löschen (0 = nie) |
| `LOG_RETENTION_DAYS` | `30` | Protokolldateien (`logs`) nach so vielen Tagen löschen (0 = nie) |
| `RESULTS_RETENTION_DAYS` | `0` | PDFs/Ergebnisse (`results`) nach so vielen Tagen löschen – Standard 0 = nie |
| `DATA_DIR`, `RESULTS_DIR`, `LOGS_DIR`, `ASSETS_DIR` | Programmordner | Speicherorte |

**Neue Spielart hinzufügen** – eine Zeile in `GAME_MODES`, sonst nichts:

```python
GameMode(key="BK200", title="200 Stoß", strokes=200, halftime_after=100,
         grid_columns=20, highlight_last=5),
```

Logo und Symbol liegen in `assets/logo.png` und `assets/icon.png` (aus der Designvorlage
ausgeschnitten). Wer das Original-Logo in höherer Auflösung hat, ersetzt einfach die Datei.

## 5. Absturzsicherheit und Dateien

```
bk_scoreboard/
├── data/
│   ├── active_game.json        aktueller Spielstand
│   ├── active_game.json.bak    vorheriger Stand (eine Wertung älter)
│   ├── archive/                beendete, abgebrochene und verworfene Partien
│   └── corrupt/                unlesbare Spielstände (werden nie gelöscht)
├── results/                    PDF + JSON jeder beendeten Partie
└── logs/                       application.log (rotierend), crash.log
```

**Automatisches Aufräumen:** Beim Programmstart und danach alle 6 Stunden werden Dateien
gelöscht, die älter sind als eingestellt – Archiv und Logs standardmäßig nach **30 Tagen**.
Die PDFs in `results` bleiben erhalten (`RESULTS_RETENTION_DAYS = 0`); ein Spielbericht ist
nur noch rund 100 KB groß. Die laufende Partie wird nie gelöscht. Die Log-Datei beginnt
jeden Tag neu (`application.log`, ältere Tage als `application.log.JJJJ-MM-TT`).

**Speichern nach jeder Wertung und jeder Rücknahme** – atomar:
1. neuen Stand in `active_game.json.tmp` schreiben, `flush` + `fsync`
2. bisherigen Stand nach `.bak` kopieren
3. `.tmp` per `os.replace` atomar zur Hauptdatei machen

Jede Datei trägt eine SHA-256-Prüfsumme und eine Revisionsnummer. Beim Start wird unter
Hauptdatei, `.tmp` und `.bak` der neueste **gültige** Stand gewählt. Ein Absturz in jedem
Schritt hinterlässt immer mindestens eine vollständige Datei.

**Beim Programmstart:**
* laufende Partie gefunden → **„Unterbrochene Partie gefunden“** mit
  **PARTIE FORTSETZEN** / **NEUE PARTIE** (die alte Partie wird dabei archiviert, nie gelöscht)
* Stand stammt aus der Sicherungskopie → deutlicher Hinweis „bitte letzten Stoß prüfen“
* alle Dateien beschädigt → Meldung, Dateien werden nach `data/corrupt` verschoben
* Partie war beendet, aber PDF/Archiv fehlten (Absturz beim Abschluss) → Abschluss wird automatisch nachgeholt

Fortgesetzt wird exakt mit Spielart, Stoßzahl, Punktestand, Stoßnummer,
vollständiger Wertungsliste und bisheriger Spieldauer.

**PDF-Dateiname:** `BK50_2026-09-29_15-42.pdf` (Spielart, Datum und Uhrzeit des Beginns).
Existiert die Datei schon, wird `_2` angehängt.
Schlägt die PDF-Erstellung fehl, liegt das Ergebnis trotzdem als JSON in `results/`
und kann mit `python main.py --pdf results\DATEI.json` nachträglich erzeugt werden.

## 6. Regelgrundlage und getroffene Entscheidungen

Grundlage: BKV-Regeln, insbesondere §3 und §4
(<https://billardregel.de/kegel/billardkegel-bkv/>).

* **BK 50 / BK 100:** Jeder Spieler absolviert 50 bzw. 100 Stoß hintereinander; die Partie
  endet mit dem letzten Stoß (§3 (1), (7)). Genau so zählt das Programm – kein Stoß mehr, keiner weniger.
* **Wertung:** Punkte (Kegel, Mittelkegel allein 2, Karambolage, Passage) und Minuspunkte
  (Fehlerkatalog §4) ermittelt der Bediener bzw. Schiedsrichter; das Programm erfasst die
  Wertung im vorgegebenen Bereich −7 … +7. Leerstoß = 0.
* **Keine Pause** in der Partie (§3 (4) 8) – „Halbzeit“ ist daher nur der Zwischenstand.
* **Vorzeitig beendete Partien** werden laut §3 (1) mit Null gewertet, bei nicht
  vorhersehbaren Gründen mit dem erzielten Ergebnis. Das entscheidet die Wettkampfleitung –
  das Programm archiviert abgebrochene Partien mit allen Wertungen, erstellt aber kein PDF.
* **„2x 50 Stoß“ und „Zweikampf“** stehen in der Designvorlage, sind im BKV-Regelwerk aber
  nicht definiert. Um keine Regeln zu erfinden, werden sie im Menü als „in Vorbereitung“
  angezeigt und sind nicht startbar. Sobald die Regeln feststehen, können sie ergänzt werden.

**Bewusste Abweichungen von Vorlage und Spezifikation:**
* **Kein Spielername und kein Spielerdaten-Fenster** (auf Wunsch des Vereins): Die Partie
  startet direkt aus dem Hauptmenü. Ältere Spielstände mit Namen lassen sich weiter fortsetzen.
* **Plus ist voreingestellt:** Eine Ziffer allein ergibt eine Plus-Wertung; Minus wird mit `-`
  für genau einen Stoß gewählt.
* **Partie-Abbruch mit `*` und dann `-`** statt „[Num] & [-]“: Die NumLock-Taste als Befehl
  würde mit der automatischen NumLock-Aktivierung kollidieren (ein Druck schaltet NumLock
  aus, die Ziffern würden dann nicht mehr funktionieren).
* Zusätzlich zur Vorlage zeigt die Zählansicht „Letzte Stöße“ und „Eingabe“ (Sperrstatus),
  weil beides in der Spezifikation gefordert ist.

## 7. Architektur

```
bk_scoreboard/
├── main.py                  Einstieg: Kommandozeile, Logging, Einzelinstanz-Sperre, Fenster
├── config.py                ALLE Einstellungen
├── requirements.txt
├── install_windows.bat      Installation per Doppelklick
├── start_bk_scoreboard.bat  Start per Doppelklick
├── build_exe.bat            .exe erstellen per Doppelklick
├── build_exe.py             Build-Skript (PyInstaller, Selbsttest, Datenschutz)
├── assets/                  logo.png, icon.png, app.ico (Programmsymbol der .exe)
├── docs/                    Screenshots und Beispiel-Spielbericht (PDF)
├── bk/                      Fachlogik (ohne Oberfläche, vollständig testbar)
│   ├── models.py            GameMode, GameState, GameStatus (+ strenge Prüfung beim Laden)
│   ├── game.py              Spiel-Engine: Wertung, Rücknahme, Stoßzähler, Kennzahlen, Abschluss
│   ├── input_logic.py       Eingabe-Zustandsautomat (Plus/Minus, Ziffer, Sperre, /, Abbruch)
│   ├── storage.py           atomisches Speichern, Wiederherstellung, Archiv, Ergebnisse
│   ├── pdf_report.py        PDF-Spielbericht
│   ├── numlock.py           NumLock prüfen/einschalten (Windows, SendInput)
│   ├── maintenance.py       automatisches Löschen alter Archiv- und Log-Dateien
│   ├── settings.py          unveränderliche Laufzeit-Einstellungen aus config.py
│   ├── logging_setup.py     logs/application.log, crash.log, Fehler-Hooks
│   └── ui/                  Oberfläche (PySide6)
│       ├── theme.py         Farben/Formen aus den Designvorlagen, Hintergrund, Schriftanpassung
│       ├── widgets.py       Titelleiste, Fußleiste, Anzeigefelder, Knöpfe, Stoß-Raster, Logo
│       ├── keymap.py        Qt-Tasten → Nummernblock-Befehle
│       ├── menu_screen.py   Hauptmenü (Vorlage 1)
│       ├── game_screen.py   Zählansicht (Vorlage 2), auch für die Wiedergabe
│       ├── archive_screen.py Archiv: Liste aller gespeicherten Partien
│       ├── report_dialog.py Statistik-Fenster: Bericht anzeigen, als PDF speichern, drucken
│       ├── overlays.py      Abfragen: Fortsetzen, Abbruch, Archiv-Auswahl, Fehler
│       └── main_window.py   Bildschirmwechsel, Start-Prüfung, Abschluss, NumLock-Wächter
└── tests/                   automatische Tests (unittest)
```

**Zustandsautomat der Partie**

```
            Wertung / Rücknahme
             ┌────────────┐
             ▼            │
  (neu) ─► RUNNING ───────┘
             │  letzter Stoß + Sperrzeit abgelaufen      * dann -
             ├──────────────────────────────► FINISHED   (PDF, Archiv)
             └──────────────────────────────► ABORTED    (Archiv, kein PDF)
```

**Eingabe-Zustandsautomat** (`bk/input_logic.py`)

```
 BEREIT (Plus) ──0..7──────────────► WERTUNG +n ─┐
   │                                                ├─► GESPERRT (INPUT_LOCK_SECONDS) ─► BEREIT (Plus)
   └── - ─► MINUS ──0..7──────────► WERTUNG −n ─┘
              └── +  → zurück auf Plus    (8/9 werden abgelehnt)

 - und + sind auch während GESPERRT erlaubt (Modus für den nächsten Stoß), Ziffern nicht.
 /  → Rücknahme (auch während GESPERRT; hebt die Sperre auf, kurze Eigen-Sperre gegen Prellen)
 *  → ABBRUCH-FRAGE ── -  → Partie abbrechen
                   └─ jede andere Taste / Zeitablauf → weiter
```

Die Sperre ist rein zeitbasiert (monotone Uhr) und wird von einem 100-ms-Qt-Timer
angezeigt – es gibt kein `sleep()`, die Oberfläche bleibt immer bedienbar.

**Speicherformat** (`data/active_game.json`)

```json
{
  "app": "BK-Scoreboard",
  "format_version": 1,
  "saved_at": "2026-09-29T15:58:03",
  "sha256": "…Prüfsumme über state…",
  "state": {
    "game_id": "5f0c…",
    "mode": {"key": "BK50", "title": "50 Stoß", "strokes": 50, "halftime_after": 25,
             "grid_columns": 10, "highlight_last": 5},
    "started_at": "2026-09-29T15:42:10",
    "strokes": [3, 5, -2, 0, 4],
    "status": "running",
    "finished_at": null,
    "elapsed_seconds": 812.4,
    "revision": 17
  }
}
```

Die Spielart wird mitgespeichert – eine Partie lässt sich also auch dann fortsetzen,
wenn `config.py` inzwischen geändert wurde.

**Oberfläche und Auflösung:** Alle Maße stammen aus den Designvorlagen (Referenz 1024 × 768)
und werden proportional skaliert. Das Hauptmenü wird als Komposition zentriert,
die Zählansicht nutzt Layout-Streckfaktoren und füllt jedes Seitenverhältnis (4:3, 5:4, 16:9,
16:10). Schriftgrößen werden in jedem Element passend zu seiner tatsächlichen Größe berechnet.
Geprüft mit 1024 × 600, 1024 × 768, 1280 × 1024, 1366 × 768 und 1920 × 1080.

**Tastatur:** Alle Bedienelemente sind fokuslos; jeder Tastendruck landet genau einmal im
Hauptfenster und wird an die sichtbare Abfrage bzw. den aktiven Bildschirm weitergegeben.
Nummernblock-Tasten erkennt Qt am `KeypadModifier`. Falls NumLock trotzdem aus ist, werden
die Navigationscodes des Nummernblocks (Pos1, Ende, Pfeile …) als Rückfallebene in Ziffern
übersetzt – sofern das System sie als Nummernblock kennzeichnet.

**NumLock:** Beim Start und danach alle 2 Sekunden wird der Zustand geprüft
(`GetKeyState`). Ist NumLock aus, sendet das Programm einen NumLock-Tastendruck über
`SendInput`. Schutz gegen Hin-und-her-Schalten: nur wenn das eigene Fenster aktiv ist,
frühestens alle 3 Sekunden und höchstens dreimal hintereinander. Gelingt es nicht
(z. B. durch Systemrichtlinien), erscheint in der Fußleiste
„NUM-LOCK IST AUS – bitte die Taste [Num] drücken“.

## 8. Tests / Testmodus

```
python main.py --selftest
```
oder `python -m unittest discover -s tests -t .` im Programmordner.
Die Tests laufen in temporären Ordnern und berühren keine echten Spielstände.

Abgedeckt sind u. a.: +0 … +7 (ohne Vorzeichen), −0 … −7, Minus nur für einen Stoß,
Aufheben von Minus mit `+`, Minus-Vorwahl während der Sperre, ungültige Werte (8, 9, Text,
Kommazahlen), Sperrzeit (mit simulierter Uhr), Eingabe während der Sperre,
Tastenprellen, `/` direkt nach einer Eingabe, `/` mehrfach, Stoßzähler, komplette
50- und 100-Stoß-Partien, Abschluss exakt beim 50. bzw. 100. Stoß, Speichern nach jeder
Wertung, Absturz direkt nach einer Wertung, Absturz während des Schreibens, beschädigte
Dateien, Wiederherstellung kurz vor dem letzten Stoß, Fortsetzen, neue Partie, Abbruch,
PDF-Inhalt und Dateiname, NumLock-Schutzlogik, Archivliste, Statistik-Fenster
(Speichern und Drucken in eine Datei), Wiedergabe ohne Speicherung, Weiterspielen aus
dem Archiv, Anzahl je Wertung, Drucken ohne Standarddrucker, automatisches Löschen alter
Dateien sowie Oberflächentests mit echten Nummernblock-Tastenereignissen.

## 9. Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Fußleiste meldet „NUM-LOCK IST AUS“ | Taste `Num` drücken; Einstellung `AUTO_ENABLE_NUMLOCK` prüfen |
| Ziffern werden ignoriert | Wird der Nummernblock benutzt? Bei Laptops ohne Nummernblock `NUMPAD_ONLY = False` setzen |
| „ACHTUNG: Spielstand konnte nicht gespeichert werden!“ | Programmordner beschreibbar? Speicherplatz? Das Spiel läuft weiter, beim nächsten Stoß wird erneut gespeichert |
| PDF fehlt | `logs/application.log` prüfen, dann `python main.py --pdf results\DATEI.json` |
| „Das BK-Scoreboard läuft bereits“ | Es darf nur ein Programmfenster laufen (schützt den Spielstand) |
| Allgemeine Fehler | Details stehen in `logs/application.log` |
| „Kein Standarddrucker eingerichtet“ | Windows-Einstellungen → Bluetooth und Geräte → Drucker und Scanner → Drucker wählen → „Als Standard festlegen“. Tipp: dort „Windows verwaltet Standarddrucker“ ausschalten, sonst wechselt Windows den Standarddrucker eigenmächtig |
| Es wird auf dem falschen Drucker gedruckt | Standarddrucker in Windows ändern (siehe oben) |
| Windows meldet beim ersten Start der .exe „Der Computer wurde durch Windows geschützt“ | „Weitere Informationen“ → „Trotzdem ausführen“ (die .exe ist nicht digital signiert) |
| Virenscanner blockiert die .exe | Programmordner als Ausnahme eintragen – selbst erstellte PyInstaller-Programme werden gelegentlich fälschlich gemeldet |

## 10. Als .exe – ohne Python- und pip-Installation

Die `.exe` wird **einmalig** auf einem Windows-PC erstellt, auf dem das Programm bereits
installiert ist (`install_windows.bat` wurde ausgeführt). Das Ergebnis läuft danach auf
**jedem Windows-10/11-PC (64 Bit) ohne Python, ohne pip und ohne Installation**.

**Erstellen:** Doppelklick auf **`build_exe.bat`**. Das Skript
1. installiert PyInstaller in die vorhandene `.venv`,
2. führt den Selbsttest aus (bei einem Fehler wird keine .exe erstellt),
3. erstellt die Programmversion und öffnet den fertigen Ordner.

Dauer: einige Minuten. Alternativ in der Eingabeaufforderung:
`.venv\Scripts\python.exe -m pip install pyinstaller` und dann `.venv\Scripts\python.exe build_exe.py`.

**Ergebnis:** `dist\BK-Scoreboard\` (etwa 150–200 MB)

```
BK-Scoreboard\
├── BK-Scoreboard.exe   ← Programm (Doppelklick startet im Vollbild)
├── _internal\          ← Python, Qt, ReportLab … (nicht verändern)
├── config.py           ← Einstellungen – editierbar, danach Programm neu starten
├── assets\             ← Logo und Symbol – austauschbar
├── sounds\             ← Töne (WAV), z. B. halbzeit.wav – austauschbar
├── bilder\             ← Bilder/GIFs für hohe Wertungen – austauschbar
└── README.md
```
`data`, `results` und `logs` legt das Programm beim ersten Start daneben an.

**Einrichten auf dem Vereins-PC:**
* den **kompletten Ordner** kopieren (nicht nur die .exe), z. B. nach `C:\BK-Scoreboard` –
  nicht nach `C:\Programme`, dort darf das Programm keine Spielstände speichern
* Verknüpfung auf `BK-Scoreboard.exe` auf den Desktop bzw. in den Autostart (`shell:startup`) legen
* Optionen funktionieren wie bei Python, z. B. Verknüpfung mit Ziel `BK-Scoreboard.exe --windowed`

**Ton und Bilder ändern:** Datei in `sounds` bzw. `bilder` legen, den Dateinamen in `config.py` eintragen,
Programm neu starten – ein Neubau der .exe ist dafür nicht nötig.

**Einstellungen ändern:** `config.py` neben der .exe mit dem Editor öffnen, Wert ändern
(z. B. `INPUT_LOCK_SECONDS = 4`), speichern, Programm neu starten. Ein Neubau ist nicht nötig.
Enthält die Datei einen Fehler, meldet das Programm beim Start die Zeile.

**Neue Programmversion einspielen:** neue .exe erstellen und im installierten Ordner nur
`BK-Scoreboard.exe` und `_internal` ersetzen. `config.py`, `data`, `results` und `logs`
bleiben erhalten.

**Schutz beim Neubau:** PyInstaller leert `dist\BK-Scoreboard` vollständig. Liegen dort
bereits Spielstände oder Ergebnisse (weil das Programm direkt aus `dist` gestartet wurde),
bricht `build_exe.py` ab, statt sie zu löschen.

Der Selbsttest ist nur in der Python-Fassung verfügbar; er läuft beim Erstellen automatisch.
