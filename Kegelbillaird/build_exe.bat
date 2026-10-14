@echo off
rem =====================================================================
rem  BK-Scoreboard als eigenstaendige .exe erstellen
rem  Einmalig auf DIESEM PC ausfuehren (nach install_windows.bat).
rem  Das Ergebnis (dist\BK-Scoreboard) laeuft auf jedem Windows-PC
rem  OHNE Python- oder pip-Installation.
rem =====================================================================
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Bitte zuerst install_windows.bat ausfuehren.
    pause
    exit /b 1
)
echo.
echo  Installiere bzw. aktualisiere PyInstaller ...
".venv\Scripts\python.exe" -m pip install --upgrade "pyinstaller>=6.3"
if errorlevel 1 (
    echo.
    echo  FEHLER: PyInstaller konnte nicht installiert werden - Internetverbindung pruefen.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" build_exe.py
if errorlevel 1 (
    echo.
    echo  Es wurde keine .exe erstellt - siehe Meldungen oben.
    pause
    exit /b 1
)
explorer "dist\BK-Scoreboard"
pause
