namespace Lkds.Join.Shared;

public class JoinLocation
{
    public string Name { get; set; } = "";
    public string Dn { get; set; } = "";
}

/// <summary>Nicht-sensitive Konfiguration, die der Builder in die Join-EXE einbettet. Enthält nie ein Passwort.</summary>
public class JoinConfig
{
    public string Domain { get; set; } = "";
    public string BaseOu { get; set; } = "";
    public List<string> Users { get; set; } = new();
    public List<JoinLocation> Locations { get; set; } = new();
}
