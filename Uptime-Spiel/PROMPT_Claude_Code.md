Baue mir in diesem Ordner die spielbare Basis meines Koop-Spiels „UPTIME – Das Koop-Rechenzentrum“ mit Godot 4 (GDScript). Ich bin auf einem Mac (Apple Silicon); das Spiel muss sofort auf dem Mac laufen und später als Windows-.exe exportierbar sein. Alle Texte im Spiel auf Deutsch.

## Arbeitsort
Das Projekt liegt auf einem Netzlaufwerk (SMB-Fileserver, gemountet unter /Volumes). Arbeite ausschließlich in diesem Ordner. Netzlaufwerke sind langsamer und unterstützen nicht immer Dateisperren und Symlinks – nutze keine Symlinks, setze `git config core.fileMode false`, ignoriere `.DS_Store` und `._*` in der .gitignore und weise mich hin, falls Godot oder git Probleme mit dem Laufwerk haben.

## Spielidee
1–4 Spieler bauen gemeinsam ein Rechenzentrum auf – vom kleinen Abstellraum bis zur großen Halle. Racks und Server aufstellen, Strom und Kühlung im Gleichgewicht halten, Kundenaufträge mit SLA (versprochene Uptime) erfüllen. Zufällige Störungen („Incidents“) wie defekte Festplatten oder Überhitzung muss das Team gemeinsam lösen.

## Komplett 3D, man läuft selbst herum
- Alles ist echte 3D-Welt, keine 2D-Menüs zum Bauen außer einem kleinen Auswahlrad/Leiste.
- **Third-Person-Ansicht**: Kamera hinter der Spielfigur, Maus dreht die Kamera (Maus eingefangen), WASD laufen, Shift sprinten, Leertaste springen. Taste V wechselt zur Ego-Perspektive (First Person).
- Fadenkreuz in der Mitte; Interaktion per Raycast auf das Objekt, auf das man schaut (E = benutzen/aufheben/reparieren, Hinweistext „[E] Festplatte tauschen“ einblenden).
- **Bauen in 3D**: Taste B öffnet Bau-Leiste (1–5 wählen), ein halbtransparentes Vorschau-Modell erscheint dort, wo man auf den Boden schaut, rastet auf ein 1-m-Raster ein, grün = möglich, rot = blockiert. Mausrad oder R dreht, Linksklick platziert, Rechtsklick bricht ab.
- Server werden per E in ein Rack eingeschoben (sichtbar als Einschub im Rack). Racks haben blinkende LEDs (emissive Material): grün = ok, orange = heiß/gedrosselt, rot = Ausfall.
- Gekaufte Teile kommen als Kartons an der Eingangstür/Laderampe an und müssen hingetragen werden (Figur trägt immer nur 1 Objekt sichtbar in den Händen).
- Grafik: Low-Poly aus Grundformen (BoxMesh, CylinderMesh, CapsuleMesh, CSG für Räume), gute Beleuchtung (Deckenlampen als OmniLight3D/SpotLight3D, WorldEnvironment mit leichtem Glow für LEDs, Schatten). Keine externen Assets.
- Sound optional mit generierten Tönen (AudioStreamGenerator) für Lüfterrauschen und Alarm.

## Fortschritt = die Welt wächst
Eine zusammenhängende 3D-Welt mit Bereichen, die nacheinander freigeschaltet werden. Freigeschaltete Bereiche werden durch eine Tür / ein Rolltor mit dem vorherigen verbunden – man läuft einfach hinein.
1. **Abstellraum im Keller** (Start): klein, ca. 4×5 m, Platz für 2 Racks, 5 kW Strom, ein Fenster-Lüfter als Kühlung.
2. **Garage**: ca. 6×8 m, Rolltor, Platz für ~6 Racks, 15 kW. Freischalten: 10.000 € + Ruf 20.
3. **Lagerhalle**: ca. 20×30 m, Laderampe, 60 kW. Freischalten: 50.000 € + Ruf 40.
4. (Später) **Industriehalle** und **Rechenzentrum-Campus** – nur als verschlossene Bereiche/Platzhalter anlegen.
- Freischalten über ein „Immobilien“-Terminal oder ein Schild am verschlossenen Tor („[E] Garage mieten – 10.000 €“). Beim Freischalten öffnet sich das Tor mit Animation, Strom-Limit erhöht sich.
- Jeder Bereich hat eigenes Strom-Limit und eigene Raumtemperatur.

