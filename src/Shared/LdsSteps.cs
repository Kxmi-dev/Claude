using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Lkds.Shared;

/// <summary>
/// Fester Ablauf, der nach dem Join und Neustart als Batch-Skript läuft.
/// Alle Pfade liegen fest unter C:\LDS auf dem Zielrechner.
/// </summary>
public static class LdsSteps
{
    /// <summary>DNS-Dateien, die im Builder zur Auswahl stehen.</summary>
    public static readonly string[] KnownDnsNames = { "LNBE", "LNRE", "KWBR" };

    /// <summary>Nur Buchstaben, Ziffern, Bindestrich und Unterstrich, damit daraus kein fremder Pfad werden kann.</summary>
    public static bool IsValidDnsName(string name) =>
        name.Length > 0 && name.Length <= 20 &&
        name.All(c => char.IsLetterOrDigit(c) && c < 128 || c == '-' || c == '_');

    public static string DnsRegPath(string dnsName) => @"C:\LDS\REG\DNS-" + dnsName + ".reg";

    /// <summary>
    /// Vorauswahl der DNS-Datei für einen Standort. ANNAHME: LNWS verwendet LNRE (so von Kimi angegeben).
    /// Sonst die Datei mit demselben Namen wie der Standort, falls sie angeboten wird.
    /// </summary>
    public static string? DefaultDnsFor(string locationName, IEnumerable<string> options)
    {
        var list = options.ToList();
        var location = locationName.Trim().ToUpperInvariant();
        var wanted = location == "LNWS" ? "LNRE" : location;
        return list.FirstOrDefault(o => string.Equals(o, wanted, StringComparison.OrdinalIgnoreCase));
    }

    public const string OesRegFile = @"C:\LDS\REG\OES.reg";

    /// <summary>Registry-Dateien, die vor dem Join importiert werden: OES.reg und die gewählte DNS-Datei.</summary>
    public static List<string> PreJoinRegFiles(string? dnsName)
    {
        var files = new List<string> { OesRegFile };
        if (!string.IsNullOrEmpty(dnsName)) files.Add(DnsRegPath(dnsName!));
        return files;
    }

    /// <summary>Batch-Skript für nach dem Neustart (ohne die Dateien, die schon vor dem Join importiert wurden).</summary>
    public static string Build()
    {
        var sb = new StringBuilder();
        sb.AppendLine("@echo off");
        sb.AppendLine("echo Starte Programme...");
        AppendStart(sb, @"C:\LDS\zenworks.exe", "");
        AppendStart(sb, @"C:\LDS\bitdef\epskit_x64.exe", " /silent /bdparams");

        sb.AppendLine("echo Importiere Registry...");
        AppendImport(sb, @"C:\LDS\ZENworkspassivLogin.reg");
        AppendImport(sb, @"C:\LDS\eml.reg");
        AppendImport(sb, @"C:\LDS\Credential-Guard.reg");

        sb.AppendLine("echo LDS-Nachlauf beendet.");
        return sb.ToString().Replace("\r\n", "\n").Replace("\n", "\r\n");
    }

    private static void AppendStart(StringBuilder sb, string exe, string args)
    {
        sb.AppendLine($"if exist \"{exe}\" (start \"\" \"{exe}\"{args}) else echo FEHLT: {exe}");
    }

    private static void AppendImport(StringBuilder sb, string reg)
    {
        sb.AppendLine($"if exist \"{reg}\" (reg import \"{reg}\") else echo FEHLT: {reg}");
    }
}
