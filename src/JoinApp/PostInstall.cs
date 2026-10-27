using System.Diagnostics;
using System.Net;
using System.Text;
using Lkds.Join.Shared;
using Microsoft.Win32;

namespace Lkds.Join.JoinApp;

/// <summary>
/// Phase 2: läuft ohne Fenster als SYSTEM beim Systemstart nach dem Join. Startet ZENworks und Bitdefender
/// gleichzeitig und räumt danach alles auf (Programme, Task, Registry-Marke, Log und die EXE selbst).
/// Der ZENworks-Neustart mitten in der Installation ist eingeplant: der Task läuft beim nächsten Start erneut
/// und macht anhand der Marke in der Registry dort weiter.
/// </summary>
static class PostInstall
{
    const string LdsDir = @"C:\LDS";
    const string KeyPath = @"SOFTWARE\LKDS-Join";

    static readonly (string Path, string Args)[] Programs =
    {
        (LdsDir + @"\zenworks.exe", ""),
        (LdsDir + @"\bitdef\epskit_x64.exe", "/silent /bdparams"),
    };

    // Frühestens nach so langer Zeit gilt die Installation als fertig (ZENworks startet nach ca. 5 Minuten neu).
    static readonly TimeSpan MinAge = TimeSpan.FromMinutes(8);
    // Ohne Erkennung in der Programmliste räumen wir nach dieser Zeit trotzdem auf, sofern kein Installer mehr läuft.
    static readonly TimeSpan FallbackAge = TimeSpan.FromMinutes(20);
    // Spätestens dann wird in jedem Fall aufgeräumt.
    static readonly TimeSpan MaxAge = TimeSpan.FromMinutes(90);
    const int MaxBoots = 5;

    static readonly string[] InstallerProcesses = { "zenworks", "epskit_x64", "epskit_x86", "setupdownloader" };

    /// <summary>Vor dem Neustart (Phase 1): Task anlegen und merken, was später aufgeräumt werden muss.</summary>
    public static void Register()
    {
        string exe = Environment.ProcessPath!;
        using (var key = Registry.LocalMachine.CreateSubKey(KeyPath))
            key.SetValue("ExtractDir", ExtractDir(), RegistryValueKind.String);
        Autostart.RegisterPost(exe);
        Log.Write("Autostart-Task angelegt");
    }

    public static void Run()
    {
        try
        {
            using var key = Registry.LocalMachine.CreateSubKey(KeyPath);
            int boots = key.GetValue("Boots") is int b ? b + 1 : 1;
            key.SetValue("Boots", boots, RegistryValueKind.DWord);
            long started = key.GetValue("Started") is long s ? s : 0;
            Log.Write($"Phase 2, Start Nr. {boots}");

            if (boots <= MaxBoots)
            {
                if (started == 0)
                {
                    WaitForDomain();
                    StartPrograms();
                    started = DateTime.UtcNow.Ticks;
                    key.SetValue("Started", started, RegistryValueKind.QWord);
                }
                WaitUntilDone(new DateTime(started, DateTimeKind.Utc));
            }
        }
        catch (Exception ex)
        {
            Log.Write("Phase 2 fehlgeschlagen: " + ex.Message);
        }
        // Auch bei Fehlern wird alles entfernt – dann wird von Hand installiert.
        Cleanup();
    }

