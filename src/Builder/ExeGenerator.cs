using System.IO;
using System.Reflection;
using Lkds.Shared;

namespace Lkds.Builder;

/// <summary>Erzeugt die Join-EXE: eingebettete Vorlage kopieren und die Konfiguration anhängen.</summary>
public static class ExeGenerator
{
    private const string TemplateResource = "JoinTemplate.exe";

    public static bool HasTemplate =>
        Assembly.GetExecutingAssembly().GetManifestResourceInfo(TemplateResource) is not null;

    public static void Generate(string outputPath, JoinConfig config)
    {
        using var template = Assembly.GetExecutingAssembly().GetManifestResourceStream(TemplateResource)
            ?? throw new InvalidOperationException("Die Join-Vorlage ist nicht im Builder enthalten. Bitte mit build.ps1 bauen.");

        var temp = outputPath + ".tmp";
        try
        {
            using (var fs = File.Create(temp)) template.CopyTo(fs);
            ConfigPayload.AppendTo(temp, config);
            File.Move(temp, outputPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }

    /// <summary>Gibt eine Fehlermeldung zurück oder null, wenn der Dateiname brauchbar ist.</summary>
    public static string? ValidateFileName(string name)
    {
        if (string.IsNullOrWhiteSpace(name)) return "Bitte einen Dateinamen eingeben.";
        if (name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0) return "Der Dateiname enthält ungültige Zeichen.";
        if (!name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)) return "Der Dateiname muss auf .exe enden.";
        return null;
    }
}
