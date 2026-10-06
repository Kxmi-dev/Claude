using System.Diagnostics;
using System.Windows;
using Lkds.Shared;

namespace Lkds.JoinApp;

public partial class MainWindow : Window
{
    private readonly JoinConfig? _config;

    public MainWindow()
    {
        InitializeComponent();

        try
        {
            _config = ConfigPayload.ReadFrom(Environment.ProcessPath!);
        }
        catch (Exception ex)
        {
            ShowStatus("Die eingebettete Konfiguration konnte nicht gelesen werden.", ex.Message);
        }

        NameBox.Text = Environment.MachineName;

        if (_config is null)
        {
            DomainText.Text = "Keine Konfiguration enthalten";
            if (StatusText.Text == "Bereit")
                ShowStatus("Diese Datei wurde nicht mit dem LKDS AD Join Builder erstellt.", "");
            JoinButton.IsEnabled = false;
            return;
        }

        DomainText.Text = $"Domäne: {_config.Domain}";
        UserBox.ItemsSource = _config.Users;
        UserBox.SelectedIndex = 0;
        LocationBox.ItemsSource = _config.Locations;
        LocationBox.SelectedIndex = 0;

        var current = DomainJoiner.GetCurrentDomain();
        if (current is not null)
        {
            ShowStatus($"Der Computer ist bereits Mitglied einer Domäne ({current}).", "");
            JoinButton.IsEnabled = false;
        }
    }

    private async void JoinButton_Click(object sender, RoutedEventArgs e)
    {
        if (_config is null) return;

        var nameError = ComputerNameValidator.Validate(NameBox.Text.Trim());
        if (nameError is not null) { ShowStatus(nameError, ""); return; }
        if (UserBox.SelectedItem is not string user) { ShowStatus("Bitte einen AD-Benutzer auswählen.", ""); return; }
        if (LocationBox.SelectedItem is not LocationEntry location) { ShowStatus("Bitte einen Standort auswählen.", ""); return; }
        if (PasswordBox.Password.Length == 0) { ShowStatus("Bitte das Passwort eingeben.", ""); return; }

        var name = NameBox.Text.Trim().ToUpperInvariant();
        var password = PasswordBox.Password;

        JoinButton.IsEnabled = false;
        ShowStatus("Computer wird der Domäne hinzugefügt …", "");

        var result = await Task.Run(() => DomainJoiner.Join(_config.Domain, location.Dn, user, password, name));
        PasswordBox.Clear();

        JoinLog.Write(name, user, location.Name, location.Dn,
            result.Success ? "Erfolg" : "Fehler", result.Details);
        ShowStatus(result.Message, result.Details);

        if (result.Success)
        {
            var restart = MessageBox.Show(this, "Der Computer muss neu gestartet werden. Jetzt neu starten?",
                "Neustart", MessageBoxButton.YesNo, MessageBoxImage.Question);
            if (restart == MessageBoxResult.Yes)
                Process.Start(new ProcessStartInfo("shutdown", "/r /t 5") { CreateNoWindow = true, UseShellExecute = false });
        }
        else
        {
            JoinButton.IsEnabled = true;
        }
    }

    private void ShowStatus(string message, string details)
    {
        StatusText.Text = message;
        DetailsBox.Text = details;
        DetailsExpander.Visibility = string.IsNullOrEmpty(details) ? Visibility.Collapsed : Visibility.Visible;
    }
}
