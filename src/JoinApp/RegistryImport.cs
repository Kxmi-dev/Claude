using System.Collections.Generic;
using System.IO;

namespace Lkds.JoinApp;

public static class RegistryImport
{
    /// <summary>Importiert die .reg-Dateien der Reihe nach. Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung.</summary>
    public static string? Import(IEnumerable<string> files)
    {
        foreach (var file in files)
        {
            if (!File.Exists(file)) return $"Datei nicht gefunden: {file}";
            var error = Tools.Run("reg", "import", file);
            if (error is not null) return $"Import von {file} fehlgeschlagen: {error}";
        }
        return null;
    }
}
