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
        StatusText.Text = "Programme werden gestartet, Registry wird importiert ...";
        var errors = await Task.Run(Preparation.RunStartup);
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

        JoinButton.IsEnabled = false;
        StatusText.Text = "Computer wird der Domäne hinzugefügt ...";
        DetailsExpander.Visibility = Visibility.Collapsed;
        Log.Write($"Join gestartet: Computer={name}, Benutzer={user}, Standort={location!.Name}, OU={location.Dn}");

        string domain = config!.Domain;
        uint rc = await Task.Run(() =>
        {
            try { Preparation.ImportDnsReg(location.Name); }
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
            StatusText.Text = "Der Computer wurde erfolgreich der Domäne hinzugefügt.";
            AskForRestart();
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

    void AskForRestart()
    {
        var answer = MessageBox.Show(this, "Der Computer muss neu gestartet werden. Jetzt neu starten?",
            "LKDS Computer Join", MessageBoxButton.YesNo, MessageBoxImage.Question);
        if (answer == MessageBoxResult.Yes)
            Process.Start(new ProcessStartInfo("shutdown.exe", "/r /t 5") { CreateNoWindow = true, UseShellExecute = false });
    }

    void ShowError(string message, string? details)
    {
        StatusText.Text = message;
        DetailsText.Text = details ?? "";
        DetailsExpander.Visibility = string.IsNullOrEmpty(details) ? Visibility.Collapsed : Visibility.Visible;
    }
}
