using System.DirectoryServices;
using System.Runtime.InteropServices;
using Lkds.Shared;

namespace Lkds.Builder;

/// <summary>Liest die OUs direkt unterhalb der Basis-OU aus dem Active Directory.</summary>
public static class AdReader
{
    /// <summary>user/password = null: es wird das aktuell angemeldete Windows-Konto verwendet.</summary>
    public static List<LocationEntry> ReadLocations(string domain, string baseOu, string? user, string? password)
    {
        var path = $"LDAP://{domain}/{baseOu}";
        using var root = user is null
            ? new DirectoryEntry(path)
            : new DirectoryEntry(path, $"{domain}\\{user}", password, AuthenticationTypes.Secure);
        using var searcher = new DirectorySearcher(root)
        {
            Filter = "(objectClass=organizationalUnit)",
            SearchScope = SearchScope.OneLevel,
            PageSize = 500
        };
        searcher.PropertiesToLoad.Add("ou");
        searcher.PropertiesToLoad.Add("distinguishedName");

        var result = new List<LocationEntry>();
        using var hits = searcher.FindAll();
        foreach (SearchResult hit in hits)
        {
            var name = hit.Properties["ou"][0]?.ToString();
            var dn = hit.Properties["distinguishedName"][0]?.ToString();
            if (name is not null && dn is not null) result.Add(new LocationEntry(name, dn));
        }
        return result.OrderBy(l => l.Name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    /// <summary>Übersetzt typische AD-Fehler in eine verständliche Meldung.</summary>
    public static string Describe(Exception ex) => ex switch
    {
        DirectoryServicesCOMException { ExtendedError: 0x52E } or
        COMException { HResult: unchecked((int)0x8007052E) } => "Benutzername oder Passwort sind nicht korrekt.",
        DirectoryServicesCOMException { ExtendedError: 0x525 } => "Der Benutzer wurde nicht gefunden.",
        COMException { HResult: unchecked((int)0x80072030) } => "Die Basis-OU wurde nicht gefunden.",
        COMException { HResult: unchecked((int)0x8007203A) } or
        COMException { HResult: unchecked((int)0x8007054B) } => "Keine Verbindung zum Active Directory möglich.",
        _ => "Keine Verbindung zum Active Directory möglich."
    };
}
