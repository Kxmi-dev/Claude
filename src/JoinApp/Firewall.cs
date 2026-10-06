namespace Lkds.JoinApp;

/// <summary>Öffnet eingehend TCP 445 (SMB) über eine eigene Firewall-Regel, nur im Domänenprofil.</summary>
public static class Firewall
{
    private const string RuleName = "LKDS SMB eingehend (TCP 445)";

    /// <summary>Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung.</summary>
    public static string? OpenPort445()
    {
        // Vorhandene Regel zuerst entfernen, damit nie Duplikate entstehen (Fehler hier ist egal).
        Tools.Run("netsh", "advfirewall", "firewall", "delete", "rule", $"name={RuleName}");
        return Tools.Run("netsh", "advfirewall", "firewall", "add", "rule", $"name={RuleName}",
            "dir=in", "action=allow", "protocol=TCP", "localport=445", "profile=domain");
    }
}
