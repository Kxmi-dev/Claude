using System.Collections.Generic;
using System.Linq;

namespace Lkds.Shared;

/// <summary>
/// Fester LDS-Ablauf: Welche Dateien liegen unter C:\LDS, was wird vor dem Join importiert,
/// was nach dem Neustart gestartet und was am Ende wieder entfernt.
/// </summary>
public static class LdsSteps
{
    public const string LdsDir = @"C:\LDS";

    /// <summary>Anzeige im Builder für „dieser Standort bekommt keine DNS-Datei“.</summary>
    public const string NoDns = "keine";

    /// <summary>DNS-Dateien, die im Builder zur Auswahl stehen.</summary>
    public static readonly string[] KnownDnsNames = { "KWBR", "LNRE", "LNBE" };

    /// <summary>Nur Buchstaben, Ziffern, Bindestrich und Unterstrich, damit daraus kein fremder Pfad werden kann.</summary>
    public static bool IsValidDnsName(string name) =>
        name.Length > 0 && name.Length <= 20 &&
        name.All(c => char.IsLetterOrDigit(c) && c < 128 || c == '-' || c == '_');

    /// <summary>Pfad relativ zu C:\LDS, z. B. REG\DNS-LNBE.reg.</summary>
    public static string DnsRegName(string dnsName) => @"REG\DNS-" + dnsName + ".reg";

    /// <summary>Reg-Dateien (relativ zu C:\LDS), die beim ersten Start der EXE importiert werden.</summary>
    public static readonly string[] StartupRegs =
    {
        "ZENworkspassivLogin.reg",
        "eml.reg",
        "Credential-Guard.reg",
        @"REG\OES.reg"
    };

    /// <summary>Programme, die nach dem Neustart gleichzeitig gestartet werden (Arbeitsverzeichnis = ihr Ordner).</summary>
    public static readonly (string Path, string Args)[] Programs =
    {
        (LdsDir + @"\zenworks.exe", ""),
        (LdsDir + @"\bitdef\epskit_x64.exe", "/silent /bdparams")
    };

    /// <summary>
    /// Vorauswahl der DNS-Datei für einen Standort. LNWS verwendet LNRE (so von Kimi bestätigt).
    /// Sonst die Datei mit demselben Namen wie der Standort, falls sie angeboten wird. Sonst null.
    /// </summary>
    public static string? DefaultDnsFor(string locationName, IEnumerable<string> options)
    {
        var list = options.ToList();
        var location = locationName.Trim().ToUpperInvariant();
        var wanted = location == "LNWS" ? "LNRE" : location;
        return list.FirstOrDefault(o => string.Equals(o, wanted, StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>Dateien unter C:\LDS, die am Ende gelöscht werden.</summary>
    public static IEnumerable<string> CleanupFiles()
    {
        yield return LdsDir + @"\zenworks.exe";
        foreach (var reg in StartupRegs) yield return LdsDir + "\\" + reg;
        foreach (var dns in KnownDnsNames) yield return LdsDir + "\\" + DnsRegName(dns);
        yield return LdsDir + @"\sysprep.bat";
        yield return LdsDir + @"\unattend.xml";
        yield return LdsDir + @"\install_Windows 10 Enterprise.clg";
    }

    /// <summary>Ordner unter C:\LDS, die samt Inhalt gelöscht werden.</summary>
    public static readonly string[] CleanupFolders = { LdsDir + @"\bitdef", LdsDir + @"\part" };

    /// <summary>Ordner, die nur gelöscht werden, wenn sie leer sind (zuerst REG, zuletzt C:\LDS).</summary>
    public static readonly string[] CleanupFoldersIfEmpty = { LdsDir + @"\REG", LdsDir };
}
