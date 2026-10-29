using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using Lkds.Shared;
using Microsoft.Win32;

namespace Lkds.JoinApp;

/// <summary>
/// Phase 2: läuft ohne Fenster als SYSTEM beim Systemstart nach dem Join (EXE-Kopie mit --post).
/// Startet ZENworks und Bitdefender gleichzeitig und räumt danach alles auf.
/// ZENworks startet mitten in der Installation neu: der Task läuft beim nächsten Start erneut und macht
/// anhand der Marke in der Registry weiter, ohne die Programme nochmal zu starten.
/// </summary>
public static class PostInstall
{
    private const string KeyPath = @"SOFTWARE\LKDS-Join";

    private static readonly string Folder =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "LKDS-Join");

    private static readonly string PostExe = Path.Combine(Folder, "LKDS-Join.exe");
    private static readonly string ScriptFile = Path.Combine(Folder, "zusatz.bat");

    // Frühestens nach so langer Zeit gilt die Installation als fertig (ZENworks startet nach ca. 5 Minuten neu).
    private static readonly TimeSpan MinAge = TimeSpan.FromMinutes(8);
    // Ohne Erkennung in der Programmliste räumen wir nach dieser Zeit trotzdem auf, sofern kein Installer mehr läuft.
    private static readonly TimeSpan FallbackAge = TimeSpan.FromMinutes(20);
    // Spätestens dann wird in jedem Fall aufgeräumt.
    private static readonly TimeSpan MaxAge = TimeSpan.FromMinutes(90);
    private const int MaxBoots = 5;

    private static readonly string[] InstallerProcesses = { "zenworks", "epskit_x64", "epskit_x86", "setupdownloader" };

    private static string CurrentExe => System.Reflection.Assembly.GetExecutingAssembly().Location;

    /// <summary>
    /// Phase 1, vor dem Neustart: Kopie der EXE (ohne Passwörter) auf die lokale Platte legen, Marke setzen, Task anlegen.
    /// Gibt null bei Erfolg zurück, sonst eine Fehlerbeschreibung.
    /// </summary>
    public static string? Register(JoinConfig config)
    {
        try
        {
            Directory.CreateDirectory(Folder);
            // Nur SYSTEM (S-1-5-18) und Administratoren (S-1-5-32-544) dürfen im Ordner schreiben.
            var acl = Tools.Run("icacls", Folder, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F");
            if (acl is not null) return $"Ordner konnte nicht abgesichert werden: {acl}";

            ConfigPayload.CopyWithoutSecrets(CurrentExe, PostExe);

            Registry.LocalMachine.DeleteSubKeyTree(KeyPath, false);
            using (var key = Registry.LocalMachine.CreateSubKey(KeyPath))
            {
                key.SetValue("Original", config.SelfDelete ? CurrentExe : "", RegistryValueKind.String);
                key.SetValue("Boots", 0, RegistryValueKind.DWord);
            }
            return Autostart.RegisterPost(PostExe);
        }
        catch (Exception ex)
        {
            return ex.Message;
        }
    }

    public static void Run()
    {
        try
        {
            var config = ConfigPayload.ReadFrom(CurrentExe);
            using var key = Registry.LocalMachine.CreateSubKey(KeyPath);
            var boots = (key.GetValue("Boots") is int b ? b : 0) + 1;
            key.SetValue("Boots", boots, RegistryValueKind.DWord);
            var started = key.GetValue("Started") is long s ? s : 0L;
            var runLds = config?.RunLdsSteps ?? false;

            if (boots <= MaxBoots)
            {
                if (started == 0)
                {
                    var hasScript = config?.PostScript is { Length: > 0 };
                    if (runLds || hasScript) WaitForDomain(config?.Domain);
                    if (runLds) StartPrograms();
                    if (hasScript) RunScript(config!.PostScript!);
                    started = DateTime.UtcNow.Ticks;
                    key.SetValue("Started", started, RegistryValueKind.QWord);
                }
                if (runLds) WaitUntilDone(new DateTime(started, DateTimeKind.Utc));
            }
        }
        catch
        {
            // Auch bei Fehlern wird alles entfernt, dann wird von Hand installiert.
        }
        Cleanup();
    }

    private static void WaitForDomain(string? domain)
    {
        var deadline = DateTime.UtcNow.AddMinutes(3);
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                if (DomainJoiner.GetCurrentDomain() is not null &&
                    (string.IsNullOrEmpty(domain) || Dns.GetHostEntry(domain).AddressList.Length > 0))
                    return;
            }
            catch
            {
                // Netz noch nicht da: weiter warten.
            }
            Thread.Sleep(5000);
        }
    }

    private static void StartPrograms()
    {
        foreach (var (path, args) in LdsSteps.Programs)
        {
            try
            {
                if (!File.Exists(path)) continue;
                var psi = new ProcessStartInfo(path, args)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(path)!
                };
                Process.Start(psi)?.Dispose();
            }
            catch
            {
                // Ein Programm, das nicht startet, soll das andere nicht verhindern.
            }
        }
    }

    private static void RunScript(byte[] script)
    {
        try
        {
            File.WriteAllBytes(ScriptFile, script);
            var psi = new ProcessStartInfo("cmd.exe", "/c \"" + ScriptFile + "\"")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = Folder
            };
            using var p = Process.Start(psi)!;
            p.WaitForExit(10 * 60 * 1000);
        }
        catch
        {
            // Das Zusatzskript ist optional.
        }
    }

    private static void WaitUntilDone(DateTime started)
    {
        while (true)
        {
            var age = DateTime.UtcNow - started;
            if (age >= MaxAge) return;
            if (age >= MinAge && !InstallersRunning()
                && ((IsInstalled("Bitdefender") && IsInstalled("ZENworks")) || age >= FallbackAge))
                return;
            Thread.Sleep(15000);
        }
    }

    private static bool InstallersRunning()
    {
        foreach (var p in Process.GetProcesses())
        {
            using (p)
            {
                try
                {
                    if (InstallerProcesses.Contains(p.ProcessName, StringComparer.OrdinalIgnoreCase)) return true;
                    var path = p.MainModule?.FileName;
                    if (p.Id != Process.GetCurrentProcess().Id && path is not null
                        && path.StartsWith(LdsSteps.LdsDir + "\\", StringComparison.OrdinalIgnoreCase)) return true;
                }
                catch
                {
                    // Zugriff verweigert (z. B. geschützte Prozesse): ignorieren.
                }
            }
        }
        return false;
    }

    private static bool IsInstalled(string namePart)
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            using var hive = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
            using var uninstall = hive.OpenSubKey(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall");
            if (uninstall is null) continue;
            foreach (var sub in uninstall.GetSubKeyNames())
            {
                using var entry = uninstall.OpenSubKey(sub);
                if (entry?.GetValue("DisplayName") is string name &&
                    name.IndexOf(namePart, StringComparison.OrdinalIgnoreCase) >= 0)
                    return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Die laufende EXE kann sich nicht selbst löschen. Ein separater, einmaliger Task (SYSTEM) führt ein
    /// Skript aus, das wartet und es mit Wiederholungen versucht, und dabei auch Task und Skript selbst entfernt.
    /// </summary>
    private static void Cleanup()
    {
        string? original = null;
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(KeyPath);
            original = key?.GetValue("Original") as string;
            Registry.LocalMachine.DeleteSubKeyTree(KeyPath, false);
        }
        catch
        {
            // Marke bleibt dann stehen, das Skript unten entfernt sie nochmal.
        }

        try
        {
            var script = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp", "lkds-aufraeumen.cmd");
            File.WriteAllText(script, BuildCleanupScript(original), Encoding.Default);
            Autostart.RegisterOnDemand(Autostart.CleanupTask, script);
            Autostart.RunNow(Autostart.CleanupTask);
        }
        catch
        {
            // Wenn auch das scheitert, bleibt nur die Handarbeit.
        }
    }

    public static string BuildCleanupScript(string? originalExe)
    {
        var sb = new StringBuilder();
        sb.AppendLine("@echo off");
        sb.AppendLine("ping -n 11 127.0.0.1 >nul");
        sb.AppendLine("set n=0");
        sb.AppendLine(":retry");
        sb.AppendLine("set /a n+=1");
        // Der Nachlauf-Task zuerst, damit nach einem Neustart nichts mehr startet.
        sb.AppendLine($"schtasks /Delete /TN \"{Autostart.PostTask}\" /F >nul 2>&1");
        if (!string.IsNullOrEmpty(originalExe)) sb.AppendLine($"del /f /q \"{originalExe}\" >nul 2>&1");
        foreach (var file in LdsSteps.CleanupFiles()) sb.AppendLine($"del /f /q \"{file}\" >nul 2>&1");
        foreach (var dir in LdsSteps.CleanupFolders) sb.AppendLine($"rd /s /q \"{dir}\" >nul 2>&1");
        sb.AppendLine($"rd /s /q \"{Folder}\" >nul 2>&1");
        sb.AppendLine($"reg delete \"HKLM\\{KeyPath}\" /f >nul 2>&1");
        sb.AppendLine($"if not exist \"{Folder}\" if not exist \"{LdsSteps.LdsDir}\\bitdef\" goto done");
        sb.AppendLine("if %n% GEQ 20 goto done");
        sb.AppendLine("ping -n 6 127.0.0.1 >nul");
        sb.AppendLine("goto retry");
        sb.AppendLine(":done");
        // Nur leere Ordner entfernen, damit in C:\LDS nichts anderes verloren geht.
        foreach (var dir in LdsSteps.CleanupFoldersIfEmpty) sb.AppendLine($"rd \"{dir}\" >nul 2>&1");
        sb.AppendLine($"schtasks /Delete /TN \"{Autostart.CleanupTask}\" /F >nul 2>&1");
        sb.AppendLine("(goto) 2>nul & del \"%~f0\"");
        return sb.ToString().Replace("\r\n", "\n").Replace("\n", "\r\n");
    }
}
