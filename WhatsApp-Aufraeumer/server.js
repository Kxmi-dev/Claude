// WhatsApp-Aufräumer – lokaler Server
// Meldet sich per QR-Code bei WhatsApp Web an, listet Chats & Gruppen
// und kann Chats löschen sowie Gruppen verlassen (und danach löschen).

const path = require('path');
const { exec } = require('child_process');
const express = require('express');
const QRCode = require('qrcode');
const { Client, LocalAuth } = require('whatsapp-web.js');

const PORT = Number(process.env.PORT) || 3000;
const HOST = '127.0.0.1'; // nur lokal erreichbar – niemand im Netzwerk kommt an deine Chats
const PAUSE_MS = 1200;    // Pause zwischen Aktionen, damit WhatsApp nicht misstrauisch wird

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- Zustand
const state = {
  status: 'starting', // starting | qr | loading | ready | disconnected | error
  qr: null,           // QR-Code als data:-URL
  percent: 0,
  message: 'WhatsApp wird gestartet …',
  me: null,
  busy: false,
};

let client = null;

function createClient() {
  const puppeteer = {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  };
  if (process.env.CHROME_PATH) puppeteer.executablePath = process.env.CHROME_PATH;

  const c = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
    puppeteer,
  });

  c.on('qr', async (qr) => {
    state.status = 'qr';
    state.qr = await QRCode.toDataURL(qr, { margin: 1, width: 300 });
    state.message = 'Scanne den QR-Code mit WhatsApp auf deinem Handy.';
    console.log('QR-Code bereit – im Browser scannen.');
  });

  c.on('authenticated', () => {
    state.status = 'loading';
    state.qr = null;
    state.message = 'Angemeldet – Chats werden geladen …';
    console.log('Angemeldet.');
  });

  c.on('loading_screen', (percent, msg) => {
    state.status = 'loading';
    state.percent = Number(percent) || 0;
    state.message = `Chats werden geladen … ${percent} %`;
  });

  c.on('ready', () => {
    state.status = 'ready';
    state.qr = null;
    state.percent = 100;
    state.message = 'Bereit.';
    const info = c.info || {};
    state.me = { name: info.pushname || '', number: info.wid ? info.wid.user : '' };
    console.log('WhatsApp ist bereit.');
  });

  c.on('auth_failure', (msg) => {
    state.status = 'error';
    state.message = 'Anmeldung fehlgeschlagen: ' + msg;
    console.error('Anmeldung fehlgeschlagen:', msg);
  });

  c.on('disconnected', (reason) => {
    state.status = 'disconnected';
    state.me = null;
    state.message = 'Verbindung getrennt (' + reason + ').';
    console.log('Getrennt:', reason);
  });

  return c;
}

async function startClient() {
  state.status = 'starting';
  state.qr = null;
  state.percent = 0;
  state.message = 'WhatsApp wird gestartet …';
  client = createClient();
  try {
    await client.initialize();
  } catch (err) {
    state.status = 'error';
    state.message = 'Start fehlgeschlagen: ' + err.message;
    console.error(err);
  }
}

async function restartClient() {
  try { if (client) await client.destroy(); } catch (_) { /* egal */ }
  await startClient();
}

// ---------------------------------------------------------------- Hilfen
function chatToJson(chat) {
  const isGroup = !!chat.isGroup;
  const meta = isGroup ? chat.groupMetadata || {} : {};
  const myId = client.info && client.info.wid ? client.info.wid._serialized : null;
  let iAmAdmin = false;
  let participants = null;
  if (isGroup && Array.isArray(meta.participants)) {
    participants = meta.participants.length;
    const me = meta.participants.find((p) => p.id && p.id._serialized === myId);
    iAmAdmin = !!(me && (me.isAdmin || me.isSuperAdmin));
  }
  const last = chat.lastMessage;
  let preview = '';
  if (last) {
    preview = last.body || (last.hasMedia ? '[Medien]' : `[${last.type || 'Nachricht'}]`);
    if (preview.length > 80) preview = preview.slice(0, 80) + '…';
  }
  return {
    id: chat.id._serialized,
    name: chat.name || (chat.id && chat.id.user) || 'Unbekannt',
    isGroup,
    timestamp: chat.timestamp || 0, // Unix-Sekunden der letzten Aktivität
    unreadCount: chat.unreadCount || 0,
    archived: !!chat.archived,
    pinned: !!chat.pinned,
    muted: !!chat.isMuted,
    left: isGroup && !!chat.isReadOnly, // Gruppe bereits verlassen
    participants,
    iAmAdmin,
    preview,
  };
}

