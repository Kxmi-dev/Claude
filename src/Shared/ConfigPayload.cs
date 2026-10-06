using System.Text;
using System.Text.Json;

namespace Lkds.Shared;

/// <summary>
/// Hängt die Konfiguration als JSON an das Ende einer EXE an und liest sie wieder aus.
/// Aufbau am Dateiende: [JSON (UTF-8)] [Länge als Int32] [Kennung "LKDSCFG1"].
/// Windows ignoriert angehängte Daten, die EXE läuft unverändert.
/// </summary>
public static class ConfigPayload
{
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("LKDSCFG1");

    public static byte[] Build(JoinConfig config)
    {
        var json = JsonSerializer.SerializeToUtf8Bytes(config);
        using var ms = new MemoryStream();
        ms.Write(json);
        ms.Write(BitConverter.GetBytes(json.Length));
        ms.Write(Magic);
        return ms.ToArray();
    }

    public static void AppendTo(string exePath, JoinConfig config)
    {
        using var fs = new FileStream(exePath, FileMode.Append, FileAccess.Write);
        fs.Write(Build(config));
    }

    /// <summary>Liest die Konfiguration vom Ende der Datei. Gibt null zurück, wenn keine eingebettet ist.</summary>
    public static JoinConfig? ReadFrom(string exePath)
    {
        using var fs = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        var trailer = Magic.Length + sizeof(int);
        if (fs.Length < trailer) return null;

        var tail = new byte[trailer];
        fs.Seek(-trailer, SeekOrigin.End);
        fs.ReadExactly(tail);
        if (!tail.AsSpan(sizeof(int)).SequenceEqual(Magic)) return null;

        var length = BitConverter.ToInt32(tail, 0);
        if (length <= 0 || length > fs.Length - trailer) return null;

        var json = new byte[length];
        fs.Seek(-(trailer + length), SeekOrigin.End);
        fs.ReadExactly(json);
        return JsonSerializer.Deserialize<JoinConfig>(json);
    }
}
