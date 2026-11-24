Baue mir in diesem Ordner die spielbare Basis meines Koop-Spiels „UPTIME – Das Koop-Rechenzentrum“ mit Godot 4 (GDScript). Ich bin auf einem Mac (Apple Silicon); das Spiel muss sofort auf dem Mac laufen und später als Windows-.exe exportierbar sein. Alle Texte im Spiel auf Deutsch.

## Spielidee (Kurzfassung)
1–4 Spieler bauen gemeinsam ein Rechenzentrum: Racks und Server platzieren, Strom und Kühlung im Gleichgewicht halten, Kundenaufträge mit SLA (versprochene Uptime) erfüllen. Zufällige Störungen („Incidents“) wie defekte Festplatten oder Überhitzung muss das Team gemeinsam lösen. Jeder Spieler ist eine Figur, die durch den Serverraum läuft (isometrische 3D-Ansicht von schräg oben, Low-Poly).

## Setup (bitte selbst erledigen)
1. Prüfe, ob Godot 4 installiert ist. Falls nicht: `brew install --cask godot` (wenn Homebrew fehlt, sag mir Bescheid). Die Godot-Binary liegt dann unter `/Applications/Godot.app/Contents/MacOS/Godot`.
2. `git init`, sinnvolle `.gitignore` für Godot (`.godot/`, `export/`).
3. Ordnerstruktur: `scenes/`, `scripts/`, `ui/`. Nur Grundformen (BoxMesh, CapsuleMesh, Materialien in Farbe), keine externen Assets.

## Umfang der Basis (in dieser Reihenfolge bauen)
**Schritt 1 – Koop-Grundgerüst (wichtigster Teil, zuerst!)**
- Hauptmenü: Namensfeld, Button „Spiel hosten“, Feld für IP + Button „Beitreten“, „Beenden“. Beim Hosten die eigene lokale IP anzeigen.
- Godot High-Level-Multiplayer mit ENetMultiplayerPeer, Port 7777, max. 4 Spieler.
- **Host-autoritativ:** Der Host berechnet Simulation, Geld, Incidents. Clients schicken nur Eingaben/Aktionswünsche per RPC; Zustand wird per MultiplayerSynchronizer/RPC verteilt. Spieler per MultiplayerSpawner.
- Jeder Spieler: Kapsel-Figur in eigener Farbe mit Namensschild, Bewegung WASD, Kamera isometrisch folgt der eigenen Figur.
- Kommandozeilen-Argumente zum Testen: `--host` startet direkt als Host, `--join <ip>` tritt direkt bei, `--name <name>`.
- Sauber behandeln: Verbindung fehlgeschlagen, Host beendet, Spieler verlässt das Spiel.

**Schritt 2 – Bauen**
- Raum mit Raster (z. B. 16×12 Felder), Wände, Laderampe.
- Baumenü (Taste B): Rack (2.000 €), Klimagerät (3.000 €), Server-Typen zum Einbauen ins Rack: Web (800 €, 0,3 kW, wenig Hitze), Storage (1.500 €, 0,5 kW), Compute (2.500 €, 0,8 kW, mittlere Hitze). Platzieren mit linker Maus, R dreht, rechte Maus bricht ab. Interaktion mit E.
- Gemeinsame Kasse (Startkapital 15.000 €).
- Strom: Standort-Limit 20 kW, Anzeige im HUD; Überlast = Server fallen aus.
- Hitze: jeder Server erzeugt Hitze pro Feld, Klimageräte kühlen in einem Radius. Ab 35 °C drosseln, ab 45 °C Ausfall. Taste H zeigt Wärme-Overlay (Felder farbig).

**Schritt 3 – Kunden & Spieltag**
- Spieltag ca. 10 Min. mit Phasen Morgen (Planung) → Tag → Abend (Lastspitze, mehr Hitze) → Nacht (Abrechnung). Uhrzeit im HUD.
- Auftragsbrett (Taste Tab oder Objekt im Raum): 3–4 Kundenanfragen, z. B. „Bäckerei Krause“ (1 Web, 99 %, 30 €/Tag), „PixelPlay Gaming“ (4 Compute, 99,5 %, 400 €/Tag, Lastspitze abends), „StreamCo“ (6 Storage + 2 Compute, 99,9 %, 900 €/Tag). Annehmen → Server werden dem Kunden zugewiesen.
- Uptime pro Kunde messen; Einnahmen laufend; Strafe + Ruf-Verlust, wenn SLA verletzt.
- Tagesabrechnung als Fenster (Uptime je Kunde, Gewinn, Ruf).
- HUD: Uhrzeit/Phase, Kontostand, Ruf, Strom kW / Limit, Kundenliste mit Ampel (grün/gelb/rot).

**Schritt 4 – Erste Incidents**
- Einfaches „Regisseur“-System auf dem Host, häufiger bei hoher Last und abends.
- Festplatte defekt: Server-LED rot; Ersatzteil aus dem Lager-Regal holen (Spieler trägt immer nur 1 Objekt), am Server E gedrückt halten (3 s).
- Klimaanlage ausgefallen: Hitze steigt; Reparatur am Gerät mit Ersatzteil.
- Meldung oben im HUD mit Pfeil/Markierung zum Ort.
- Ping-System: mittlere Maustaste setzt eine für alle sichtbare Markierung.

## Qualität & Test
- Nach jedem Schritt mit `/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit-after 300` prüfen, dass keine Skriptfehler auftreten, und Fehler beheben.
- Lege `start_host.sh` und `start_client.sh` an (öffnen Host bzw. Client mit `127.0.0.1`), damit ich auf dem Mac zwei Fenster nebeneinander testen kann. Starte zum Schluss beide einmal selbst, um zu prüfen, dass sich der Client verbindet.
- Code übersichtlich und kommentiert (Deutsch), Konstanten (Preise, Limits) zentral in einer Datei `scripts/balance.gd`.
- Lege `export_presets.cfg` mit Presets für „Windows Desktop“ (export/windows/Uptime.exe) und „macOS“ an. Erkläre mir am Ende, wie ich die Export-Templates installiere und exportiere.
- Commit nach jedem abgeschlossenen Schritt.

## Am Ende
Schreibe eine `README.md` auf Deutsch: Starten auf dem Mac, Koop testen (lokal, LAN, Internet über Tailscale/Radmin VPN oder Portfreigabe 7777/UDP), Steuerung, Windows-Export. Gib mir dann eine kurze Zusammenfassung, was fertig ist und was als Nächstes kommt (weitere Incidents, Tech-Baum, Standorte, Speichern/Laden).
