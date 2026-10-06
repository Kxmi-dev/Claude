using System.Diagnostics;

namespace Lkds.JoinApp;

/// <summary>Öffnet eingehend TCP 445 (SMB) über eine eigene Firewall-Regel, nur im Domänenprofil.</summary>
public static class Firewall
{
    private const string RuleName = "LKDS SMB eingehend (TCP 445)";

    /// <summary>Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung.</summary>
    public static string? OpenPort445()
    {
        // Vorhandene Regel zuerst entfernen, damit nie Duplikate entstehen (Fehler hier ist egal).
        RunNetsh("advfirewall", "firewall", "delete", "rule", $"name={RuleName}");
        return RunNetsh("advfirewall", "firewall", "add", "rule", $"name={RuleName}",
            "dir=in", "action=allow", "protocol=TCP", "localport=445", "profile=domain");
    }

    private static string? RunNetsh(params string[] args)
    {
        try
        {
            var psi = new ProcessStartInfo("netsh")
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