    static void WaitForDomain()
    {
        string? domain = null;
        try { domain = ConfigPayload.ReadFrom(Environment.ProcessPath!)?.Domain; } catch { }

        var deadline = DateTime.UtcNow.AddMinutes(3);
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                if (DomainJoin.IsDomainMember() && (domain == null || Dns.GetHostEntry(domain).AddressList.Length > 0)) return;
            }
            catch { }
            Thread.Sleep(5_000);
        }
        Log.Write("Domäne/Netz nach 3 Minuten nicht erreichbar, es wird trotzdem fortgefahren");
    }

    static void StartPrograms()
    {
        foreach (var (path, args) in Programs)
        {
            try
            {
                if (!File.Exists(path)) throw new FileNotFoundException($"Programm nicht gefunden: {path}");
                Process.Start(new ProcessStartInfo(path, args)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(path)!,
                })?.Dispose();
                Log.Write($"Programm gestartet: {path} {args}".TrimEnd());
            }
            catch (Exception ex)
            {
                Log.Write("Start fehlgeschlagen: " + ex.Message);
            }
        }
    }

    static void WaitUntilDone(DateTime started)
    {
        while (true)
        {
            var age = DateTime.UtcNow - started;
            if (age >= MaxAge) return;
            if (age >= MinAge && !InstallersRunning()
                && ((IsInstalled("Bitdefender") && IsInstalled("ZENworks")) || age >= FallbackAge))
                return;
            Thread.Sleep(15_000);
        }
    }

    static bool InstallersRunning()
    {
        foreach (var p in Process.GetProcesses())
        {
            using (p)
            {
                try
                {
                    if (InstallerProcesses.Contains(p.ProcessName, StringComparer.OrdinalIgnoreCase)) return true;
                    string? path = p.MainModule?.FileName;
                    if (p.Id != Environment.ProcessId && path != null
                        && path.StartsWith(LdsDir + @"\", StringComparison.OrdinalIgnoreCase)) return true;
                }
                catch
                {
                    // Zugriff verweigert (z. B. geschützte Prozesse): ignorieren.
                }
            }
        }
        return false;
    }

    static bool IsInstalled(string namePart)
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            using var hive = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
            using var uninstall = hive.OpenSubKey(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall");
            if (uninstall == null) continue;
            foreach (var sub in uninstall.GetSubKeyNames())
            {
                using var entry = uninstall.OpenSubKey(sub);
                if (entry?.GetValue("DisplayName") is string name && name.Contains(namePart, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
        }
        return false;
    }

    static string ExtractDir() =>
        Path.Combine(Path.GetTempPath(), ".net", Path.GetFileNameWithoutExtension(Environment.ProcessPath!));

    /// <summary>
    /// Die laufende EXE kann sich nicht selbst löschen. Ein separater, einmaliger Task (SYSTEM) führt ein
    /// Skript aus, das wartet, bis die EXE beendet ist, und dann alles entfernt – auch Task und Skript selbst.
    /// </summary>
    static void Cleanup()
    {
        try
        {
            string exe = Environment.ProcessPath!;
            var extractDirs = new List<string> { ExtractDir() };
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(KeyPath);
                if (key?.GetValue("ExtractDir") is string dir) extractDirs.Add(dir);
                Registry.LocalMachine.DeleteSubKeyTree(KeyPath, throwOnMissingSubKey: false);
            }
            catch (Exception ex) { Log.Write("Registry-Marke nicht entfernt: " + ex.Message); }

            var sb = new StringBuilder();
            sb.AppendLine("@echo off");
            sb.AppendLine("ping -n 11 127.0.0.1 >nul");
            sb.AppendLine("set n=0");
            sb.AppendLine(":retry");
            sb.AppendLine($"del /f /q \"{exe}\" >nul 2>&1");
            sb.AppendLine($"del /f /q \"{LdsDir}\\zenworks.exe\" >nul 2>&1");
            foreach (var reg in StartupFiles.Regs) sb.AppendLine($"del /f /q \"{LdsDir}\\{reg}\" >nul 2>&1");
            sb.AppendLine($"rd /s /q \"{LdsDir}\\bitdef\" >nul 2>&1");
            foreach (var dir in extractDirs.Distinct(StringComparer.OrdinalIgnoreCase))
                sb.AppendLine($"rd /s /q \"{dir}\" >nul 2>&1");
            sb.AppendLine($"if not exist \"{exe}\" if not exist \"{LdsDir}\\bitdef\" goto done");
            sb.AppendLine("set /a n+=1");
            sb.AppendLine("if %n% GEQ 20 goto done");
            sb.AppendLine("ping -n 6 127.0.0.1 >nul");
            sb.AppendLine("goto retry");
            sb.AppendLine(":done");
            // Nur leere Ordner entfernen, damit nichts anderes in C:\LDS verloren geht.
            sb.AppendLine($"rd \"{LdsDir}\\REG\" >nul 2>&1");
            sb.AppendLine($"rd \"{LdsDir}\" >nul 2>&1");
            sb.AppendLine($"rd /s /q \"{Path.GetDirectoryName(LogPath())}\" >nul 2>&1");
            sb.AppendLine($"schtasks /Delete /TN \"{Autostart.PostTask}\" /F >nul 2>&1");
            sb.AppendLine($"schtasks /Delete /TN \"{Autostart.CleanupTask}\" /F >nul 2>&1");
            sb.AppendLine("(goto) 2>nul & del \"%~f0\"");

            string script = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp", "lkds-cleanup.cmd");
            File.WriteAllText(script, sb.ToString(), Encoding.Default);
            Autostart.RegisterOnDemand(Autostart.CleanupTask, script);
            Autostart.RunNow(Autostart.CleanupTask);
        }
        catch (Exception ex)
        {
            Log.Write("Aufräumen fehlgeschlagen: " + ex.Message);
        }
    }

    static string LogPath() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "LKDS-Join", "join.log");
}
