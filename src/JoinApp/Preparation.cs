using System.Diagnostics;
using Lkds.Join.Shared;

namespace Lkds.Join.JoinApp;

/// <summary>Importiert die in die EXE eingebetteten .reg-Dateien.</summary>
static class Preparation
{
    /// <summary>Importiert alle Start-Reg-Dateien. Gibt die Fehler zurück (leer = alles ok).</summary>
    public static List<string> ImportStartupRegs(JoinConfig config)
    {
        var errors = new List<string>();
        foreach (var name in StartupFiles.Regs)
        {
            try { ImportEmbedded(config, name); }
            catch (Exception ex)
            {
                errors.Add(ex.Message);
                Log.Write("Reg-Import fehlgeschlagen: " + ex.Message);
            }
        }
        return errors;
    }

    /// <summary>Importiert die DNS-Reg-Datei des Standorts (falls für ihn eine definiert ist).</summary>
    public static void ImportDnsReg(JoinConfig config, string locationName)
    {
        var name = StartupFiles.DnsRegFor(locationName);
        if (name != null) ImportEmbedded(config, name);
    }

    static void ImportEmbedded(JoinConfig config, string name)
    {
        if (!config.RegFiles.TryGetValue(name, out var base64))
            throw new FileNotFoundException($"Reg-Datei nicht in der EXE enthalten: {name}");

        string temp = Path.Combine(Path.GetTempPath(), "lkds-" + Guid.NewGuid().ToString("N") + ".reg");
        File.WriteAllBytes(temp, Convert.FromBase64String(base64));
        try
        {
            var psi = new ProcessStartInfo("reg.exe") { UseShellExecute = false, CreateNoWindow = true };
            psi.ArgumentList.Add("import");
            psi.ArgumentList.Add(temp);
            using var p = Process.Start(psi)!;
            if (!p.WaitForExit(30_000)) throw new TimeoutException($"Reg-Import hat zu lange gedauert: {name}");
            if (p.ExitCode != 0) throw new InvalidOperationException($"Reg-Import fehlgeschlagen (Code {p.ExitCode}): {name}");
            Log.Write("Reg importiert: " + name);
        }
        finally
        {
            try { File.Delete(temp); } catch { }
        }
    }
}
