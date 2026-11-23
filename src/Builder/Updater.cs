using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;

namespace Lkds.Builder;

public record UpdateInfo(string Version, string File, string Sha256, long Size, List<string> Changes);

/// <summary>Holt neue Builder-Versionen von der Download-Seite (pxe.krauses.selfhost.co) und ersetzt die laufende EXE.</summary>
public static class Updater
{
    private const string BaseUrl = "https://pxe.krauses.selfhost.co/update/join-builder/";

    public static string CurrentVersion
    {
        get
        {
            var v = Assembly.GetExecutingAssembly().GetName().Version;
            return v is null ? "0.0.0" : $"{v.Major}.{v.Minor}.{v.Build}";
        }
    }

    private static string Meta(string key) =>
        Assembly.GetExecutingAssembly().GetCustomAttributes<AssemblyMetadataAttribute>()
            .FirstOrDefault(a => a.Key == key)?.Value ?? "";

    private static HttpClient NewClient()
    {
        var key = Meta("UpdateKey");
        if (key.Length == 0) throw new InvalidOperationException("Dieser Build enthält keinen Update-Schlüssel. Bitte über release-builder.sh bauen.");
        var c = new HttpClient { Timeout = TimeSpan.FromMinutes(5) };
        c.DefaultRequestHeaders.Add("X-Update-Key", key);
        return c;
    }

    /// <summary>Neueste Version laut Server, oder null wenn die laufende schon aktuell ist.</summary>
    public static async Task<UpdateInfo?> CheckAsync()
    {
        using var c = NewClient();
        var json = await c.GetStringAsync(BaseUrl + "manifest.json");
        var info = JsonSerializer.Deserialize<UpdateInfo>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                   ?? throw new InvalidOperationException("Die Update-Angaben sind leer.");
        return Version.TryParse(info.Version, out var n) && Version.TryParse(CurrentVersion, out var cur) && n > cur ? info : null;
    }

    /// <summary>Lädt die neue EXE, prüft die Prüfsumme, tauscht sie gegen die laufende aus und startet sie neu.</summary>
    public static async Task InstallAsync(UpdateInfo info)
    {
        var exe = Environment.ProcessPath ?? throw new InvalidOperationException("Pfad der EXE unbekannt.");
        if (info.File.IndexOfAny(['/', '\\']) >= 0) throw new InvalidOperationException("Ungültiger Dateiname im Update.");
        var neu = exe + ".neu";
        using (var c = NewClient())
        using (var resp = await c.GetAsync(BaseUrl + "files/" + info.File, HttpCompletionOption.ResponseHeadersRead))
        {
            resp.EnsureSuccessStatusCode();
            await using var fs = File.Create(neu);
            await resp.Content.CopyToAsync(fs);
        }
        string hash;
        await using (var fs = File.OpenRead(neu)) hash = Convert.ToHexString(await SHA256.HashDataAsync(fs));
        if (!hash.Equals(info.Sha256, StringComparison.OrdinalIgnoreCase))
        {
            File.Delete(neu);
            throw new InvalidOperationException("Die Prüfsumme der heruntergeladenen Datei stimmt nicht. Update abgebrochen.");
        }
        // Eine laufende EXE lässt sich umbenennen, aber nicht überschreiben.
        File.Move(exe, exe + ".alt", true);
        File.Move(neu, exe);
        Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true });
        Application.Current.Shutdown();
    }

    /// <summary>Räumt die Reste eines früheren Updates auf.</summary>
    public static void CleanupOld()
    {
        try
        {
            var exe = Environment.ProcessPath;
            if (exe is not null && File.Exists(exe + ".alt")) File.Delete(exe + ".alt");
        }
        catch { /* wird beim nächsten Start nochmal versucht */ }
    }
}
