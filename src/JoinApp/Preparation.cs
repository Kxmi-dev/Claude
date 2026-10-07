using System.Diagnostics;

namespace Lkds.Join.JoinApp;

/// <summary>Programme starten und .reg-Dateien importieren (ersetzt die bisherige .bat).</summary>
static class Preparation
{
    const string LdsDir = @"C:\LDS";

    // Wird beim Start der EXE ausgeführt.
    static readonly (string Path, string Args)[] Programs =
    {
        (LdsDir + @"\zenworks.exe", ""),
        (LdsDir + @"\bitdef\epskit_x64.exe", "/silent /bdparams"),
    };

    static readonly string[] RegFiles =
    {
        LdsDir + @"\ZENworkspassivLogin.reg",
        LdsDir + @"\eml.reg",
        LdsDir + @"\Credential-Guard.reg",
        LdsDir + @"\REG\OES.reg",
    };

    // Standortabhängig: wird direkt vor dem Domain Join importiert.
    static readonly Dictionary<string, string> DnsRegByLocation = new(StringComparer.OrdinalIgnoreCase)
    {
        ["LNBE"] = LdsDir + @"\REG\DNS-LNBE.reg",
        ["LNWS"] = LdsDir + @"\REG\DNS-LNRE.reg",
    };

    /// <summary>Startet alle Programme und importiert alle Reg-Dateien. Gibt die Fehler zurück (leer = alles ok).</summary>
    public static List<string> RunStartup()
    {
        var errors = new List<string>();
        foreach (var (path, args) in Programs)
            TryRun(() => StartProgram(path, args), errors);
        foreach (var reg in RegFiles)
            TryRun(() => ImportReg(reg), errors);
        return errors;
    }

    /// <summary>Importiert die DNS-Reg-Datei des Standorts (falls für ihn eine definiert ist).</summary>
    public static void ImportDnsReg(string locationName)
    {
        if (DnsRegByLocation.TryGetValue(locationName, out var path))
            ImportReg(path);
    }

    static void TryRun(Action action, List<string> errors)
    {
        try { action(); }
        catch (Exception ex)
        {
            errors.Add(ex.Message);
            Log.Write("Vorbereitung fehlgeschlagen: " + ex.Message);
        }
    }

    static void StartProgram(string path, string args)
    {
        if (!File.Exists(path)) throw new FileNotFoundException($"Programm nicht gefunden: {path}");
        Process.Start(new ProcessStartInfo(path, args)
        {
            UseShellExecute = true,
            WorkingDirectory = Path.GetDirectoryName(path)!,
        });
        Log.Write($"Programm gestartet: {path} {args}".TrimEnd());
    }

    static void ImportReg(string path)
    {
        if (!File.Exists(path)) throw new FileNotFoundException($"Reg-Datei nicht gefunden: {path}");
        var psi = new ProcessStartInfo("reg.exe") { UseShellExecute = false, CreateNoWindow = true };
        psi.ArgumentList.Add("import");
        psi.ArgumentList.Add(path);
        using var p = Process.Start(psi)!;
        if (!p.WaitForExit(30_000)) throw new TimeoutException($"Reg-Import hat zu lange gedauert: {path}");
        if (p.ExitCode != 0) throw new InvalidOperationException($"Reg-Import fehlgeschlagen (Code {p.ExitCode}): {path}");
        Log.Write("Reg importiert: " + path);
    }
}
