using System.IO;
using System.Security;
using System.Text;

namespace Lkds.JoinApp;

/// <summary>Geplante Tasks (SYSTEM) über schtasks.exe. Laufen auch ohne angemeldeten Benutzer und im Akkubetrieb.</summary>
public static class Autostart
{
    public const string PostTask = "LKDS-Join-Nachlauf";
    public const string CleanupTask = "LKDS-Join-Aufraeumen";

    /// <summary>Task, der bei jedem Systemstart (30 Sekunden verzögert) die EXE mit --post startet. Null = ok.</summary>
    public static string? RegisterPost(string exePath) => Create(PostTask, exePath, "--post", true);

    /// <summary>Task ohne Trigger, der nur auf Abruf läuft (siehe <see cref="RunNow"/>).</summary>
    public static string? RegisterOnDemand(string name, string command) => Create(name, command, "", false);

    public static string? RunNow(string name) => Tools.Run("schtasks", "/Run", "/TN", name);

    public static void Delete(string name) => Tools.Run("schtasks", "/Delete", "/TN", name, "/F");

    private static string? Create(string name, string command, string arguments, bool atBoot)
    {
        var trigger = atBoot ? "<Triggers><BootTrigger><Enabled>true</Enabled><Delay>PT30S</Delay></BootTrigger></Triggers>" : "";
        var args = arguments.Length > 0 ? "<Arguments>" + SecurityElement.Escape(arguments) + "</Arguments>" : "";
        var xml =
            "<?xml version=\"1.0\" encoding=\"UTF-16\"?>\n" +
            "<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">\n" +
            "  " + trigger + "\n" +
            "  <Principals><Principal id=\"Author\"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>\n" +
            "  <Settings>\n" +
            "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n" +
            "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n" +
            "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n" +
            "    <AllowStartOnDemand>true</AllowStartOnDemand>\n" +
            "    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>\n" +
            "    <Enabled>true</Enabled>\n" +
            "  </Settings>\n" +
            "  <Actions Context=\"Author\">\n" +
            "    <Exec>\n" +
            "      <Command>" + SecurityElement.Escape(command) + "</Command>\n" +
            "      " + args + "\n" +
            "      <WorkingDirectory>" + SecurityElement.Escape(Path.GetDirectoryName(command) ?? "") + "</WorkingDirectory>\n" +
            "    </Exec>\n" +
            "  </Actions>\n" +
            "</Task>\n";

        var temp = Path.Combine(Path.GetTempPath(), "lkds-" + Guid.NewGuid().ToString("N") + ".xml");
        try
        {
            File.WriteAllText(temp, xml, Encoding.Unicode);
            return Tools.Run("schtasks", "/Create", "/TN", name, "/XML", temp, "/F");
        }
        finally
        {
            try { File.Delete(temp); } catch { }
        }
    }
}
