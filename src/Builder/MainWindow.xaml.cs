using System.IO;
using System.Windows;
using System.Windows.Controls;
using Lkds.Shared;

namespace Lkds.Builder;

public class CheckItem
{
    public string Name { get; set; } = "";
    public string Dn { get; set; } = "";
    public bool Selected { get; set; }
    public string? Password { get; set; }
    /// <summary>DNS-Datei dieses Standorts (Name oder "keine").</summary>
    public string Dns { get; set; } = LdsSteps.NoDns;
    public string[] DnsChoices { get; } = [LdsSteps.NoDns, .. LdsSteps.KnownDnsNames];
    public string Hint => string.IsNullOrEmpty(Password) ? "" : "Passwort hinterlegt";
}

public partial class MainWindow : Window
{
    private static readonly string[] StepNames = ["AD-Verbindung", "Standorte", "Benutzer", "EXE erstellen"];

    private readonly List<Profile> _profiles = ProfileStore.Load();
    private readonly List<CheckItem> _locations = [];
    private readonly List<CheckItem> _users = [];
    private readonly UIElement[] _pages;
    private const int MaxBatBytes = 1024 * 1024;
    private int _step;
    private bool _connected;
    private List<string> _wantedLocations = [];
    private Dictionary<string, string> _wantedDns = [];

    public MainWindow()
    {
        InitializeComponent();
        _pages = [Page1, Page2, Page3, Page4];

        // Der eigene Windows-Benutzername steht gleich drin, ohne Passwort gilt die aktuelle Anmeldung (SSO).
        ConnUserBox.Text = Environment.UserName;
        NewUserBox.Text = Environment.UserName;

        OutputBox.Text = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
        ProfileBox.ItemsSource = _profiles;
        ProfileBox.SelectedIndex = 0;
        ShowStep(0);
    }

    // ---------- Navigation ----------

    private void ShowStep(int step)
    {
        _step = step;
        for (var i = 0; i < _pages.Length; i++)
            _pages[i].Visibility = i == step ? Visibility.Visible : Visibility.Collapsed;

        StepText.Text = $"Schritt {step + 1} von {StepNames.Length}: {StepNames[step]}";
        BackButton.Visibility = step == 0 ? Visibility.Hidden : Visibility.Visible;
        NextButton.Visibility = step == StepNames.Length - 1 ? Visibility.Hidden : Visibility.Visible;
        if (step == 3) UpdateSummary();
    }

    private void Back_Click(object sender, RoutedEventArgs e) => ShowStep(_step - 1);

