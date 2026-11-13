using System.Diagnostics;

namespace Lkds.JoinApp;

/// <summary>
/// Löscht die laufende EXE nach Programmende. Eine laufende EXE kann sich nicht selbst löschen,
/// deshalb startet ein kleiner versteckter cmd-Befehl, der bis zu ca. 60 Sekunden lang versucht zu löschen.
/// Der Löschbefehl umgeht den Papierkorb (del), die Datei ist danach weg.
/// </summary>
public static class SelfDelete
{
    public static void Start(string exePath)
    {
        // Nur Anführungszeichen im Pfad wären problematisch, die kommen in Windows-Dateinamen nicht vor.
        var args = "/c for /l %i in (1,1,60) do (del /f /q \"" + exePath + "\" >nul 2>&1 & " +
                   "if not exist \"" + exePath + "\" exit & ping -n 2 127.0.0.1 >nul)";
        Process.Start(new ProcessStartInfo("cmd.exe", args) { CreateNoWindow = true, UseShellExecute = false });
    }
}
