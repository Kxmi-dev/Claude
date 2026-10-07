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

    public static string DnsRegPath(string dnsName) => @"C:\LDS\REG\DNS " + dnsName + ".reg";

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

    /// <summary>Dateien, die nach dem Neustart gelöscht werden.</summary>
    public static readonly string[] CleanupFiles =
    {
        @"C:\LDS\sysprep.bat",
        @"C:\LDS\unattend.xml",
        @"C:\LDS\install_Windows 10 Enterprise.clg"
    };

    /// <summary>Ordner, die samt Inhalt nach dem Neustart gelöscht werden.</summary>
    public static readonly string[] CleanupFolders = { @"C:\LDS\part" };

    public const string OesRegFile = @"C:\LDS\REG\OES.reg";

    /// <summary>Batch-Skript für nach dem Neustart. dnsName: gewählte DNS-Datei (ohne Endung) oder null.</summary>
    public static string Build(string? dnsName = null)
    {
        var sb = new StringBuilder();
        sb.AppendLine("@echo off");
        sb.AppendLine("echo Starte Programme...");
        AppendStart(sb, @"C:\LDS\zenworks.exe", "");
        AppendStart(sb, @"C:\LDS\bitdef\epskit_x64.exe", " /silent /bdparams");

        sb.AppendLine("echo Importiere Registry...");
        AppendImport(sb, OesRegFile);
        if (!string.IsNullOrEmpty(dnsName)) AppendImport(sb, DnsRegPath(dnsName!));
        AppendImport(sb, @"C:\LDS\ZENworkspassivLogin.reg");
        AppendImport(sb, @"C:\LDS\eml.reg");
        AppendImport(sb, @"C:\LDS\Credential-Guard.reg");

        // Aufräumen: genau diese Einträge unter C:\LDS, nichts anderes.
        sb.AppendLine("echo Raeume auf...");
        foreach (var file in CleanupFiles) AppendDeleteFile(sb, file);
        foreach (var dir in CleanupFolders) AppendDeleteFolder(sb, dir);

        sb.AppendLine("echo LDS-Nachlauf beendet.");
        return sb.ToString().Replace("\r\n", "\n").Replace("\n", "\r\n");
    }

    private static void AppendDeleteFile(StringBuilder sb, string file)
    {
        sb.AppendLine($"if exist \"{file}\" (del /f /q \"{file}\" & if exist \"{file}\" (echo FEHLER beim Loeschen: {file}) else (echo Geloescht: {file})) else echo Nicht vorhanden: {file}");
    }

    private static void AppendDeleteFolder(StringBuilder sb, string folder)
    {
        sb.AppendLine($"if exist \"{folder}\\\" (rmdir /s /q \"{folder}\" & if exist \"{folder}\\\" (echo FEHLER beim Loeschen: {folder}) else (echo Geloescht: {folder})) else echo Nicht vorhanden: {folder}");
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
