using System.ComponentModel;
using System.Runtime.InteropServices;

namespace Lkds.Join.JoinApp;

/// <summary>Domain Join über die Windows-API (netapi32). Das Passwort wird nur durchgereicht, nie gespeichert.</summary>
static class DomainJoin
{
    const uint JoinDomain = 0x1;
    const uint AccountCreate = 0x2;
    const int ComputerNamePhysicalDnsHostname = 5;
    const int NetSetupDomainName = 3;

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    static extern uint NetJoinDomain(string? server, string domain, string? accountOu, string? account, string? password, uint options);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    static extern uint NetGetJoinInformation(string? server, out IntPtr name, out int status);

    [DllImport("netapi32.dll")]
    static extern uint NetApiBufferFree(IntPtr buffer);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetComputerNameEx(int type, string name);

    public static bool IsDomainMember()
    {
        if (NetGetJoinInformation(null, out var name, out var status) != 0) return false;
        NetApiBufferFree(name);
        return status == NetSetupDomainName;
    }

    /// <summary>Gibt 0 bei Erfolg zurück, sonst den Windows-Fehlercode.</summary>
    public static uint Join(string domain, string ou, string user, string password, string computerName)
    {
        string oldName = Environment.MachineName;
        bool renamed = !string.Equals(oldName, computerName, StringComparison.OrdinalIgnoreCase);

        if (renamed && !SetComputerNameEx(ComputerNamePhysicalDnsHostname, computerName))
            return (uint)Marshal.GetLastWin32Error();

        string account = user.Contains('\\') || user.Contains('@') ? user : $"{domain}\\{user}";
        uint rc = NetJoinDomain(null, domain, ou, account, password, JoinDomain | AccountCreate);

        if (rc != 0 && renamed)
            SetComputerNameEx(ComputerNamePhysicalDnsHostname, oldName);
        return rc;
    }

    public static string FriendlyMessage(uint code) => code switch
    {
        5 => "Für diesen Benutzer fehlen die erforderlichen Berechtigungen.",
        1326 or 86 => "Das eingegebene Passwort ist nicht korrekt.",
        1909 => "Das Benutzerkonto ist gesperrt.",
        53 or 1355 or 2453 => "Keine Verbindung zum Active Directory möglich.",
        87 or 8240 => "Die Ziel-OU wurde nicht gefunden.",
        2224 => "Ein Computerkonto mit diesem Namen existiert bereits.",
        2691 => "Der Computer ist bereits Mitglied einer Domäne.",
        _ => "Der Domain Join ist fehlgeschlagen.",
    };

    public static string TechnicalMessage(uint code) => $"Fehlercode {code}: {new Win32Exception((int)code).Message}";
}
