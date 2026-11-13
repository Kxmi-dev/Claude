#!/bin/bash
# WhatsApp-Aufräumer für macOS – per Doppelklick starten
cd "$(dirname "$0")"

# Node.js aus Homebrew finden, auch wenn das Terminal es nicht im PATH hat
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js ist nicht installiert."
  echo "Bitte von https://nodejs.org die LTS-Version (macOS-Installer) installieren und dann nochmal starten."
  read -n 1 -s -r -p "Taste drücken zum Schließen …"
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "Erster Start: benötigte Pakete werden installiert, das dauert ein paar Minuten …"
  npm install || { read -n 1 -s -r -p "Installation fehlgeschlagen. Taste drücken …"; exit 1; }
fi

node server.js
