using System.Diagnostics;
using System.Security;
using System.Text;

namespace Lkds.Join.JoinApp;

/// <summary>Geplante Tasks (SYSTEM) über schtasks.exe. Laufen auch ohne angemeldeten Benutzer und im Akkubetrieb.</summary>
static class Autostart
{
    public const string PostTask = "LKDS-Join-Post";
    public const string CleanupTask = "LKDS-Join-Cleanup";

    /// <summary>Task, der beim Systemstart die EXE mit --post startet.</summary>
    public static void RegisterPost(string exePath) => Create(PostTask, exePath, "--post", atBoot: true);

    /// <summary>Task ohne Trigger, der nur auf Abruf läuft (siehe <see cref="RunNow"/>).</summary>
    public static void RegisterOnDemand(string name, string command) => Create(name, command, "", atBoot: false);

    public static void RunNow(string name) => Schtasks("/Run", "/TN", name);

    static void Create(string name, string command, string arguments, bool atBoot)
    {
        string trigger = atBoot ? "<Triggers><BootTrigger><Enabled>true</Enabled><Delay>PT30S</Delay></BootTrigger></Triggers>" : "";
        string args = arguments.Length > 0 ? $"<Arguments>{SecurityElement.Escape(arguments)}</Arguments>" : "";
        string xml = $"""
            <?xml version="1.0" encoding="UTF-16"?>
            <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
              {trigger}
              <Principals><Principal id="Author"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
              <Settings>
                <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
                <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
                <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
                <AllowStartOnDemand>true</AllowStartOnDemand>
                <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
                <Enabled>true</Enabled>
              </Settings>
              <Actions Context="Author">
                <Exec>
                  <Command>{SecurityElement.Escape(command)}</Command>
                  {args}
                  <WorkingDirectory>{SecurityElement.Escape(Path.GetDirectoryName(command) ?? "")}</WorkingDirectory>
                </Exec>
              </Actions>
            </Task>
            """;

        string temp = Path.Combine(Path.GetTempPath(), "lkds-" + Guid.NewGuid().ToString("N") + ".xml");
        File.WriteAllText(temp, xml, Encoding.Unicode);
        try { Schtasks("/Create", "/TN", name, "/XML", temp, "/F"); }
        finally { try { File.Delete(temp); } catch { } }
    }

    static void Schtasks(params string[] args)
    {
        var psi = new ProcessStartInfo("schtasks.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (var a in args) psi.ArgumentList.Add(a);
        using var p = Process.Start(psi)!;
        string output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
        if (!p.WaitForExit(30_000)) throw new TimeoutException("schtasks.exe hat zu lange gedauert.");
        if (p.ExitCode != 0) throw new InvalidOperationException($"schtasks.exe (Code {p.ExitCode}): {output.Trim()}");
    }
}
