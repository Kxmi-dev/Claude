using System.Collections.Generic;
using System.IO;
using Lkds.Shared;

namespace Lkds.JoinApp;

/// <summary>Importiert die in die EXE eingebetteten .reg-Dateien (beim ersten Start, vor dem Join).</summary>
public static class Preparation
{
    /// <summary>
    /// Importiert die Start-Reg-Dateien und, falls gewählt, die DNS-Datei. Gibt die Fehler zurück (leer = alles ok).
    /// </summary>
    public static List<string> ImportRegs(JoinConfig config, string? dnsName)
    {
        var names = new List<string>(LdsSteps.StartupRegs);
        // DNS zuerst, damit die Domäne beim Join sicher gefunden wird.
        if (!string.IsNullOrEmpty(dnsName)) names.Insert(0, LdsSteps.DnsRegName(dnsName!));

        var errors = new List<string>();
        foreach (var name in names)
        {
            var error = Import(config, name);
            if (error is not null) errors.Add(error);
        }
        return errors;
    }

    private static string? Import(JoinConfig config, string name)
    {
        if (!config.RegFiles.TryGetValue(name, out var data))
            return $"Nicht in der EXE enthalten: {name}";

        var temp = Path.Combine(Path.GetTempPath(), "lkds-" + Guid.NewGuid().ToString("N") + ".reg");
        try
        {
            File.WriteAllBytes(temp, data);
            var error = Tools.Run("reg", "import", temp);
            return error is null ? null : $"{name}: {error}";
        }
        catch (Exception ex)
        {
            return $"{name}: {ex.Message}";
        }
        finally
        {
            try { File.Delete(temp); } catch { }
        }
    }
}
