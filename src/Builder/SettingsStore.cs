using System.Text.Json;

namespace Lkds.Join.Builder;

static class SettingsStore
{
    static readonly string FilePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "LKDS-Join-Builder", "settings.json");

    public static BuilderSettings Load()
    {
        try
        {
            if (File.Exists(FilePath))
                return JsonSerializer.Deserialize<BuilderSettings>(File.ReadAllText(FilePath)) ?? new();
        }
        catch
        {
            // Defekte Datei: mit leeren Einstellungen starten.
        }
        return new();
    }

    public static void Save(BuilderSettings settings)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllText(FilePath, JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true }));
    }
}
