namespace Lkds.Shared;

/// <summary>Ein Standort mit vollständigem Distinguished Name der Ziel-OU.</summary>
public class LocationEntry
{
    public string Name { get; }
    public string Dn { get; }

    public LocationEntry(string name, string dn)
    {
        Name = name;
        Dn = dn;
    }
}

/// <summary>
/// Konfiguration, die der Builder in die Join-EXE einbettet.
/// Enthält bewusst keine Passwörter. PostScript ist der Inhalt einer optionalen .bat,
/// die nach dem Neustart einmalig als SYSTEM ausgeführt wird.
/// </summary>
public class JoinConfig
{
    public string Domain { get; }
    public string BaseOu { get; }
    public string[] Users { get; }
    public LocationEntry[] Locations { get; }
    public byte[]? PostScript { get; }
    /// <summary>Fester LDS-Ablauf (Programme starten, Registry importieren) nach dem Neustart.</summary>
    public bool RunLdsSteps { get; }

    public JoinConfig(string domain, string baseOu, string[] users, LocationEntry[] locations, byte[]? postScript = null, bool runLdsSteps = false)
    {
        Domain = domain;
        BaseOu = baseOu;
        Users = users;
        Locations = locations;
        PostScript = postScript;
        RunLdsSteps = runLdsSteps;
    }
}
