using System.Diagnostics;

namespace Lkds.JoinApp;

/// <summary>Startet Windows-Kommandozeilenprogramme (netsh, icacls, schtasks) ohne Shell und ohne Passwörter.</summary>
public static class Tools
{
    /// <summary>Gibt null bei Erfolg zurück, sonst die Ausgabe des Programms als Fehlerbeschreibung.</summary>
    public static string? Run(string exe, params string[] args)
    {
        try
        {
            var psi = new ProcessStartInfo(exe)
            {
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            foreach (var a in args) psi.ArgumentList.Add(a);

            using var p = Process.Start(psi)!;
            var output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
            p.WaitForExit();
            return p.ExitCode == 0 ? null : output.Trim();
        }
        catch (Exception ex)
        {
            return ex.Message;
        }
    }
}
