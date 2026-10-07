using System.IO;
using System.Text;

namespace Lkds.Shared;

/// <summary>
/// Hängt die Konfiguration als einfachen Text ("Schlüssel=Wert", eine Zeile pro Eintrag) an das Ende
/// einer EXE an und liest sie wieder aus. Bewusst kein JSON, damit die Join-EXE ohne Zusatzbibliothek
/// winzig bleibt. Aufbau am Dateiende: [Text (UTF-8)] [Länge als Int32] [Kennung "LKDSCFG2"].
/// Windows ignoriert angehängte Daten, die EXE läuft unverändert.
/// </summary>
public static class ConfigPayload
{
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("LKDSCFG2");
    private const char Separator = '\t';

    public static byte[] Build(JoinConfig config)
    {
        var sb = new StringBuilder();
        sb.Append("Domain=").Append(config.Domain).Append('\n');
        sb.Append("BaseOu=").Append(config.BaseOu).Append('\n');
        foreach (var user in config.Users) sb.Append("User=").Append(user).Append('\n');
        foreach (var l in config.Locations) sb.Append("Location=").Append(l.Name).Append(Separator).Append(l.Dn).Append('\n');
        if (config.RunLdsSteps) sb.Append("LdsSteps=1\n");
        if (config.PostScript is { Length: > 0 }) sb.Append("Script=").Append(Convert.ToBase64String(config.PostScript)).Append('\n');

        var text = Encoding.UTF8.GetBytes(sb.ToString());
        var result = new byte[text.Length + sizeof(int) + Magic.Length];
        text.CopyTo(result, 0);
        BitConverter.GetBytes(text.Length).CopyTo(result, text.Length);
        Magic.CopyTo(result, text.Length + sizeof(int));
        return result;
    }

    public static void AppendTo(string exePath, JoinConfig config)
    {
        var data = Build(config);
        using var fs = new FileStream(exePath, FileMode.Append, FileAccess.Write);
        fs.Write(data, 0, data.Length);
    }

    /// <summary>Liest die Konfiguration vom Ende der Datei. Gibt null zurück, wenn keine eingebettet ist.</summary>
    public static JoinConfig? ReadFrom(string exePath)
    {
        using var fs = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        var trailerSize = Magic.Length + sizeof(int);
        if (fs.Length < trailerSize) return null;

        var tail = ReadAt(fs, fs.Length - trailerSize, trailerSize);
        for (var i = 0; i < Magic.Length; i++)
            if (tail[sizeof(int) + i] != Magic[i]) return null;

        var length = BitConverter.ToInt32(tail, 0);
        if (length <= 0 || length > fs.Length - trailerSize) return null;

        var text = Encoding.UTF8.GetString(ReadAt(fs, fs.Length - trailerSize - length, length));
        return Parse(text);
    }

    private static JoinConfig Parse(string text)
    {
        string domain = "", baseOu = "";
        var users = new List<string>();
        var locations = new List<LocationEntry>();
        byte[]? script = null;
        var ldsSteps = false;

        foreach (var line in text.Split('\n'))
        {
            var eq = line.IndexOf('=');
            if (eq < 0) continue;
            var key = line.Substring(0, eq);
            var value = line.Substring(eq + 1);
            switch (key)
            {
                case "Domain": domain = value; break;
                case "BaseOu": baseOu = value; break;
                case "User": users.Add(value); break;
                case "LdsSteps": ldsSteps = value == "1"; break;
                case "Script": script = Convert.FromBase64String(value); break;
                case "Location":
                    var parts = value.Split(Separator);
                    if (parts.Length == 2) locations.Add(new LocationEntry(parts[0], parts[1]));
                    break;
            }
        }
        return new JoinConfig(domain, baseOu, users.ToArray(), locations.ToArray(), script, ldsSteps);
    }

    private static byte[] ReadAt(FileStream fs, long position, int count)
    {
        var buffer = new byte[count];
        fs.Seek(position, SeekOrigin.Begin);
        var read = 0;
        while (read < count)
        {
            var n = fs.Read(buffer, read, count - read);
            if (n <= 0) throw new EndOfStreamException();
            read += n;
        }
        return buffer;
    }
}