    private void Next_Click(object sender, RoutedEventArgs e)
    {
        if (_step == 0 && !_connected)
        {
            MessageBox.Show(this, "Bitte zuerst mit dem Active Directory verbinden.", Title, MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        if (_step == 1 && !_locations.Any(l => l.Selected))
        {
            MessageBox.Show(this, "Bitte mindestens einen Standort auswählen.", Title, MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        if (_step == 2 && !_users.Any(u => u.Selected))
        {
            MessageBox.Show(this, "Bitte mindestens einen Benutzer auswählen.", Title, MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        ShowStep(_step + 1);
    }

    // ---------- Profile ----------

    private void ProfileBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ProfileBox.SelectedItem is not Profile p) return;
        DomainBox.Text = p.Domain;
        BaseOuBox.Text = p.BaseOu;
        _wantedLocations = [.. p.SelectedLocations];
        _wantedDns = new Dictionary<string, string>(p.LocationDns, StringComparer.OrdinalIgnoreCase);

        _users.Clear();
        foreach (var name in p.Users.Union(p.SelectedUsers))
            _users.Add(new CheckItem { Name = name, Selected = p.SelectedUsers.Contains(name) });
        RefreshUsers();

        foreach (var l in _locations)
        {
            l.Selected = _wantedLocations.Contains(l.Name);
            l.Dns = WantedDnsFor(l.Name);
        }
        RefreshLocations();
    }

    private void SaveProfile_Click(object sender, RoutedEventArgs e)
    {
        var name = ProfileBox.Text.Trim();
        if (name.Length == 0)
        {
            MessageBox.Show(this, "Bitte einen Profilnamen eingeben.", Title, MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var profile = _profiles.FirstOrDefault(p => p.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
        if (profile is null)
        {
            profile = new Profile { Name = name };
            _profiles.Add(profile);
        }
        profile.Domain = DomainBox.Text.Trim();
        profile.BaseOu = BaseOuBox.Text.Trim();
        profile.Users = _users.Select(u => u.Name).ToList();
        profile.SelectedUsers = _users.Where(u => u.Selected).Select(u => u.Name).ToList();
        profile.SelectedLocations = _locations.Count > 0
            ? _locations.Where(l => l.Selected).Select(l => l.Name).ToList()
            : _wantedLocations;
        profile.LocationDns = _locations.Count > 0
            ? _locations.ToDictionary(l => l.Name, l => l.Dns)
            : new Dictionary<string, string>(_wantedDns);

        ProfileStore.Save(_profiles);
        ProfileBox.Items.Refresh();
        ProfileBox.SelectedItem = profile;
        ConnStatus.Text = $"Profil „{profile.Name}“ gespeichert (ohne Passwort).";
    }

    private void DeleteProfile_Click(object sender, RoutedEventArgs e)
    {
        if (ProfileBox.SelectedItem is not Profile p || _profiles.Count <= 1) return;
        _profiles.Remove(p);
        ProfileStore.Save(_profiles);
        ProfileBox.Items.Refresh();
        ProfileBox.SelectedIndex = 0;
    }

    // ---------- Schritt 1: Verbindung ----------

    /// <summary>Gespeicherte Zuordnung aus dem Profil, sonst Namensregel (LNWS zu LNRE), sonst keine.</summary>
    private string WantedDnsFor(string location) =>
        _wantedDns.TryGetValue(location, out var dns) && (dns == LdsSteps.NoDns || LdsSteps.KnownDnsNames.Contains(dns))
            ? dns
            : LdsSteps.DefaultDnsFor(location, LdsSteps.KnownDnsNames) ?? LdsSteps.NoDns;

    private async void Connect_Click(object sender, RoutedEventArgs e)
    {
        var domain = DomainBox.Text.Trim();
        var baseOu = BaseOuBox.Text.Trim();
        // Leeres Passwort: mit der aktuellen Windows-Anmeldung verbinden (SSO).
        var own = ConnPasswordBox.Password.Length == 0;
        var user = own ? null : ConnUserBox.Text.Trim();
        var password = own ? null : ConnPasswordBox.Password;

        if (domain.Length == 0 || baseOu.Length == 0 || (!own && user!.Length == 0))
        {
            ConnStatus.Text = "Bitte Domäne, Basis-OU und, falls ein Passwort eingegeben ist, den Benutzer ausfüllen.";
            return;
        }

        ConnStatus.Text = "Verbinde …";
        _connected = false;
        try
        {
            var found = await Task.Run(() => AdReader.ReadLocations(domain, baseOu, user, password));
            ConnPasswordBox.Clear();

            _locations.Clear();
            foreach (var l in found)
                _locations.Add(new CheckItem { Name = l.Name, Dn = l.Dn, Selected = _wantedLocations.Contains(l.Name), Dns = WantedDnsFor(l.Name) });
            RefreshLocations();

            _connected = true;
            ConnStatus.Text = found.Count == 0
                ? "Verbunden, aber unterhalb der Basis-OU wurden keine OUs gefunden."
                : $"Verbunden. {found.Count} Standort(e) gefunden.";
        }
        catch (Exception ex)
        {
            ConnStatus.Text = $"{AdReader.Describe(ex)}\n\nDetails: {ex.Message}";
        }
    }

    // ---------- Schritt 2 und 3: Listen ----------

    private void RefreshLocations()
    {
        LocationList.ItemsSource = null;
        LocationList.ItemsSource = _locations;
    }

    private void RefreshUsers()
    {
        UserList.ItemsSource = null;
        UserList.ItemsSource = _users;
    }

    private void AddUser_Click(object sender, RoutedEventArgs e)
    {
        var name = NewUserBox.Text.Trim();
        if (name.Length == 0 || _users.Any(u => u.Name.Equals(name, StringComparison.OrdinalIgnoreCase))) return;
        var password = NewPasswordBox.Password;
        _users.Add(new CheckItem { Name = name, Selected = true, Password = password.Length > 0 ? password : null });
        NewUserBox.Clear();
        NewPasswordBox.Clear();
        RefreshUsers();
    }

    private void NewUserBox_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key == System.Windows.Input.Key.Enter) AddUser_Click(sender, e);
    }

    private void RemoveUser_Click(object sender, RoutedEventArgs e)
    {
        if (((FrameworkElement)sender).DataContext is CheckItem item)
        {
            _users.Remove(item);
            RefreshUsers();
        }
    }

    // ---------- Schritt 4: EXE ----------

    private void BrowseFolder_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog { InitialDirectory = OutputBox.Text };
        if (dialog.ShowDialog(this) == true) OutputBox.Text = dialog.FolderName;
    }

    private void BrowseRegFolder_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog { InitialDirectory = RegFolderBox.Text };
        if (dialog.ShowDialog(this) == true) RegFolderBox.Text = dialog.FolderName;
    }

    private void BrowseBat_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog { Filter = "Batch-Datei (*.bat;*.cmd)|*.bat;*.cmd" };
        if (dialog.ShowDialog(this) != true) return;
        if (new FileInfo(dialog.FileName).Length > MaxBatBytes)
        {
            BuildStatus.Text = "Die .bat-Datei ist zu groß (maximal 1 MB).";
            return;
        }
        BatBox.Text = dialog.FileName;
        UpdateSummary();
    }

    private void LdsCheck_Changed(object sender, RoutedEventArgs e)
    {
        if (IsLoaded) UpdateSummary();
    }

    private void ClearBat_Click(object sender, RoutedEventArgs e)
    {
        BatBox.Clear();
        UpdateSummary();
    }

    private void Summary_Changed(object sender, TextChangedEventArgs e)
    {
        if (IsLoaded) UpdateSummary();
    }

    private void UpdateSummary()
    {
        SummaryText.Text =
            $"EXE:\n{ExeNameBox.Text}\n\n" +
            $"Domäne:\n{DomainBox.Text}\n\n" +
            $"Benutzer:\n{string.Join("\n", _users.Where(u => u.Selected).Select(u => u.Name + (u.Password is null ? "" : " (Passwort hinterlegt)")))}\n\n" +
            $"Standorte (DNS-Datei):\n{string.Join("\n", _locations.Where(l => l.Selected).Select(l => l.Name + " (" + l.Dns + ")"))}\n\n" +
            $"Standard-Ablauf (LDS): {(LdsCheck.IsChecked == true ? "ja" : "nein")}\n" +
            $"EXE löscht sich selbst: {(SelfDeleteCheck.IsChecked == true ? "ja" : "nein")}\n" +
            $"Registry-Ordner: {RegFolderBox.Text}\n\n" +
            $"Zusätzliches Skript:\n{(BatBox.Text.Length == 0 ? "keines" : Path.GetFileName(BatBox.Text))}";
    }

    private void Build_Click(object sender, RoutedEventArgs e)
    {
        var fileError = ExeGenerator.ValidateFileName(ExeNameBox.Text.Trim());
        if (fileError is not null) { BuildStatus.Text = fileError; return; }
        if (!Directory.Exists(OutputBox.Text)) { BuildStatus.Text = "Der Ausgabeordner existiert nicht."; return; }
        if (!ExeGenerator.HasTemplate)
        {
            BuildStatus.Text = "Die Join-Vorlage fehlt in diesem Builder. Bitte den Builder mit build.ps1 erstellen.";
            return;
        }

        var path = Path.Combine(OutputBox.Text, ExeNameBox.Text.Trim());
        if (File.Exists(path) && MessageBox.Show(this, $"„{ExeNameBox.Text}“ existiert bereits. Überschreiben?", Title,
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;

        byte[]? script = null;
        if (BatBox.Text.Length > 0)
        {
            try { script = File.ReadAllBytes(BatBox.Text); }
            catch (Exception ex) { BuildStatus.Text = $"Die .bat-Datei konnte nicht gelesen werden.\n\nDetails: {ex.Message}"; return; }
        }

        var selectedLocations = _locations.Where(l => l.Selected).ToList();
        var locationDns = selectedLocations.Where(l => l.Dns != LdsSteps.NoDns).ToDictionary(l => l.Name, l => l.Dns, StringComparer.OrdinalIgnoreCase);
        var dnsNames = locationDns.Values.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();

        var regFiles = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        if (LdsCheck.IsChecked == true)
        {
            var missing = new List<string>();
            foreach (var name in LdsSteps.StartupRegs.Concat(dnsNames.Select(LdsSteps.DnsRegName)))
            {
                var file = Path.Combine(RegFolderBox.Text.Trim(), name);
                if (File.Exists(file)) regFiles[name] = File.ReadAllBytes(file);
                else missing.Add(file);
            }
            if (missing.Count > 0)
            {
                BuildStatus.Text = "Diese Registry-Dateien fehlen:\n" + string.Join("\n", missing);
                return;
            }
        }

        var withPassword = _users.Where(u => u.Selected && u.Password is not null).ToList();
        if (withPassword.Count > 0 && MessageBox.Show(this,
                $"Für {string.Join(", ", withPassword.Select(u => u.Name))} wird das Passwort verschlüsselt in die EXE gelegt.\n\n" +
                "Wer die EXE besitzt und gezielt danach sucht, kann das Passwort mit etwas Aufwand auslesen. " +
                "Verwende dafür ein Konto, das nur Computer in die Domäne aufnehmen darf, und gib die EXE nicht weiter.\n\nFortfahren?",
                Title, MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;

        byte[]? key = null;
        var sealedPasswords = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        if (withPassword.Count > 0)
        {
            key = SecretBox.NewKey();
            foreach (var u in withPassword) sealedPasswords[u.Name] = SecretBox.Seal(u.Password!, key);
        }

        var config = new JoinConfig(
            DomainBox.Text.Trim(),
            BaseOuBox.Text.Trim(),
            _users.Where(u => u.Selected).Select(u => u.Name).ToArray(),
            _locations.Where(l => l.Selected).Select(l => new LocationEntry(l.Name, l.Dn)).ToArray(),
            script,
            LdsCheck.IsChecked == true,
            dnsNames,
            key,
            sealedPasswords,
            SelfDeleteCheck.IsChecked == true,
            locationDns,
            regFiles);

        try
        {
            ExeGenerator.Generate(path, config);
            BuildStatus.Text = $"Fertig: {path}";
        }
        catch (Exception ex)
        {
            BuildStatus.Text = $"Die EXE konnte nicht erstellt werden.\n\nDetails: {ex.Message}";
        }
    }
}
