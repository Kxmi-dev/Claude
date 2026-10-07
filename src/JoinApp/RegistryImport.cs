using System.Collections.Generic;
using System.IO;

namespace Lkds.JoinApp;

public static class RegistryImport
{
    /// <summary>
    /// Importiert die .reg-Dateien der Reihe nach (reg.exe, in System32, damit auch ein 32-Bit-Aufruf die 64-Bit-Registry trifft).
    /// Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung. imported listet die erfolgreich importierten Dateinamen.
    /// </summary>
    public static string? Import(IEnumerable<string> files, List<string> imported)
    {
        var reg = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "sysnative", "reg.exe");
        if (!File.Exists(reg)) reg = Path.Combine(Environment.SystemDirectory, "reg.exe");

        foreach (var file in files)
        {
            if (!File.Exists(file)) return $"Datei nicht gefunden: {file}";
            var error = Tools.Run(reg, "import", file);
            if (error is not null) return $"Import von {file} fehlgeschlagen: {error}";
            imported.Add(Path.GetFileName(file));
        }
        return null;
    }
}
