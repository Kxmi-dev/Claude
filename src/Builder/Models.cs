namespace Lkds.Join.Builder;

/// <summary>Eintrag einer Checkbox-Liste (Standort oder Benutzer).</summary>
public class CheckItem
{
    public string Name { get; set; } = "";
    public string Dn { get; set; } = "";
    public bool IsSelected { get; set; }
}

/// <summary>Profil: nur nicht-sensitive Werte, niemals ein Passwort.</summary>
public class Profile
{
    public string Name { get; set; } = "";
    public string Domain { get; set; } = "";
    public string BaseOu { get; set; } = "";
    public List<string> Users { get; set; } = new();
    public List<string> Locations { get; set; } = new();
}

/// <summary>Lokale Builder-Einstellungen (%AppData%\LKDS-Join-Builder\settings.json).</summary>
public class BuilderSettings
{
    public List<Profile> Profiles { get; set; } = new();
    public List<string> KnownUsers { get; set; } = new();
    public string RegFolder { get; set; } = @"C:\LDS";
}
