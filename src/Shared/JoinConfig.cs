using System.Collections.Generic;

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
/// Passwörter sind nur optional und nur verschlüsselt enthalten (siehe SecretBox). PostScript ist der Inhalt einer optionalen .bat,
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
    /// <summary>Namen der wählbaren DNS-Dateien (C:\LDS\REG\DNS NAME.reg), z. B. LNBE, LNRE, KWBR.</summary>
    public string[] DnsOptions { get; }
    /// <summary>Schlüssel für die optional hinterlegten Passwörter (null, wenn keine hinterlegt sind).</summary>
    public byte[]? Key { get; }
    /// <summary>Benutzername zu verschlüsseltem Passwort. Benutzer ohne Eintrag müssen das Passwort am PC eingeben.</summary>
    public Dictionary<string, byte[]> SealedPasswords { get; }
    /// <summary>Die Join-EXE löscht sich nach erfolgreichem Join selbst.</summary>
    public bool SelfDelete { get; }

    public JoinConfig(string domain, string baseOu, string[] users, LocationEntry[] locations, byte[]? postScript = null, bool runLdsSteps = false, string[]? dnsOptions = null,
        byte[]? key = null, Dictionary<string, byte[]>? sealedPasswords = null,
        bool selfDelete = false)
    {
        Domain = domain;
        BaseOu = baseOu;
        Users = users;
        Locations = locations;
        PostScript = postScript;
        RunLdsSteps = runLdsSteps;
        DnsOptions = dnsOptions ?? new string[0];
        Key = key;
        SelfDelete = selfDelete;
        SealedPasswords = sealedPasswords ?? new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
    }

    public bool HasPassword(string user) => Key is not null && SealedPasswords.ContainsKey(user);

    /// <summary>Entschlüsseltes hinterlegtes Passwort oder null.</summary>
    public string? GetPassword(string user)
    {
        if (Key is null || !SealedPasswords.TryGetValue(user, out var data)) return null;
        return SecretBox.Open(data, Key);
    }
}
