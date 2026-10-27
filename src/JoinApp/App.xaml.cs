using System.Windows;

namespace Lkds.Join.JoinApp;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // Phase 2 nach dem Neustart: läuft ohne Fenster, gestartet vom geplanten Task.
        if (e.Args.Contains("--post"))
        {
            ShutdownMode = ShutdownMode.OnExplicitShutdown;
            PostInstall.Run();
            Shutdown();
            return;
        }

        new MainWindow().Show();
    }
}
