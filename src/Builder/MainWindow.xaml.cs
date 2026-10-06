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

    public MainWindow()
    {
        InitializeComponent();
        _pages = [Page1, Page2, Page3, Page4];

        var domainJoined = !string.Equals(Environment.UserDomainName, Environment.MachineName, StringComparison.OrdinalIgnoreCase);
        CurrentUserCheck.Content = $"Mit meinem Windows-Konto anmelden ({Environment.UserDomainName}\\{Environment.UserName})";
        ConnUserBox.Text = Environment.UserName;
        CurrentUserCheck.IsChecked = domainJoined;
        CurrentUserCheck_Changed(this, new RoutedEventArgs());

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

        _users.Clear();
        foreach (var name in p.Users.Union(p.SelectedUsers))
            _users.Add(new CheckItem { Name = name, Selected = p.SelectedUsers.Contains(name) });
        RefreshUsers();

        foreach (var l in _locations) l.Selected = _wantedLocations.Contains(l.Name);
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

    private void CurrentUserCheck_Changed(object sender, RoutedEventArgs e)
    {
        var own = CurrentUserCheck.IsChecked == true;
        ConnUserBox.IsEnabled = !own;
        ConnPasswordBox.IsEnabled = !own;
    }

    private async void Connect_Click(object sender, RoutedEventArgs e)
    {
        var domain = DomainBox.Text.Trim();
        var baseOu = BaseOuBox.Text.Trim();
        var own = CurrentUserCheck.IsChecked == true;
        var user = own ? null : ConnUserBox.Text.Trim();
        var password = own ? null : ConnPasswordBox.Password;

        if (domain.Length == 0 || baseOu.Length == 0 || (!own && (user!.Length == 0 || password!.Length == 0)))
        {
            ConnStatus.Text = "Bitte Domäne, Basis-OU, Benutzer und Passwort ausfüllen.";
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
                _locations.Add(new CheckItem { Name = l.Name, Dn = l.Dn, Selected = _wantedLocations.Contains(l.Name) });
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
        _users.Add(new CheckItem { Name = name, Selected = true });
        NewUserBox.Clear();
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
            $"Benutzer:\n{string.Join("\n", _users.Where(u => u.Selected).Select(u => u.Name))}\n\n" +
            $"Standorte:\n{string.Join("\n", _locations.Where(l => l.Selected).Select(l => l.Name))}\n\n" +
            $"Skript nach Neustart:\n{(BatBox.Text.Length == 0 ? "keines" : Path.GetFileName(BatBox.Text))}";
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

        var config = new JoinConfig(
            DomainBox.Text.Trim(),
            BaseOuBox.Text.Trim(),
            _users.Where(u => u.Selected).Select(u => u.Name).ToArray(),
            _locations.Where(l => l.Selected).Select(l => new LocationEntry(l.Name, l.Dn)).ToArray(),
            script);

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
