# LKDS AD Join Builder

Zwei kleine WPF-Anwendungen (.NET 9, keine Zusatzpakete außer `System.DirectoryServices`):

- **Builder** (`src/Builder`) – liest Standorte aus dem AD und erzeugt individuelle Join-EXEs.
- **JoinApp** (`src/JoinApp`) – die Vorlage für die Join-EXE; führt den Domain Join durch.
- **Shared** (`src/Shared`) – Konfigurationsmodell und Einbetten/Lesen der Konfiguration.

## Voraussetzungen
- Windows 10/11 x64, zum Bauen das .NET SDK 9.
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
4. **EXE erstellen:** Dateiname, Ausgabeordner und Reg-Ordner (z. B. `C:\LDS`, daraus werden die Reg-Dateien eingebettet; fehlt eine, wird nicht gebaut) wählen, Zusammenfassung prüfen, „EXE erstellen“.
Profile (Domäne, Basis-OU, Benutzer, Standorte) liegen in `%AppData%\LKDS-Join-Builder\settings.json`.

## Join-EXE verwenden
Voraussetzung: `C:\LDS\zenworks.exe` und `C:\LDS\bitdef\` liegen auf dem PC (vom Image). Die EXE selbst muss auf einer lokalen Platte liegen (z. B. `C:\LDS`), nicht auf USB oder Netzlaufwerk. Doppelklick, UAC bestätigen.

**Phase 1 (erster Start):**
1. Beim Start werden die in die EXE eingebetteten Reg-Dateien importiert (`ZENworkspassivLogin.reg`, `eml.reg`, `Credential-Guard.reg`, `REG\OES.reg`).
2. „COMPUTER JOINEN“: erst die DNS-Reg des Standorts (`LNBE` → `REG\DNS-LNBE.reg`, `LNWS` → `REG\DNS-LNRE.reg`), dann der Join in die gewählte OU.
3. Bei Erfolg legt die EXE einen geplanten Task (SYSTEM, beim Systemstart, `LKDS-Join-Post`) an und startet **sofort** neu.

**Phase 2 (nach dem Neustart, ohne Anmeldung und ohne Fenster):**
1. Der Task startet die EXE mit `--post`. Sie wartet bis zu 3 Minuten auf Domäne/Netz und startet dann `C:\LDS\zenworks.exe` und `C:\LDS\bitdef\epskit_x64.exe /silent /bdparams` gleichzeitig.
2. ZENworks startet nach etwa 5 Minuten selbst neu. Beim nächsten Start läuft der Task erneut und macht anhand einer Marke in `HKLM\SOFTWARE\LKDS-Join` weiter, ohne die Programme nochmal zu starten.
3. Aufräumen, sobald kein Installer mehr läuft und frühestens 8 Minuten nach dem Start (wenn Bitdefender und ZENworks in der Programmliste stehen; sonst nach 20 Minuten; spätestens nach 90 Minuten bzw. 5 Startversuchen): `zenworks.exe`, `bitdef\`, Reg-Dateien in `C:\LDS`, die Join-EXE, die Tasks, die Registry-Marke, Log und .NET-Temp-Ordner werden gelöscht. `C:\LDS` selbst nur, wenn sie danach leer ist. Das erledigt ein einmaliger Hilfs-Task (`LKDS-Join-Cleanup`), weil sich die laufende EXE nicht selbst löschen kann.

Schlägt etwas fehl, wird trotzdem aufgeräumt; dann muss von Hand installiert werden. Log (bis zum Aufräumen): `%ProgramData%\LKDS-Join\join.log`.

## AD-Berechtigungen
Das Join-Konto braucht in der Ziel-OU das Recht „Computerobjekte erstellen“ (und Schreibrechte auf diese). Der Builder braucht nur Leserechte auf die Basis-OU.

## Sicherheit
Passwörter werden nie gespeichert, geloggt, eingebettet oder per Kommandozeile übergeben. Benutzernamen und OUs sind eingebettet und nicht geheim. Die Join-EXE importiert Reg-Dateien und startet Programme mit Administratorrechten (Phase 2 als SYSTEM) – `C:\LDS` und der Ordner der EXE sollten nur für Administratoren beschreibbar sein.
