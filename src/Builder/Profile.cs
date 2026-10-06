using System.IO;
using System.Text.Json;

namespace Lkds.Builder;

/// <summary>Nicht-sensible Einstellungen. Enthält nie ein Passwort.</summary>
public class Profile
{
    public string Name { get; set; } = "";
    public string Domain { get; set; } = Defaults.Domain;
    public string BaseOu { get; set; } = Defaults.BaseOu;
    public List<string> Users { get; set; } = [];
    public List<string> SelectedUsers { get; set; } = [];
    public List<string> SelectedLocations { get; set; } = [];
}

public static class Defaults
{
    public const string Domain = "ad.lkds.de";
    public const string BaseOu = "OU=PCs,OU=Computer,OU=LKDS,DC=ad,DC=lkds,DC=de";
    public const string StandardUser = "test-wadm";
}

/// <summary>Speichert die Profile als eine kleine JSON-Datei unter %AppData%\LKDS-AD-Join-Builder.</summary>
public static class ProfileStore
{
    private static readonly string FilePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "LKDS-AD-Join-Builder", "profile.json");

    private static readonly JsonSerializerOptions Options = new() { WriteIndented = true };

    public static List<Profile> Load()
    {
        try
        {
            if (File.Exists(FilePath))
            {
                var list = JsonSerializer.Deserialize<List<Profile>>(File.ReadAllText(FilePath));
                if (list is { Count: > 0 }) return list;
            }
        }
        catch
        {
            // Defekte Datei: mit Standardprofil neu beginnen.
        }
        return [new Profile { Name = "Standard", Users = [Defaults.StandardUser], SelectedUsers = [Defaults.StandardUser] }];
    }

    public static void Save(List<Profile> profiles)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllText(FilePath, JsonSerializer.Serialize(profiles, Options));
    }
}
