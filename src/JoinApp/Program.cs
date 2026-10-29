using System.Linq;
using System.Windows.Forms;

namespace Lkds.JoinApp;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        // --post: Nachlauf nach dem Neustart, läuft als SYSTEM ohne Fenster.
        if (args.Contains("--post"))
        {
            PostInstall.Run();
            return;
        }

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm());
    }
}