function requireReady(req, res, next) {
  if (state.status !== 'ready') return res.status(409).json({ error: 'WhatsApp ist noch nicht bereit.' });
  next();
}

// ---------------------------------------------------------------- Aktionen
async function doAction(action, id) {
  const chat = await client.getChatById(id);
  if (!chat) throw new Error('Chat nicht gefunden');

  if (action === 'delete') {
    if (chat.isGroup && !chat.isReadOnly) {
      throw new Error('Du bist noch in der Gruppe – erst verlassen');
    }
    const ok = await chat.delete();
    if (ok === false) throw new Error('WhatsApp hat das Löschen abgelehnt');
    return 'gelöscht';
  }

  if (action === 'leave' || action === 'leaveDelete') {
    if (!chat.isGroup) throw new Error('Kein Gruppenchat');
    if (!chat.isReadOnly) {
      await chat.leave();
      await sleep(PAUSE_MS);
    }
    if (action === 'leave') return 'verlassen';
    const fresh = await client.getChatById(id);
    const ok = await fresh.delete();
    if (ok === false) throw new Error('Verlassen ok, aber Löschen abgelehnt');
    return 'verlassen & gelöscht';
  }

  throw new Error('Unbekannte Aktion');
}

// ---------------------------------------------------------------- Web-Server
const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/status', (req, res) => res.json(state));

app.get('/api/chats', requireReady, async (req, res) => {
  try {
    const chats = await client.getChats();
    const list = chats
      .filter((c) => c.id && c.id._serialized !== 'status@broadcast')
      .map(chatToJson);
    res.json(list);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/action', requireReady, async (req, res) => {
  const { action, ids } = req.body || {};
  if (!['delete', 'leave', 'leaveDelete'].includes(action) || !Array.isArray(ids) || ids.length === 0) {
    return res.status(400).json({ error: 'Ungültige Anfrage.' });
  }
  if (state.busy) return res.status(409).json({ error: 'Es läuft gerade schon eine Aktion.' });

  state.busy = true;
  const results = [];
  try {
    for (const id of ids) {
      try {
        const msg = await doAction(action, id);
        results.push({ id, ok: true, msg });
      } catch (err) {
        results.push({ id, ok: false, msg: err.message });
      }
      await sleep(PAUSE_MS);
    }
  } finally {
    state.busy = false;
  }
  res.json({ results });
});

app.post('/api/logout', async (req, res) => {
  try {
    if (client && state.status === 'ready') await client.logout();
  } catch (err) {
    console.error(err);
  }
  res.json({ ok: true });
  restartClient(); // danach direkt wieder einen neuen QR-Code anbieten
});

app.post('/api/restart', async (req, res) => {
  res.json({ ok: true });
  restartClient();
});

app.listen(PORT, HOST, () => {
  const url = `http://localhost:${PORT}`;
  console.log(`\nWhatsApp-Aufräumer läuft: ${url}\n(Fenster offen lassen – zum Beenden Strg+C)\n`);
  if (!process.env.NO_BROWSER) {
    const cmd = process.platform === 'win32' ? `start "" "${url}"`
      : process.platform === 'darwin' ? `open "${url}"` : `xdg-open "${url}"`;
    exec(cmd, () => {});
  }
  startClient();
});

process.on('SIGINT', async () => {
  console.log('\nBeende …');
  try { if (client) await client.destroy(); } catch (_) { /* egal */ }
  process.exit(0);
});
