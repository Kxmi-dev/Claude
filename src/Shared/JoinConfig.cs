namespace Lkds.Shared;

/// <summary>Ein Standort mit vollständigem Distinguished Name der Ziel-OU.</summary>
public record LocationEntry(string Name, string Dn);

/// <summary>
/// Konfiguration, die der Builder in die Join-EXE einbettet.
/// Enthält bewusst keine Passwörter. PostScript ist der Inhalt einer optionalen .bat,
/// die nach dem Neustart einmalig als SYSTEM ausgeführt wird.
/// </summary>
public record JoinConfig(
    string Domain,
    string BaseOu,
    string[] Users,
    LocationEntry[] Locations,
    byte[]? PostScript = null);
