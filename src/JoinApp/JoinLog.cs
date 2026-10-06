using System.IO;

namespace Lkds.JoinApp;

/// <summary>Einfaches Textlog unter C:\ProgramData\LKDS-Join\join.log. Enthält nie Passwörter.</summary>
public static class JoinLog
{
    private static readonly string Folder =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "LKDS-Join");

    public static void Write(string computer, string user, string location, string targetOu, string result, string details)
    {
        try
        {
            Directory.CreateDirectory(Folder);
            var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} | Computer={computer} | Benutzer={user} | " +
                       $"Standort={location} | OU={targetOu} | Ergebnis={result} | {details}";
            File.AppendAllText(Path.Combine(Folder, "join.log"), line + Environment.NewLine);
        }
        catch
        {
            // Ein Logfehler darf den Join nicht verhindern.
        }
    }
}
