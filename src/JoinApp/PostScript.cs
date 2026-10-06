using System.IO;
using System.Text;

namespace Lkds.JoinApp;

/// <summary>
/// Legt die eingebettete .bat in einem geschützten Ordner ab und plant sie einmalig für den nächsten
/// Systemstart (als SYSTEM, höchste Rechte). Danach entfernt sich die Aufgabe samt Dateien selbst.
/// </summary>
public static class PostScript
{
    private const string TaskName = "LKDS-Nachlauf";
    private static readonly string Folder =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "LKDS-Join");

    /// <summary>Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung.</summary>
    public static string? Schedule(byte[] script)
    {
        try
        {
            Directory.CreateDirectory(Folder);

            // Nur SYSTEM (S-1-5-18) und Administratoren (S-1-5-32-544) dürfen im Ordner schreiben.
            var acl = Tools.Run("icacls", Folder, "/inheritance:r",
                "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F");
            if (acl is not null) return $"Ordner konnte nicht abgesichert werden: {acl}";

            var bat = Path.Combine(Folder, "nachlauf.bat");
            var runner = Path.Combine(Folder, "nachlauf-start.cmd");
            File.WriteAllBytes(bat, script);
            File.WriteAllText(runner, RunnerText.ReplaceLineEndings("\r\n"), Encoding.ASCII);

            return Tools.Run("schtasks", "/Create", "/TN", TaskName, "/TR", $"\"{runner}\"",
                "/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F");
        }
        catch (Exception ex)
        {
            return ex.Message;
        }
    }

    // Führt die .bat aus, schreibt die Ausgabe ins join.log und räumt anschließend alles auf.
    private const string RunnerText = """
        @echo off
        set "D=%~dp0"
        call "%D%nachlauf.bat" > "%D%nachlauf-ausgabe.txt" 2>&1
        set "RC=%errorlevel%"
        schtasks /Delete /TN "LKDS-Nachlauf" /F >nul 2>&1
        echo %date% %time% - Nachlauf-Skript beendet, Exitcode %RC% >> "%D%join.log"
        type "%D%nachlauf-ausgabe.txt" >> "%D%join.log"
        del "%D%nachlauf-ausgabe.txt" "%D%nachlauf.bat" >nul 2>&1
        (goto) 2>nul & del "%~f0"
        """;
}
