using System.Windows;
using System.Windows.Input;
using Lkds.Join.Shared;
using Microsoft.Win32;

namespace Lkds.Join.Builder;

public partial class MainWindow : Window
{
    readonly BuilderSettings settings = SettingsStore.Load();
    List<CheckItem> locations = new();
    List<CheckItem> users = new();
    HashSet<string> pendingLocations = new(StringComparer.OrdinalIgnoreCase);

    public MainWindow()
    {
        InitializeComponent();
    }

    void Window_Loaded(object sender, RoutedEventArgs e)
    {
        // AD-Kennung durchschleifen: aktueller Windows-Benutzer
        UserBox.Text = Environment.UserName;
        OutputBox.Text = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
        RegFolderBox.Text = settings.RegFolder;

        var known = settings.KnownUsers.Count > 0 ? settings.KnownUsers : new List<string> { "test-wadm" };
        users = known.Select(n => new CheckItem { Name = n, IsSelected = n == known[0] }).ToList();
        UserList.ItemsSource = users;

        ProfileBox.ItemsSource = settings.Profiles;
        UpdateSummary();
    }

    // ---------- AD-Verbindung ----------

    async void Connect_Click(object sender, RoutedEventArgs e)
    {
        string domain = DomainBox.Text.Trim(), baseOu = BaseOuBox.Text.Trim(), user = UserBox.Text.Trim();
        string password = PasswordBox.Password;
        if (domain.Length == 0 || baseOu.Length == 0) { SetStatus("Bitte Domäne und Basis-OU angeben.", null); return; }

        ConnectButton.IsEnabled = false;
        SetStatus("Verbindung wird aufgebaut ...", null);
        try
        {
            var found = await Task.Run(() => AdDirectory.LoadLocations(domain, baseOu, user, password));
            foreach (var item in found) item.IsSelected = pendingLocations.Contains(item.Name);
            locations = found;
            LocationList.ItemsSource = locations;
            LocationsHint.Visibility = locations.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            LocationsHint.Text = "Unterhalb der Basis-OU wurden keine OUs gefunden.";
            SetStatus($"Verbunden. {locations.Count} Standort(e) gefunden.", null);
        }
        catch (Exception ex)
        {
            SetStatus(AdDirectory.FriendlyMessage(ex), ex.Message);
        }
        finally
        {
            PasswordBox.Clear();
            ConnectButton.IsEnabled = true;
            UpdateSummary();
        }
    }

    void SetStatus(string message, string? details)
    {
        ConnectStatus.Text = message;
        DetailsText.Text = details ?? "";
        DetailsExpander.Visibility = string.IsNullOrEmpty(details) ? Visibility.Collapsed : Visibility.Visible;
    }

    // ---------- Benutzer ----------

    void AddUser_Click(object sender, RoutedEventArgs e)
    {
        string name = NewUserBox.Text.Trim();
        if (name.Length == 0) return;
        if (!users.Any(u => u.Name.Equals(name, StringComparison.OrdinalIgnoreCase)))
            users.Add(new CheckItem { Name = name, IsSelected = true });
        NewUserBox.Clear();
        RefreshUsers();
    }

