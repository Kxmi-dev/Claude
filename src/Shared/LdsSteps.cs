using System.Text;

namespace Lkds.Shared;

/// <summary>
/// Fester Ablauf, der nach dem Join und Neustart als Batch-Skript läuft.
/// Alle Pfade liegen fest unter C:\LDS auf dem Zielrechner.
/// </summary>
public static class LdsSteps
{
    /// <summary>
    /// Standort-Name (Großbuchstaben) zu DNS-Registrierungsdatei.
    /// ANNAHME: LNWS verwendet DNS-LNRE.reg (so von Kimi angegeben, bitte bestätigen).
    /// </summary>
    public static string? DnsRegFileFor(string locationName)
    {
        switch (locationName.Trim().ToUpperInvariant())
        {
            case "LNBE": return @"C:\LDS\REG\DNS-LNBE.reg";
            case "LNWS": return @"C:\LDS\REG\DNS-LNRE.reg";
            default: return null;
        }
    }

    public static string Build(string locationName)
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
        AppendImport(sb, @"C:\LDS\REG\OES.reg");

        var dns = DnsRegFileFor(locationName);
        if (dns is not null) AppendImport(sb, dns);
        else sb.AppendLine("echo Hinweis: Fuer diesen Standort ist keine DNS-Registry-Datei hinterlegt.");

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
