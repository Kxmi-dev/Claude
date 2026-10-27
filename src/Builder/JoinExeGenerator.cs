using Lkds.Join.Shared;

namespace Lkds.Join.Builder;

static class JoinExeGenerator
{
    public const string TemplateFileName = "JoinApp.template";

    /// <summary>Kopiert die Join-Vorlage und hängt die Konfiguration samt Reg-Dateien an. Ergebnis: eine einzelne EXE.</summary>
    public static string Create(string outputFolder, string fileName, JoinConfig config, string regFolder)
    {
        config.RegFiles = LoadRegFiles(regFolder, config.Locations);

        string template = Path.Combine(AppContext.BaseDirectory, TemplateFileName);
        if (!File.Exists(template))
            throw new FileNotFoundException($"Die Vorlage '{TemplateFileName}' fehlt neben dem Builder.");

        if (!fileName.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)) fileName += ".exe";
        string target = Path.Combine(outputFolder, fileName);

        File.Copy(template, target, overwrite: true);
        try { ConfigPayload.Append(target, config); }
        catch { File.Delete(target); throw; }
        return target;
    }

    // Alle Start-Reg-Dateien plus die DNS-Reg jedes gewählten Standorts. Fehlt eine, wird nicht gebaut.
    static Dictionary<string, string> LoadRegFiles(string regFolder, IEnumerable<JoinLocation> locations)
    {
        var names = StartupFiles.Regs
            .Concat(locations.Select(l => StartupFiles.DnsRegFor(l.Name)).OfType<string>())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        var missing = names.Where(n => !File.Exists(Path.Combine(regFolder, n))).ToList();
        if (missing.Count > 0)
            throw new FileNotFoundException("Diese Reg-Dateien fehlen im Reg-Ordner:\n" + string.Join("\n", missing));

        return names.ToDictionary(n => n, n => Convert.ToBase64String(File.ReadAllBytes(Path.Combine(regFolder, n))));
    }
}