    void NewUserBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter) AddUser_Click(sender, e);
    }

    void RemoveUser_Click(object sender, RoutedEventArgs e)
    {
        if (UserList.SelectedItem is CheckItem item) users.Remove(item);
        RefreshUsers();
    }

    void RefreshUsers()
    {
        UserList.ItemsSource = null;
        UserList.ItemsSource = users;
        UpdateSummary();
    }

    // ---------- Profile ----------

    void ProfileBox_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (ProfileBox.SelectedItem is not Profile p) return;

        DomainBox.Text = p.Domain;
        BaseOuBox.Text = p.BaseOu;
        foreach (var name in p.Users)
            if (!users.Any(u => u.Name.Equals(name, StringComparison.OrdinalIgnoreCase)))
                users.Add(new CheckItem { Name = name });
        foreach (var u in users) u.IsSelected = p.Users.Contains(u.Name, StringComparer.OrdinalIgnoreCase);
        RefreshUsers();

        pendingLocations = new HashSet<string>(p.Locations, StringComparer.OrdinalIgnoreCase);
        foreach (var l in locations) l.IsSelected = pendingLocations.Contains(l.Name);
        LocationList.ItemsSource = null;
        LocationList.ItemsSource = locations;
        UpdateSummary();
    }

    void SaveProfile_Click(object sender, RoutedEventArgs e)
    {
        string name = ProfileBox.Text.Trim();
        if (name.Length == 0) { MessageBox.Show(this, "Bitte einen Profilnamen eingeben.", Title); return; }

        var profile = settings.Profiles.FirstOrDefault(p => p.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
        if (profile == null)
        {
            profile = new Profile { Name = name };
            settings.Profiles.Add(profile);
        }
        profile.Domain = DomainBox.Text.Trim();
        profile.BaseOu = BaseOuBox.Text.Trim();
        profile.Users = users.Where(u => u.IsSelected).Select(u => u.Name).ToList();
        profile.Locations = locations.Where(l => l.IsSelected).Select(l => l.Name).ToList();
        PersistSettings();

        ProfileBox.ItemsSource = null;
        ProfileBox.ItemsSource = settings.Profiles;
        ProfileBox.Text = name;
    }

    void DeleteProfile_Click(object sender, RoutedEventArgs e)
    {
        if (ProfileBox.SelectedItem is not Profile p) return;
        settings.Profiles.Remove(p);
        PersistSettings();
        ProfileBox.ItemsSource = null;
        ProfileBox.ItemsSource = settings.Profiles;
    }

    void PersistSettings()
    {
        settings.KnownUsers = users.Select(u => u.Name).ToList();
        settings.RegFolder = RegFolderBox.Text.Trim();
        try { SettingsStore.Save(settings); }
        catch (Exception ex) { MessageBox.Show(this, "Einstellungen konnten nicht gespeichert werden:\n" + ex.Message, Title); }
    }

    // ---------- EXE erstellen ----------

    void Browse_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog { Title = "Ausgabeordner wählen" };
        if (dialog.ShowDialog(this) == true) OutputBox.Text = dialog.FolderName;
    }

    void BrowseReg_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog { Title = "Ordner mit den Reg-Dateien wählen" };
        if (dialog.ShowDialog(this) == true) RegFolderBox.Text = dialog.FolderName;
    }

    void Selection_Changed(object sender, RoutedEventArgs e) => UpdateSummary();
    void FileNameBox_TextChanged(object sender, System.Windows.Controls.TextChangedEventArgs e) => UpdateSummary();

    void UpdateSummary()
    {
        if (SummaryText == null) return;
        string Join(IEnumerable<string> items) => string.Join(", ", items.DefaultIfEmpty("–"));
        SummaryText.Text =
            $"EXE: {FileNameBox.Text}\n" +
            $"Domäne: {DomainBox.Text}\n" +
            $"Reg-Ordner: {RegFolderBox.Text}\n" +
            $"Benutzer: {Join(users.Where(u => u.IsSelected).Select(u => u.Name))}\n" +
            $"Standorte: {Join(locations.Where(l => l.IsSelected).Select(l => l.Name))}";
    }

    void Build_Click(object sender, RoutedEventArgs e)
    {
        var selectedUsers = users.Where(u => u.IsSelected).Select(u => u.Name).ToList();
        var selectedLocations = locations.Where(l => l.IsSelected).ToList();
        string fileName = FileNameBox.Text.Trim(), folder = OutputBox.Text.Trim();

        string? problem =
            selectedUsers.Count == 0 ? "Bitte mindestens einen Benutzer auswählen." :
            selectedLocations.Count == 0 ? "Bitte mindestens einen Standort auswählen (zuerst mit dem AD verbinden)." :
            fileName.Length == 0 || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ? "Der Dateiname ist ungültig." :
            !Directory.Exists(folder) ? "Der Ausgabeordner existiert nicht." :
            !Directory.Exists(RegFolderBox.Text.Trim()) ? "Der Reg-Ordner existiert nicht." : null;
        if (problem != null) { MessageBox.Show(this, problem, Title, MessageBoxButton.OK, MessageBoxImage.Warning); return; }

        var config = new JoinConfig
        {
            Domain = DomainBox.Text.Trim(),
            BaseOu = BaseOuBox.Text.Trim(),
            Users = selectedUsers,
            Locations = selectedLocations.Select(l => new JoinLocation { Name = l.Name, Dn = l.Dn }).ToList(),
        };

        try
        {
            string target = JoinExeGenerator.Create(folder, fileName, config, RegFolderBox.Text.Trim());
            PersistSettings();
            MessageBox.Show(this, $"Die Join-EXE wurde erstellt:\n{target}", Title, MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, "Die EXE konnte nicht erstellt werden.\n\n" + ex.Message, Title, MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
