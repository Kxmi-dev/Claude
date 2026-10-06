using System.ComponentModel;
using System.Runtime.InteropServices;

namespace Lkds.JoinApp;

/// <summary>Ergebnis eines Join-Versuchs mit Klartext-Meldung und technischem Detail.</summary>
public class JoinResult
{
    public bool Success { get; }
    public string Message { get; }
    public string Details { get; }

    public JoinResult(bool success, string message, string details)
    {
        Success = success;
        Message = message;
        Details = details;
    }
}

/// <summary>Domain Join über die Windows-API (netapi32 / kernel32). Passwörter werden nur im Speicher verwendet.</summary>
public static class DomainJoiner
{
    private const int JoinDomain = 0x1;
    private const int AccountCreate = 0x2;
    private const int JoinWithNewName = 0x400;
    private const int ComputerNamePhysicalDnsHostname = 5;
    private const int NetSetupDomainName = 3;

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern int NetJoinDomain(string? server, string domain, string? accountOU,
        string account, string password, int options);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern int NetGetJoinInformation(string? server, out IntPtr nameBuffer, out int bufferType);

    [DllImport("netapi32.dll")]
    private static extern int NetApiBufferFree(IntPtr buffer);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetComputerNameEx(int nameType, string name);

    /// <summary>Gibt den Domänennamen zurück, wenn der Computer bereits Domänenmitglied ist, sonst null.</summary>
    public static string? GetCurrentDomain()
    {
        if (NetGetJoinInformation(null, out var buffer, out var type) != 0) return null;
        try
        {
            return type == NetSetupDomainName ? Marshal.PtrToStringUni(buffer) : null;
        }
        finally
        {
            NetApiBufferFree(buffer);
        }
    }

    public static JoinResult Join(string domain, string targetOu, string user, string password, string newName)
    {
        var oldName = Environment.MachineName;
        var rename = !string.Equals(oldName, newName, StringComparison.OrdinalIgnoreCase);
        var options = JoinDomain | AccountCreate;

        if (rename)
        {
            if (!SetComputerNameEx(ComputerNamePhysicalDnsHostname, newName))
                return new JoinResult(false, "Der Computername konnte nicht geändert werden.",
                    new Win32Exception(Marshal.GetLastWin32Error()).Message);
            options |= JoinWithNewName;
        }

        var code = NetJoinDomain(null, domain, targetOu, $"{domain}\\{user}", password, options);
        if (code == 0)
            return new JoinResult(true, "Der Computer wurde erfolgreich der Domäne hinzugefügt.", "");

        if (rename) SetComputerNameEx(ComputerNamePhysicalDnsHostname, oldName);
        return new JoinResult(false, Describe(code), $"Fehlercode {code}: {new Win32Exception(code).Message}");
    }

    private static string Describe(int code) => code switch
    {
        5 => "Für diesen Benutzer fehlen die erforderlichen Berechtigungen.",
        1326 or 1331 or 86 => "Das eingegebene Passwort ist nicht korrekt.",
        1909 => "Das Benutzerkonto ist gesperrt.",
        53 or 1355 or 1222 or 1787 => "Keine Verbindung zum Active Directory möglich.",
        2 or 8240 or 1319 => "Die Ziel-OU wurde nicht gefunden.",
        2691 => "Der Computer ist bereits Mitglied einer Domäne.",
        2224 => "Ein Computerkonto mit diesem Namen existiert bereits.",
        2202 => "Der Benutzername ist ungültig.",
        _ => "Der Domain-Join ist fehlgeschlagen."
    };
}
