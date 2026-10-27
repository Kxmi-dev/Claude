# LKDS AD Join Builder

Kleines Windows-Tool aus zwei Teilen:

- **Builder** (für Administratoren): liest die OUs aus dem Active Directory, lässt Standorte und Benutzer auswählen und erzeugt daraus eine individuelle **Join-EXE**.
- **Join-EXE** (für Zielrechner): eine einzelne EXE ohne Zusatzdateien. Die Konfiguration steckt bereits in der Datei. Doppelklick, Passwort eingeben, „COMPUTER JOINEN“.

## Voraussetzungen

- Zum **Benutzen**: Windows 10 (ab Version 1803) oder Windows 11. Nichts muss installiert werden, die Join-EXE nutzt das in Windows eingebaute .NET Framework und ist nur rund 30 KB groß.
- Zum **Bauen**: Windows mit [.NET 9 SDK (oder neuer)](https://dotnet.microsoft.com/download) und Internetzugang für den ersten Build.

## Bauen

Einfach **`build.cmd` doppelklicken**. Alternativ in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

(Ein direkter Aufruf von `.\build.ps1` scheitert bei heruntergeladenen ZIP-Dateien oft mit „nicht digital signiert“. Die beiden Varianten oben umgehen das nur für diesen einen Start.)

Ergebnis: `artifacts\LKDS-AD-Join-Builder.exe` (eine einzelne Datei, enthält die Join-Vorlage). Mit `dotnet test tests\Shared.Tests` laufen die Tests.

## Builder verwenden

1. **AD-Verbindung:** Domäne (`ad.lkds.de`) und Basis-OU sind vorausgefüllt, dein Windows-Benutzername steht schon im Feld „Benutzer“. **Passwort leer lassen = Verbindung mit der aktuellen Windows-Anmeldung (SSO).** Mit eingetragenem Passwort wird mit diesem Benutzer verbunden.
2. **Standorte:** Alle OUs direkt unterhalb der Basis-OU erscheinen automatisch (z. B. LNBE, LNWS, später LNSU, LNAU). Per Haken auswählen. Rechts daneben stellst du pro Standort ein, welche DNS-Datei (KWBR, LNRE, LNBE oder keine) er bekommt. Voreingestellt: LNBE → LNBE, LNWS → LNRE, KWBR → KWBR. Der vollständige Distinguished Name und die Zuordnung werden im Profil gespeichert.
3. **Benutzer:** Benutzer hinzufügen, entfernen und per Haken auswählen. Mindestens einer ist nötig. Beim Hinzufügen kann optional ein Passwort angegeben werden, das verschlüsselt in die EXE gelegt wird. Ohne Passwort fragt die Join-EXE am PC danach.
4. **EXE erstellen:** Dateiname (z. B. `LKDS-Join.exe`), Ausgabeordner und der Ordner mit den Registry-Dateien (Standard `C:\LDS`) wählen, Zusammenfassung prüfen, „EXE erstellen“. Die Registry-Dateien werden in die EXE eingebettet; fehlt eine, nennt der Builder sie.

**Profile** (Standard, IT, Notebook, Test …) speichern Domäne, Basis-OU, Benutzer und Standorte, nie ein Passwort. Sie liegen in `%AppData%\LKDS-AD-Join-Builder\profile.json` und gehören nur zum Builder.

## Join-EXE verwenden

1. EXE auf den Zielrechner kopieren und doppelklicken (die Windows-Abfrage für Administratorrechte bestätigen).
2. AD-Benutzer und Standort wählen, Computername prüfen (vorausgefüllt, änderbar), Passwort eingeben. Ein geänderter Name wird beim Join lokal gesetzt und das Computerkonto direkt unter diesem Namen in der Ziel-OU angelegt. Dafür ist nur ein Neustart nötig. Schlägt der Join fehl, wird der alte Name wiederhergestellt. Erlaubt sind höchstens 15 Zeichen: Buchstaben (ohne Umlaute), Ziffern und Bindestriche, nicht nur Ziffern.
3. „COMPUTER JOINEN“ klicken. Zuerst werden die Registry-Dateien importiert (DNS-Datei des Standorts, `OES.reg`, `ZENworkspassivLogin.reg`, `eml.reg`, `Credential-Guard.reg`), dann läuft der Join. Bei Erfolg öffnet die EXE eingehend TCP-Port 445 (SMB) über die Firewall-Regel „LKDS SMB eingehend (TCP 445)“, **nur im Domänenprofil**. Danach **startet der Computer sofort neu, ohne Abfrage und ohne Wartezeit.**

**Standard-Ablauf (LDS):** Im Builder (Schritt 4, standardmäßig an). Der Neustart-Nachlauf (Phase 2) läuft **als SYSTEM über einen geplanten Task, ohne Fenster und ohne dass sich jemand anmelden muss**. Dafür legt die EXE vor dem Neustart eine Kopie ohne Passwort und Schlüssel in `C:\ProgramData\LKDS-Join` ab (deshalb darf die Original-EXE auch auf einem USB-Stick liegen). Der Task startet 30 Sekunden nach dem Hochfahren, ohne Akku-Sperre und ohne Zeitlimit. Die Kopie wartet bis zu 3 Minuten auf Domäne und DNS und startet dann gleichzeitig `C:\LDS\zenworks.exe` und `C:\LDS\bitdef\epskit_x64.exe /silent /bdparams`, jeweils mit dem eigenen Ordner als Arbeitsverzeichnis. ZENworks startet nach etwa 5 Minuten selbst neu: In `HKLM\SOFTWARE\LKDS-Join` stehen die Anzahl der Starts und eine Marke „Programme gestartet“, der Task läuft beim nächsten Start erneut und startet die Programme nicht nochmal. Als fertig gilt: kein Installer-Prozess mehr (`zenworks`, `epskit_x64`, `setupdownloader`, Prozesse unter `C:\LDS`), mindestens 8 Minuten vergangen und in der Windows-Programmliste „Bitdefender“ und „ZENworks“ (andernfalls nach 20 Minuten, spätestens nach 90 Minuten oder 5 Starts). **Danach wird immer aufgeräumt, auch bei einem Fehler** (dann wird von Hand installiert): `zenworks.exe`, Ordner `bitdef`, alle Registry-Dateien, `sysprep.bat`, `unattend.xml`, `install_Windows 10 Enterprise.clg`, Ordner `part`, die Join-EXE samt Kopie, Tasks und Marke. `C:\LDS\REG` und `C:\LDS` selbst nur, wenn sie danach leer sind. Das Löschen übernimmt ein einmaliger Hilfs-Task, der 10 Sekunden wartet und es mehrfach versucht. Es wird kein Log geschrieben. ZENworks und Bitdefender (ca. 1,7 GB) sind nicht in der EXE, sie müssen unter `C:\LDS` liegen.

**Zusätzliches Skript nach dem Neustart (optional):** Im Builder (Schritt 4) lässt sich eine `.bat` auswählen. Sie wird in die Join-EXE eingebettet und im Nachlauf einmalig als SYSTEM ausgeführt, nachdem die Programme gestartet wurden. Sie läuft **nicht als angemeldeter Benutzer**, Netzlaufwerke oder Einstellungen eines Benutzers gibt es dort also nicht. Keine Passwörter in die `.bat` schreiben, sie ist in der EXE lesbar.

**Selbstlöschung:** Im Builder (Schritt 4, standardmäßig an) entfernt sich die Join-EXE im Nachlauf nach dem Neustart zusammen mit allem anderen. Nach einem Fehler beim Join bleibt sie bestehen, damit man es erneut versuchen kann.

Die Join-EXE schreibt kein Log. Meldungen und technische Details erscheinen nur im Programmfenster („Details anzeigen“).

## Benötigte AD-Berechtigungen

- Builder: Leserecht auf die Basis-OU (jeder normale Domänenbenutzer).
- Join-Benutzer (z. B. `test-wadm`): Recht „Computerobjekte erstellen“ in den Ziel-OUs, ggf. auch „Computerobjekte löschen/Konto zurücksetzen“, wenn ein Konto mit gleichem Namen schon existiert.

## Technik in Kürze

- Builder: C#, .NET 9, WPF. Join-EXE: C#, .NET Framework 4.7.2 (in Windows eingebaut), Windows Forms, deshalb winzig. Einzige Zusatzbibliothek: `System.DirectoryServices` (Microsoft) für den LDAP-Zugriff.
- Der Builder enthält die kleine Join-Vorlage. Er hängt die Konfiguration als einfachen Text ans Dateiende an, die Join-EXE liest sie beim Start aus sich selbst. Es gibt keine Konfigurationsdatei daneben.
- Der Join nutzt die Windows-Funktion `NetJoinDomain`.

## Sicherheitshinweise

- Passwörter werden nie in Profilen, oder auf der Kommandozeile gespeichert oder übergeben. **Einzige Ausnahme:** Ein im Builder bewusst eingegebenes Passwort wird verschlüsselt (AES-256) in die Join-EXE gelegt. Der Schlüssel steckt in derselben EXE. Das schützt vor dem Lesen mit Texteditor oder Suchwerkzeugen, **nicht** vor jemandem, der die EXE gezielt analysiert. Dafür ein Konto verwenden, das nur Computer in die Domäne aufnehmen darf, und diese EXE nicht weitergeben. Wer das nicht möchte, lässt das Passwortfeld leer.
- Benutzernamen, Domäne und OUs stehen lesbar in der Join-EXE. Das ist gewollt, sie sind nicht geheim.
- Die Join-EXE ist nicht digital signiert. Wer signieren will, muss nach dem Erstellen signieren (eine Signatur vor dem Anhängen würde ungültig).
- Die EXE-Dateien nur an Administratoren und Techniker weitergeben, da sie die Ziel-OUs verraten.
