# LKDS AD Join Builder

Zwei kleine WPF-Anwendungen (.NET 10, keine Zusatzpakete außer `System.DirectoryServices`):

- **Builder** (`src/Builder`) – liest Standorte aus dem AD und erzeugt individuelle Join-EXEs.
- **JoinApp** (`src/JoinApp`) – die Vorlage für die Join-EXE; führt den Domain Join durch.
- **Shared** (`src/Shared`) – Konfigurationsmodell und Einbetten/Lesen der Konfiguration.

## Voraussetzungen
- Windows 10/11 x64, zum Bauen das .NET SDK 10.
- Builder-Rechner: Domänenmitglied oder Netzzugriff auf den DC.

## Bauen
```powershell
./publish.ps1
```
Ergebnis: `artifacts/LKDS-Join-Builder/` mit `LKDS-Join-Builder.exe` und `JoinApp.template`
(beide Dateien müssen zusammen bleiben). Der Builder braucht das SDK nicht.

## Builder verwenden
1. **AD-Verbindung:** Der Benutzer wird automatisch mit der aktuellen Windows-Anmeldung vorbelegt. Ohne Passwort verbindet sich der Builder mit dieser Anmeldung (SSO); mit Passwort mit den eingegebenen Daten. Das Passwort wird nie gespeichert.
2. **Standorte:** Alle OUs direkt unter der Basis-OU erscheinen automatisch; per Checkbox auswählen.
3. **Benutzer:** Join-Konten hinzufügen/entfernen/auswählen (mindestens eines).
4. **EXE erstellen:** Dateiname und Ausgabeordner wählen, Zusammenfassung prüfen, „EXE erstellen“.
Profile (Domäne, Basis-OU, Benutzer, Standorte) liegen in `%AppData%\LKDS-Join-Builder\settings.json`.

## Join-EXE verwenden
Auf den Ziel-PC kopieren, doppelklicken (UAC bestätigen). Beim Start:
1. Programme starten: `C:\LDS\zenworks.exe`, `C:\LDS\bitdef\epskit_x64.exe /silent /bdparams`
2. Reg-Dateien importieren: `ZENworkspassivLogin.reg`, `eml.reg`, `Credential-Guard.reg`, `REG\OES.reg` (alle unter `C:\LDS`)

Beim Klick auf „COMPUTER JOINEN“ wird zuerst die DNS-Reg-Datei des Standorts importiert
(`LNBE` → `C:\LDS\REG\DNS-LNBE.reg`, `LNWS` → `C:\LDS\REG\DNS-LNRE.reg`), danach erfolgt der Join in die gewählte OU; anschließend wird ein Neustart angeboten.
Fehlende Dateien werden unter „Details“ gemeldet. Log: `%ProgramData%\LKDS-Join\join.log`.
Die Listen stehen in `src/JoinApp/Preparation.cs`.

## Wie die Konfiguration in die EXE kommt
Der Builder kopiert `JoinApp.template` und hängt die Konfiguration (JSON, ohne Passwort) ans Dateiende. Die fertige EXE ist eine einzelne Datei ohne Zusatzdateien.

## AD-Berechtigungen
Das Join-Konto braucht in der Ziel-OU das Recht „Computerobjekte erstellen“ (und Schreibrechte auf diese). Der Builder braucht nur Leserechte auf die Basis-OU.

## Sicherheit
Passwörter werden nie gespeichert, geloggt, eingebettet oder per Kommandozeile übergeben. Benutzernamen und OUs sind eingebettet und nicht geheim. Die Join-EXE importiert Reg-Dateien und startet Programme mit Administratorrechten – die Dateien in `C:\LDS` sollten nur für Administratoren beschreibbar sein.
