@echo off
rem Startet build.ps1 ohne Signatur-Abfrage (Ausfuehrungsrichtlinie nur fuer diesen Aufruf umgangen).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
echo.
pause
