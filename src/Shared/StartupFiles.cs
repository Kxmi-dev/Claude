namespace Lkds.Join.Shared;

/// <summary>Reg-Dateien, die der Builder in die Join-EXE einbettet (Pfade relativ zum Reg-Ordner).</summary>
public static class StartupFiles
{
    /// <summary>Werden beim Start der Join-EXE importiert.</summary>
    public static readonly string[] Regs =
    {
        "ZENworkspassivLogin.reg",
        "eml.reg",
        "Credential-Guard.reg",
        @"REG\OES.reg",
    };

    static readonly Dictionary<string, string> DnsRegByLocation = new(StringComparer.OrdinalIgnoreCase)
    {
        ["LNBE"] = @"REG\DNS-LNBE.reg",
        ["LNWS"] = @"REG\DNS-LNRE.reg",
    };

    /// <summary>Standortabhängige DNS-Reg, direkt vor dem Join importiert. Null, wenn der Standort keine hat.</summary>
    public static string? DnsRegFor(string locationName) =>
        DnsRegByLocation.TryGetValue(locationName, out var path) ? path : null;
}
