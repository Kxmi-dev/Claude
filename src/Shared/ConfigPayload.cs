using System.Text;
using System.Text.Json;

namespace Lkds.Join.Shared;

/// <summary>
/// Die Konfiguration steht als JSON am Ende der EXE:
/// [JSON][4 Byte Länge][8 Byte Kennung]. Windows ignoriert angehängte Daten beim Start.
/// </summary>
public static class ConfigPayload
{
    static readonly byte[] Magic = Encoding.ASCII.GetBytes("LKDSJOIN");
    static readonly int FooterSize = sizeof(int) + Magic.Length;

    public static void Append(string exePath, JoinConfig config)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(config);
        using var fs = new FileStream(exePath, FileMode.Append, FileAccess.Write);
        fs.Write(json);
        fs.Write(BitConverter.GetBytes(json.Length));
        fs.Write(Magic);
    }

    /// <summary>Liefert null, wenn die EXE keine Konfiguration enthält (z. B. die Vorlage selbst).</summary>
    public static JoinConfig? ReadFrom(string exePath)
    {
        using var fs = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        if (fs.Length < FooterSize) return null;

        var footer = new byte[FooterSize];
        fs.Seek(-FooterSize, SeekOrigin.End);
        fs.ReadExactly(footer);
        if (!footer.AsSpan(sizeof(int)).SequenceEqual(Magic)) return null;

        int length = BitConverter.ToInt32(footer, 0);
        if (length <= 0 || length > fs.Length - FooterSize) return null;

        var json = new byte[length];
        fs.Seek(-(FooterSize + length), SeekOrigin.End);
        fs.ReadExactly(json);
        return JsonSerializer.Deserialize<JoinConfig>(json);
    }
}
