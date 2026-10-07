using System.DirectoryServices;
using System.Runtime.InteropServices;

namespace Lkds.Join.Builder;

static class AdDirectory
{
    /// <summary>
    /// Liest die OUs direkt unterhalb der Basis-OU. Ohne Passwort wird die aktuelle Windows-Anmeldung verwendet.
    /// </summary>
    public static List<CheckItem> LoadLocations(string domain, string baseOu, string user, string password)
    {
        string path = $"LDAP://{domain}/{baseOu}";
        using var root = password.Length == 0
            ? new DirectoryEntry(path, null, null, AuthenticationTypes.Secure)
            : new DirectoryEntry(path, user.Contains('@') || user.Contains('\\') ? user : $"{user}@{domain}", password, AuthenticationTypes.Secure);
        using var searcher = new DirectorySearcher(root)
        {
            Filter = "(objectClass=organizationalUnit)",
            SearchScope = SearchScope.OneLevel,
            PropertiesToLoad = { "ou", "distinguishedName" },
        };
        using var results = searcher.FindAll();

        var list = new List<CheckItem>();
        foreach (SearchResult r in results)
            list.Add(new CheckItem
            {
                Name = (string)r.Properties["ou"][0]!,
                Dn = (string)r.Properties["distinguishedName"][0]!,
            });
        return list.OrderBy(i => i.Name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    public static string FriendlyMessage(Exception ex) => ex switch
    {
        COMException c when c.HResult == unchecked((int)0x8007052E) => "Benutzername oder Passwort ist nicht korrekt.",
        COMException c when c.HResult == unchecked((int)0x80070005) => "Für diesen Benutzer fehlen die erforderlichen Berechtigungen.",
        COMException c when c.HResult == unchecked((int)0x80072030) => "Die Basis-OU wurde nicht gefunden.",
        COMException => "Keine Verbindung zum Active Directory möglich.",
        _ => "Die Abfrage des Active Directory ist fehlgeschlagen.",
    };
}