## Umfang der Basis (in dieser Reihenfolge bauen)
**Schritt 1 – Koop-Grundgerüst (wichtigster Teil, zuerst!)**
- Hauptmenü (3D-Hintergrund mit Racks erwünscht): Namensfeld, „Spiel hosten“, IP-Feld + „Beitreten“, „Beenden“. Beim Hosten die eigene lokale IP anzeigen.
- Godot High-Level-Multiplayer mit ENetMultiplayerPeer, Port 7777, max. 4 Spieler.
- **Host-autoritativ:** Der Host berechnet Simulation, Geld, Incidents, Bauen. Clients schicken Aktionswünsche per RPC; Zustand per MultiplayerSynchronizer/RPC. Spieler und gebaute Objekte per MultiplayerSpawner (auch für später Beitretende korrekt).
- Spielerbewegung clientseitig flüssig (eigene Figur lokal bewegen, Position synchronisieren, andere interpolieren).
- Jede Figur: Kapsel-Körper mit Kopf, Helm in eigener Spielerfarbe, Namensschild (Label3D) über dem Kopf, einfache Lauf-Wippanimation.
- Kommandozeilen-Argumente zum Testen: `--host`, `--join <ip>`, `--name <name>`.
- Sauber behandeln: Verbindung fehlgeschlagen, Host beendet, Spieler verlässt das Spiel. Esc öffnet Pause-Menü (Maus frei), Spiel läuft im Koop weiter.

**Schritt 2 – Bauen & Welt**
- Die Welt mit Abstellraum (offen), Garage und Lagerhalle (verschlossen) wie oben.
- Kaufbar: Rack (2.000 €), Klimagerät (3.000 €), Server Web (800 €, 0,3 kW, wenig Hitze), Storage (1.500 €, 0,5 kW), Compute (2.500 €, 0,8 kW, mittlere Hitze).
- Gemeinsame Kasse, Startkapital 8.000 €.
- Strom pro Bereich; Überlast = Sicherung fliegt, Licht flackert, Server des Bereichs fallen aus, Sicherungskasten an der Wand per E wieder einschalten.
- Hitze pro Bereich (und grob pro Rack): Server heizen, Klimageräte kühlen. Ab 35 °C drosseln, ab 45 °C Ausfall. Taste H schaltet Wärmebild-Ansicht (Objekte nach Temperatur einfärben). Wandthermometer zeigt Raumtemperatur.

**Schritt 3 – Kunden & Spieltag**
- Spieltag ca. 10 Min. mit Phasen Morgen → Tag → Abend (Lastspitze, mehr Hitze) → Nacht (Abrechnung). Licht durch Fenster ändert sich mit der Tageszeit.
- Auftragsbrett als Pinnwand/Monitor in der Welt (per E öffnen): 3–4 Kundenanfragen, z. B. „Bäckerei Krause“ (1 Web, 99 %, 30 €/Tag), „PixelPlay Gaming“ (4 Compute, 99,5 %, 400 €/Tag, Lastspitze abends), „StreamCo“ (6 Storage + 2 Compute, 99,9 %, 900 €/Tag). Annehmen → passende Server werden dem Kunden zugewiesen.
- Uptime pro Kunde; Einnahmen laufend; Strafe + Ruf-Verlust bei SLA-Verletzung.
- Tagesabrechnung als Fenster (Uptime je Kunde, Gewinn, Ruf).
- HUD (schlicht): Uhrzeit/Phase, Kontostand, Ruf, Strom kW / Limit des aktuellen Bereichs, Kundenliste mit Ampel (Tab).

**Schritt 4 – Erste Incidents**
- „Regisseur“-System auf dem Host, häufiger bei hoher Last und abends.
- Festplatte defekt: Rack-LED rot + Piepen; Ersatzteil aus dem Lager-Regal holen, am Rack E gedrückt halten (3 s, Fortschrittsring).
- Klimagerät ausgefallen: Rauch/Partikel, Hitze steigt; Reparatur mit Ersatzteil.
- Meldung im HUD + 3D-Markierung (leuchtender Pfeil über dem Objekt, durch Wände sichtbar).
- Ping-System: mittlere Maustaste setzt eine für alle sichtbare 3D-Markierung.

## Qualität & Test
- Nach jedem Schritt mit `/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit-after 300` prüfen, dass keine Skriptfehler auftreten, und Fehler beheben.
- Lege `start_host.sh` und `start_client.sh` an (Host bzw. Client auf `127.0.0.1`, Fenster je halbe Bildschirmbreite), damit ich auf dem Mac zwei Fenster nebeneinander testen kann. Starte zum Schluss beide einmal selbst und prüfe, dass sich der Client verbindet.
- Code übersichtlich und auf Deutsch kommentiert; alle Zahlen (Preise, Limits, Freischalt-Kosten) zentral in `scripts/balance.gd`.
- Renderer: „Forward+“, Fallback „Mobile“ falls nötig; 60 FPS auf einem MacBook anpeilen.
- `export_presets.cfg` mit Presets „Windows Desktop“ (export/windows/Uptime.exe) und „macOS“. Erkläre mir am Ende, wie ich die Export-Templates installiere und exportiere.
- Commit nach jedem abgeschlossenen Schritt.

## Am Ende
Schreibe eine `README.md` auf Deutsch: Starten auf dem Mac, Koop testen (lokal, LAN, Internet über Tailscale/Radmin VPN oder Portfreigabe 7777/UDP), Steuerung, Windows-Export. Gib mir dann eine kurze Zusammenfassung, was fertig ist und was als Nächstes kommt (Industriehalle/Campus, weitere Incidents, Tech-Baum, Personal, Speichern/Laden).
