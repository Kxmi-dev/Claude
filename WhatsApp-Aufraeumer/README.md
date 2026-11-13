# 🧹 WhatsApp-Aufräumer

Kleines Programm, das sich wie WhatsApp Web mit deinem Konto verbindet und dir **alle Chats und Gruppen** in einer Liste zeigt. Dort kannst du:

- **Chats löschen** (einzeln oder viele auf einmal)
- **Gruppen verlassen**
- **Gruppen verlassen & löschen**
- filtern nach **Alter** (z. B. „älter als 1 Jahr"), nur Chats / nur Gruppen, Suche, sortieren nach ältesten zuerst

Alles läuft nur auf deinem eigenen Computer (`http://localhost:3000`), es geht nichts an fremde Server außer an WhatsApp selbst.

## Starten

1. Einmalig **Node.js** (LTS) installieren: https://nodejs.org
2. **Windows:** Doppelklick auf `start_windows.bat`
   **Mac/Linux:** im Ordner `npm install` und dann `npm start`
3. Der Browser öffnet sich automatisch. Auf dem Handy in WhatsApp → **Einstellungen → Verknüpfte Geräte → Gerät hinzufügen** und den QR-Code scannen.
4. Warten, bis die Chats geladen sind – fertig.

Beim nächsten Start bleibst du angemeldet (gespeichert im Ordner `.wwebjs_auth`). Mit „Abmelden" oben rechts wird der Computer wieder aus deinen verknüpften Geräten entfernt.

## Gut zu wissen

- **Löschen ist endgültig** und gilt auch auf dem Handy. Vorher kommt immer eine Sicherheitsabfrage.
- **Gruppen**, in denen du noch Mitglied bist, kann WhatsApp nicht direkt löschen – dafür gibt es „Verlassen & löschen".
- Angepinnte Chats sind standardmäßig ausgeblendet, damit du sie nicht aus Versehen löschst.
- Zwischen den Aktionen wartet das Programm kurz (ca. 1 Sekunde), damit WhatsApp keinen Spam vermutet.
- Das Programm nutzt die inoffizielle Bibliothek [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js). Offiziell erlaubt WhatsApp solche Programme nicht; für normales Aufräumen am eigenen Konto ist das Risiko gering, aber nicht null. Lösch lieber in Portionen als hunderte Chats auf einmal.
- Wenn nach einem WhatsApp-Update nichts mehr geht: im Ordner `npm update` ausführen.
