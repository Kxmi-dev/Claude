# LKDS AD Join Builder

Kleines Windows-Tool aus zwei Teilen:

- **Builder** (für Administratoren): liest die OUs aus dem Active Directory, lässt Standorte und Benutzer auswählen und erzeugt daraus eine individuelle **Join-EXE**.
- **Join-EXE** (für Zielrechner): eine einzelne EXE ohne Zusatzdateien. Die Konfiguration steckt bereits in der Datei. Doppelklick, Passwort eingeben, „COMPUTER JOINEN“.

## Voraussetzungen

- Zum **Benutzen**: Windows 10/11 (64 Bit). .NET muss nicht installiert sein.
- Zum **Bauen**: Windows mit [.NET 10 SDK](https://dotnet.microsoft.com/download) und Internetzugang für den ersten Build.

## Bauen

Einfach **`build.cmd` doppelklicken**. Alternativ in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

(Ein direkter Aufruf von `.\build.ps1` scheitert bei heruntergeladenen ZIP-Dateien oft mit „nicht digital signiert“. Die beiden Varianten oben umgehen das nur für diesen einen Start.)

Ergebnis: `artifacts\LKDS-AD-Join-Builder.exe` (eine einzelne Datei, enthält die Join-Vorlage). Mit `dotnet test tests\Shared.Tests` laufen die Tests.

## Builder verwenden

1. **AD-Verbindung:** Domäne (`ad.lkds.de`) und Basis-OU sind vorausgefüllt. Standardmäßig wird mit dem aktuell angemeldeten Windows-Konto verbunden, ein Passwort ist dann nicht nötig. Alternativ Haken entfernen und Benutzer und Passwort eingeben. Dann „Mit Active Directory verbinden“.
2. **Standorte:** Alle OUs direkt unterhalb der Basis-OU erscheinen automatisch (z. B. LNBE, LNWS, später LNSU, LNAU). Per Haken auswählen. Der vollständige Distinguished Name wird mitgespeichert.
3. **Benutzer:** Benutzer hinzufügen, entfernen und per Haken auswählen. Mindestens einer ist nötig.
4. **EXE erstellen:** Dateiname (z. B. `LKDS-Join.exe`) und Ausgabeordner wählen, Zusammenfassung prüfen, „EXE erstellen“.

**Profile** (Standard, IT, Notebook, Test …) speichern Domäne, Basis-OU, Benutzer und Standorte, nie ein Passwort. Sie liegen in `%AppData%\LKDS-AD-Join-Builder\profile.json` und gehören nur zum Builder.

## Join-EXE verwenden

1. EXE auf den Zielrechner kopieren und doppelklicken (die Windows-Abfrage für Administratorrechte bestätigen).
2. AD-Benutzer und Standort wählen, Computername prüfen (vorausgefüllt, änderbar), Passwort eingeben.
3. „COMPUTER JOINEN“ klicken. Bei Erfolg wird ein Neustart angeboten.

Das Log liegt unter `C:\ProgramData\LKDS-Join\join.log` (Zeit, Computer, Benutzer, Standort, OU, Ergebnis, kein Passwort).

## Benötigte AD-Berechtigungen

- Builder: Leserecht auf die Basis-OU (jeder normale Domänenbenutzer).
- Join-Benutzer (z. B. `test-wadm`): Recht „Computerobjekte erstellen“ in den Ziel-OUs, ggf. auch „Computerobjekte löschen/Konto zurücksetzen“, wenn ein Konto mit gleichem Namen schon existiert.

## Technik in Kürze

- C#, .NET 10, WPF. Einzige Zusatzbibliothek: `System.DirectoryServices` (Microsoft) für den LDAP-Zugriff.
- Die Join-EXE ist selbst-enthalten (Single-File). Der Builder hängt die Konfiguration als JSON ans Dateiende an, die Join-EXE liest sie beim Start aus sich selbst. Es gibt keine Konfigurationsdatei daneben.
- Der Join nutzt die Windows-Funktion `NetJoinDomain`.

## Sicherheitshinweise

- Passwörter werden nie gespeichert, geloggt, übergeben (keine Kommandozeile) oder in die EXE eingebettet.
- Benutzernamen, Domäne und OUs stehen lesbar in der Join-EXE. Das ist gewollt, sie sind nicht geheim.
- Die Join-EXE ist nicht digital signiert. Wer signieren will, muss nach dem Erstellen signieren (eine Signatur vor dem Anhängen würde ungültig).
- Die EXE-Dateien nur an Administratoren und Techniker weitergeben, da sie die Ziel-OUs verraten.
