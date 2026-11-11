@echo off
rem =====================================================================
rem  BK-Scoreboard - Installation (einmalig ausfuehren)
rem  Legt eine eigene Python-Umgebung (.venv) im Programmordner an,
rem  installiert PySide6 und reportlab und startet den Selbsttest.
rem =====================================================================
setlocal
cd /d "%~dp0"
echo.
echo  BK-Scoreboard - Installation
echo  ----------------------------
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)
%PY% --version
if errorlevel 1 (
    echo.
    echo  FEHLER: Python wurde nicht gefunden.
    echo  Bitte Python 3.10 oder neuer von https://www.python.org installieren
    echo  und dabei "Add python.exe to PATH" anhaken.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo  Lege Python-Umgebung an ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo  FEHLER: Python-Umgebung konnte nicht angelegt werden.
        pause
        exit /b 1
    )
)
echo  Installiere Pakete ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  FEHLER: Pakete konnten nicht installiert werden - Internetverbindung pruefen.
    pause
    exit /b 1
)
echo.
echo  Selbsttest wird ausgefuehrt (dauert ca. 30 Sekunden) ...
".venv\Scripts\python.exe" main.py --selftest
if errorlevel 1 (
    echo.
    echo  ACHTUNG: Mindestens ein Test ist fehlgeschlagen - siehe Ausgabe oben.
) else (
    echo.
    echo  Installation erfolgreich. Start mit: start_bk_scoreboard.bat
)
pause
