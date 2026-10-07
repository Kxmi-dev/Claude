using Lkds.Join.Shared;

namespace Lkds.Join.Builder;

static class JoinExeGenerator
{
    public const string TemplateFileName = "JoinApp.template";

    /// <summary>Kopiert die Join-Vorlage und hängt die Konfiguration an. Ergebnis: eine einzelne EXE.</summary>
    public static string Create(string outputFolder, string fileName, JoinConfig config)
    {
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
}
