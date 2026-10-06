using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;
using Lkds.Shared;

namespace Lkds.JoinApp;

public class MainForm : Form
{
    private static readonly Color Accent = Color.FromArgb(15, 108, 189);
    private static readonly Color Muted = Color.FromArgb(97, 97, 97);

    private readonly JoinConfig? _config;
    private readonly ComboBox _userBox = new();
    private readonly ComboBox _locationBox = new();
    private readonly TextBox _nameBox = new();
    private readonly TextBox _passwordBox = new();
    private readonly Button _joinButton = new();
    private readonly Label _statusLabel = new();
    private readonly LinkLabel _detailsLink = new();
    private readonly TextBox _detailsBox = new();

    public MainForm()
    {
        Text = "LKDS Computer Join";
        Font = new Font("Segoe UI", 9.75f);
        BackColor = Color.White;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(420, 470);

        try
        {
            _config = ConfigPayload.ReadFrom(Application.ExecutablePath);
        }
        catch (Exception ex)
        {
            BuildLayout("Keine Konfiguration");
            ShowStatus("Die eingebettete Konfiguration konnte nicht gelesen werden.", ex.Message);
            _joinButton.Enabled = false;
            return;
        }

        BuildLayout(_config is null ? "Keine Konfiguration enthalten" : $"Domäne: {_config.Domain}");
        _nameBox.Text = Environment.MachineName;

        if (_config is null)
        {
            ShowStatus("Diese Datei wurde nicht mit dem LKDS AD Join Builder erstellt.", "");
            _joinButton.Enabled = false;
            return;
        }

        _userBox.Items.AddRange(_config.Users);
        _userBox.SelectedIndex = 0;
        foreach (var l in _config.Locations) _locationBox.Items.Add(l.Name);
        if (_locationBox.Items.Count > 0) _locationBox.SelectedIndex = 0;

        var current = DomainJoiner.GetCurrentDomain();
        if (current is not null)
        {
            ShowStatus($"Der Computer ist bereits Mitglied einer Domäne ({current}).", "");
            _joinButton.Enabled = false;
        }
    }

    private void BuildLayout(string domainText)
    {
        var y = 20;
        Add(new Label { Text = "LKDS Computer Join", Font = new Font("Segoe UI Semibold", 16f) }, 24, ref y, 30);
        Add(new Label { Text = domainText, ForeColor = Muted }, 24, ref y, 26);

        AddField("AD-Benutzer", _userBox, ref y);
        _userBox.DropDownStyle = ComboBoxStyle.DropDownList;
        AddField("Standort", _locationBox, ref y);
        _locationBox.DropDownStyle = ComboBoxStyle.DropDownList;
        AddField("Computername", _nameBox, ref y);
        _nameBox.MaxLength = ComputerNameValidator.MaxLength;
        AddField("Passwort", _passwordBox, ref y);
        _passwordBox.UseSystemPasswordChar = true;

        y += 14;
        _joinButton.Text = "COMPUTER JOINEN";
        _joinButton.BackColor = Accent;
        _joinButton.ForeColor = Color.White;
        _joinButton.FlatStyle = FlatStyle.Flat;
        _joinButton.FlatAppearance.BorderSize = 0;
        _joinButton.Font = new Font("Segoe UI Semibold", 10f);
        _joinButton.Cursor = Cursors.Hand;
        _joinButton.Click += JoinButton_Click;
        Add(_joinButton, 24, ref y, 40);

        y += 10;
        Add(new Label { Text = "Status", ForeColor = Muted, Font = new Font("Segoe UI", 8.5f) }, 24, ref y, 18);
        _statusLabel.Text = "Bereit";
        Add(_statusLabel, 24, ref y, 44);

        _detailsLink.Text = "Details anzeigen";
        _detailsLink.Visible = false;
        _detailsLink.LinkClicked += (_, _) => _detailsBox.Visible = !_detailsBox.Visible;
        Add(_detailsLink, 24, ref y, 22);

        _detailsBox.Multiline = true;
        _detailsBox.ReadOnly = true;
        _detailsBox.ScrollBars = ScrollBars.Vertical;
        _detailsBox.Visible = false;
        Add(_detailsBox, 24, ref y, 60);
    }

    private void AddField(string label, Control input, ref int y)
    {
        y += 6;
        Add(new Label { Text = label, ForeColor = Muted, Font = new Font("Segoe UI", 8.5f) }, 24, ref y, 18);
        Add(input, 24, ref y, 28);
    }

    private void Add(Control control, int x, ref int y, int height)
    {
        control.Location = new Point(x, y);
        control.Size = new Size(ClientSize.Width - 2 * x, height);
        Controls.Add(control);
        y += height;
    }

    private async void JoinButton_Click(object? sender, EventArgs e)
    {
        if (_config is null) return;

        var name = _nameBox.Text.Trim();
        var nameError = ComputerNameValidator.Validate(name);
        if (nameError is not null) { ShowStatus(nameError, ""); return; }
        if (_userBox.SelectedItem is not string user) { ShowStatus("Bitte einen AD-Benutzer auswählen.", ""); return; }
        if (_locationBox.SelectedIndex < 0) { ShowStatus("Bitte einen Standort auswählen.", ""); return; }
        if (_passwordBox.Text.Length == 0) { ShowStatus("Bitte das Passwort eingeben.", ""); return; }

        var location = _config.Locations[_locationBox.SelectedIndex];
        name = name.ToUpperInvariant();
        var password = _passwordBox.Text;

        _joinButton.Enabled = false;
        ShowStatus("Computer wird der Domäne hinzugefügt …", "");

        var result = await Task.Run(() => DomainJoiner.Join(_config.Domain, location.Dn, user, password, name));
        _passwordBox.Clear();

        var message = result.Message;
        var details = result.Details;
        if (result.Success)
        {
            var firewallError = await Task.Run(Firewall.OpenPort445);
            if (firewallError is null)
            {
                details = "Firewall: Port 445 (eingehend, Domänenprofil) geöffnet.";
            }
            else
            {
                message += " Port 445 konnte nicht geöffnet werden.";
                details = $"Firewall-Fehler: {firewallError}";
            }

            if (_config.PostScript is { Length: > 0 } script)
            {
                var scriptError = await Task.Run(() => PostScript.Schedule(script));
                if (scriptError is null)
                {
                    details += " | Skript: wird beim nächsten Start als SYSTEM ausgeführt.";
                }
                else
                {
                    message += " Das Skript für den Neustart konnte nicht eingerichtet werden.";
                    details += $" | Skript-Fehler: {scriptError}";
                }
            }
        }

        JoinLog.Write(name, user, location.Name, location.Dn,
            result.Success ? "Erfolg" : "Fehler", details);
        ShowStatus(message, details);

        if (result.Success)
        {
            var restart = MessageBox.Show(this, "Der Computer muss neu gestartet werden. Jetzt neu starten?",
                "Neustart", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (restart == DialogResult.Yes)
                Process.Start(new ProcessStartInfo("shutdown", "/r /t 5") { CreateNoWindow = true, UseShellExecute = false });
        }
        else
        {
            _joinButton.Enabled = true;
        }
    }

    private void ShowStatus(string message, string details)
    {
        _statusLabel.Text = message;
        _detailsBox.Text = details;
        _detailsBox.Visible = false;
        _detailsLink.Visible = details.Length > 0;
    }
}
