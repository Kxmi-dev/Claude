namespace Lkds.Join.JoinApp;

/// <summary>Einfaches Textlog unter %ProgramData%\LKDS-Join\join.log. Schreibt niemals Passwörter.</summary>
static class Log
{
    static readonly string FilePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "LKDS-Join", "join.log");

    public static void Write(string message)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
            File.AppendAllText(FilePath, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{Environment.MachineName}] {message}{Environment.NewLine}");
        }
        catch
        {
            // Logging darf den Join nie verhindern.
        }
    }
}
