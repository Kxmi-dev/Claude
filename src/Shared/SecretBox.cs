using System.Security.Cryptography;
using System.Text;

namespace Lkds.Shared;

/// <summary>
/// Verschlüsselt kurze Texte (AES-256-CBC, danach HMAC-SHA256 zur Manipulationserkennung).
/// WICHTIG: Der Schlüssel liegt in derselben EXE wie der verschlüsselte Text. Das schützt vor
/// Lesen mit dem Texteditor oder "strings", nicht vor jemandem, der die EXE gezielt analysiert.
/// </summary>
public static class SecretBox
{
    private const int IvSize = 16;
    private const int MacSize = 32;

    public static byte[] NewKey()
    {
        var key = new byte[32];
        using var rng = RandomNumberGenerator.Create();
        rng.GetBytes(key);
        return key;
    }

    public static byte[] Seal(string plainText, byte[] key)
    {
        var iv = new byte[IvSize];
        using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(iv);

        byte[] cipher;
        using (var aes = Aes.Create())
        {
            aes.Key = Derive(key, "enc");
            aes.IV = iv;
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;
            var data = Encoding.UTF8.GetBytes(plainText);
            using var enc = aes.CreateEncryptor();
            cipher = enc.TransformFinalBlock(data, 0, data.Length);
        }

        var body = new byte[IvSize + cipher.Length];
        iv.CopyTo(body, 0);
        cipher.CopyTo(body, IvSize);

        var result = new byte[body.Length + MacSize];
        body.CopyTo(result, 0);
        Mac(key, body).CopyTo(result, body.Length);
        return result;
    }

    /// <summary>Gibt den Klartext zurück oder null, wenn Schlüssel oder Daten nicht passen.</summary>
    public static string? Open(byte[] sealedData, byte[] key)
    {
        if (sealedData.Length < IvSize + 16 + MacSize) return null;

        var bodyLength = sealedData.Length - MacSize;
        var body = new byte[bodyLength];
        System.Array.Copy(sealedData, body, bodyLength);

        var expected = Mac(key, body);
        var diff = 0;
        for (var i = 0; i < MacSize; i++) diff |= expected[i] ^ sealedData[bodyLength + i];
        if (diff != 0) return null;

        var iv = new byte[IvSize];
        System.Array.Copy(body, iv, IvSize);
        var cipher = new byte[bodyLength - IvSize];
        System.Array.Copy(body, IvSize, cipher, 0, cipher.Length);

        try
        {
            using var aes = Aes.Create();
            aes.Key = Derive(key, "enc");
            aes.IV = iv;
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;
            using var dec = aes.CreateDecryptor();
            return Encoding.UTF8.GetString(dec.TransformFinalBlock(cipher, 0, cipher.Length));
        }
        catch (CryptographicException)
        {
            return null;
        }
    }

    private static byte[] Derive(byte[] key, string purpose)
    {
        using var sha = SHA256.Create();
        var tag = Encoding.ASCII.GetBytes(purpose);
        var input = new byte[key.Length + tag.Length];
        key.CopyTo(input, 0);
        tag.CopyTo(input, key.Length);
        return sha.ComputeHash(input);
    }

    private static byte[] Mac(byte[] key, byte[] data)
    {
        using var hmac = new HMACSHA256(Derive(key, "mac"));
        return hmac.ComputeHash(data);
    }
}
