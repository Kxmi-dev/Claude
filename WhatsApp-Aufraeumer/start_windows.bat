@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js ist nicht installiert. Bitte von https://nodejs.org die LTS-Version installieren und dann nochmal starten.
  pause
  exit /b 1
)
if not exist node_modules (
  echo Erster Start: benoetigte Pakete werden installiert, das dauert ein paar Minuten ...
  call npm install
)
node server.js
pause
