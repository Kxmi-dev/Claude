@echo off
rem =====================================================================
rem  BK-Scoreboard starten (Vollbild, ohne Konsolenfenster)
rem =====================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
    goto :eof
)
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%~dp0main.py"
    goto :eof
)
start "" pythonw "%~dp0main.py"
