using System.Diagnostics;
using System.Windows;
using System.Windows.Input;
using Lkds.Join.Shared;

namespace Lkds.Join.JoinApp;

public partial class MainWindow : Window
{
    JoinConfig? config;

    public MainWindow()
    {
        InitializeComponent();
    }

    void Window_Loaded(object sender, RoutedEventArgs e)
    {
        NameBox.Text = Environment.MachineName;

        try { config = ConfigPayload.ReadFrom(Environment.ProcessPath!); }
        catch (Exception ex) { ShowError("Die eingebettete Konfiguration konnte nicht gelesen werden.", ex.Message); }

        if (config == null || config.Users.Count == 0 || config.Locations.Count == 0)
        {
            JoinButton.IsEnabled = false;
            if (DetailsExpander.Visibility != Visibility.Visible)
                ShowError("Diese EXE enthält keine gültige Konfiguration. Bitte mit dem Builder neu erstellen.", null);
            return;
        }

        UserBox.ItemsSource = config.Users;
        UserBox.SelectedIndex = 0;
        LocationBox.ItemsSource = config.Locations;
        LocationBox.SelectedIndex = 0;

        RunStartupTasks();
    }

    async void RunStartupTasks()
    {
        StatusText.Text = "Registry wird importiert ...";
        var errors = await Task.Run(() => Preparation.ImportStartupRegs(config!));
        if (errors.Count == 0)
            StatusText.Text = "Bereit";
        else
            ShowError("Nicht alle Vorbereitungsschritte waren erfolgreich. Der Join kann trotzdem versucht werden.",
                string.Join(Environment.NewLine, errors));
    }

    void PasswordBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && JoinButton.IsEnabled) JoinButton_Click(sender, e);
    }

    async void JoinButton_Click(object sender, RoutedEventArgs e)
    {
        var location = (JoinLocation?)LocationBox.SelectedItem;
        string? user = UserBox.SelectedItem as string;
        string name = NameBox.Text.Trim();
        string password = PasswordBox.Password;

        string? problem = Validate(user, location, name, password);
        if (problem != null) { ShowError(problem, null); return; }

        if (DomainJoin.IsDomainMember())
        {
            ShowError("Der Computer ist bereits Mitglied einer Domäne.", null);
            return;
        }

        if (!IsOnFixedDrive(Environment.ProcessPath!))
        {
            ShowError("Die EXE muss auf einer lokalen Festplatte liegen (z. B. C:\\LDS), nicht auf einem Netzlaufwerk oder USB-Stick. "
                + "Sie wird nach dem Neustart erneut gebraucht.", null);
            return;
        }

        JoinButton.IsEnabled = false;
        StatusText.Text = "Computer wird der Domäne hinzugefügt ...";
        DetailsExpander.Visibility = Visibility.Collapsed;
        Log.Write($"Join gestartet: Computer={name}, Benutzer={user}, Standort={location!.Name}, OU={location.Dn}");

        var cfg = config!;
        string domain = cfg.Domain;
        uint rc = await Task.Run(() =>
        {
            try { Preparation.ImportDnsReg(cfg, location.Name); }
            catch (Exception ex) { Log.Write("DNS-Reg fehlgeschlagen: " + ex.Message); return uint.MaxValue; }
            return DomainJoin.Join(domain, location.Dn, user!, password, name);
        });
        PasswordBox.Clear();

        if (rc == uint.MaxValue)
        {
            ShowError("Die DNS-Einstellungen für den Standort konnten nicht importiert werden. Details siehe Log.", null);
        }
        else if (rc != 0)
        {
            Log.Write($"Join fehlgeschlagen: {DomainJoin.TechnicalMessage(rc)}");
            ShowError(DomainJoin.FriendlyMessage(rc), DomainJoin.TechnicalMessage(rc));
        }
        else
        {
            Log.Write("Join erfolgreich");
            RegisterAndRestart();
            return;
        }
        JoinButton.IsEnabled = true;
    }

    string? Validate(string? user, JoinLocation? location, string name, string password)
    {
        if (user == null) return "Bitte einen AD-Benutzer auswählen.";
        if (location == null) return "Bitte einen Standort auswählen.";
        if (name.Length == 0 || name.Length > 15 || name.All(char.IsDigit)
            || !name.All(c => (c < 128 && char.IsLetterOrDigit(c)) || c == '-'))
            return "Der Computername ist ungültig (1–15 Zeichen, nur Buchstaben, Ziffern und Bindestrich, nicht nur Ziffern).";
        if (password.Length == 0) return "Bitte das Passwort eingeben.";
        return null;
    }

    // Nach dem Join: Task für Phase 2 anlegen und sofort neu starten.
    void RegisterAndRestart()
    {
        try
        {
            PostInstall.Register();
        }
        catch (Exception ex)
        {
            Log.Write("Autostart-Task fehlgeschlagen: " + ex.Message);
            ShowError("Der Computer wurde der Domäne hinzugefügt, aber die Installation nach dem Neustart konnte nicht vorbereitet werden. "
                + "ZENworks und Bitdefender müssen von Hand installiert werden.", ex.Message);
            return;
        }

        StatusText.Text = "Der Computer wurde der Domäne hinzugefügt und wird neu gestartet ...";
        var psi = new ProcessStartInfo("shutdown.exe") { CreateNoWindow = true, UseShellExecute = false };
        foreach (var a in new[] { "/r", "/f", "/t", "0" }) psi.ArgumentList.Add(a);
        Process.Start(psi);
    }

    static bool IsOnFixedDrive(string path)
    {
        try
        {
            string? root = Path.GetPathRoot(path);
            return !string.IsNullOrEmpty(root) && !root.StartsWith(@"\\") && new DriveInfo(root).DriveType == DriveType.Fixed;
        }
        catch { return false; }
    }

    void ShowError(string message, string? details)
    {
        StatusText.Text = message;
        DetailsText.Text = details ?? "";
        DetailsExpander.Visibility = string.IsNullOrEmpty(details) ? Visibility.Collapsed : Visibility.Visible;
    }
}
