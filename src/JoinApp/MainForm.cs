using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
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
    private readonly ComboBox _dnsBox = new();
    private readonly TextBox _nameBox = new();
    private readonly TextBox _passwordBox = new();
    private readonly Label _passwordLabel = new();
    private readonly Button _joinButton = new();
    private readonly Label _statusLabel = new();
    private readonly LinkLabel _detailsLink = new();
    private readonly TextBox _detailsBox = new();

    public MainForm()
    {
        // Layout wächst mit Schrift und Windows-Skalierung (kein festes Pixelraster).
        AutoScaleDimensions = new SizeF(96f, 96f);
        AutoScaleMode = AutoScaleMode.Dpi;
        Text = "LKDS Computer Join";
        Font = new Font("Segoe UI", 9.75f);
        BackColor = Color.White;
        FormBorderStyle = FormBorderStyle.Sizable;
        StartPosition = FormStartPosition.CenterScreen;

        try
        {
            _config = ConfigPayload.ReadFrom(Application.ExecutablePath);
        }
        catch (Exception ex)
        {
            BuildLayout("Keine Konfiguration", false);
            ShowStatus("Die eingebettete Konfiguration konnte nicht gelesen werden.", ex.Message);
            _joinButton.Enabled = false;
            return;
        }

        var showDns = _config is { RunLdsSteps: true } && _config.DnsOptions.Length > 0;
        BuildLayout(_config is null ? "Keine Konfiguration enthalten" : $"Domäne: {_config.Domain}", showDns);
        _nameBox.Text = Environment.MachineName;

        if (_config is null)
        {
            ShowStatus("Diese Datei wurde nicht mit dem LKDS AD Join Builder erstellt.", "");
            _joinButton.Enabled = false;
            return;
        }

        _userBox.Items.AddRange(_config.Users);
        _userBox.SelectedIndex = 0;
        UpdatePasswordField();
        foreach (var l in _config.Locations) _locationBox.Items.Add(l.Name);
        _dnsBox.Items.AddRange(_config.DnsOptions);
        if (_locationBox.Items.Count > 0) _locationBox.SelectedIndex = 0;
        SelectDefaultDns();

        var current = DomainJoiner.GetCurrentDomain();
        if (current is not null)
        {
            ShowStatus($"Der Computer ist bereits Mitglied einer Domäne ({current}).", "");
            _joinButton.Enabled = false;
        }
    }

    private const int StartWidth = 460;
    private const int StartHeight = 580;

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        // Startgröße in echten Pixeln, passend zur Windows-Skalierung. Danach frei veränderbar.
        var size = new Size(LogicalToDeviceUnits(StartWidth), LogicalToDeviceUnits(StartHeight));
        MinimumSize = SizeFromClientSize(new Size(LogicalToDeviceUnits(380), LogicalToDeviceUnits(420)));
        ClientSize = size;
        CenterToScreen();
    }

    private void BuildLayout(string domainText, bool showDns)
    {
        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
        Controls.Add(scroll);
        var table = new TableLayoutPanel
        {
            ColumnCount = 1,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Dock = DockStyle.Top,
            Padding = new Padding(24, 20, 24, 24)
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        scroll.Controls.Add(table);
        // Lange Meldungen umbrechen passend zur aktuellen Fensterbreite.
        scroll.SizeChanged += (_, _) =>
            _statusLabel.MaximumSize = new Size(Math.Max(100, scroll.ClientSize.Width - table.Padding.Horizontal - 10), 0);

        AddRow(table, new Label { Text = "LKDS Computer Join", Font = new Font("Segoe UI Semibold", 16f), AutoSize = true });
        AddRow(table, new Label { Text = domainText, ForeColor = Muted, AutoSize = true, Margin = new Padding(3, 0, 3, 8) });

        AddField(table, "AD-Benutzer", _userBox);
        _userBox.DropDownStyle = ComboBoxStyle.DropDownList;
        AddField(table, "Standort", _locationBox);
        _locationBox.DropDownStyle = ComboBoxStyle.DropDownList;
        if (showDns)
        {
            AddField(table, "DNS-Einstellung (Registry nach dem Neustart)", _dnsBox);
            _dnsBox.DropDownStyle = ComboBoxStyle.DropDownList;
            _locationBox.SelectedIndexChanged += (_, _) => SelectDefaultDns();
        }
        AddField(table, "Computername", _nameBox);
        _nameBox.MaxLength = ComputerNameValidator.MaxLength;
        _passwordLabel.Text = "Passwort";
        _passwordLabel.ForeColor = Muted;
        _passwordLabel.Font = new Font("Segoe UI", 8.5f);
        _passwordLabel.AutoSize = true;
        _passwordLabel.Margin = new Padding(3, 10, 3, 2);
        AddRow(table, _passwordLabel);
        AddRow(table, _passwordBox, fill: true);
        _passwordBox.UseSystemPasswordChar = true;
        _userBox.SelectedIndexChanged += (_, _) => UpdatePasswordField();

        _joinButton.Text = "COMPUTER JOINEN";
        _joinButton.BackColor = Accent;
        _joinButton.ForeColor = Color.White;
        _joinButton.FlatStyle = FlatStyle.Flat;
        _joinButton.FlatAppearance.BorderSize = 0;
        _joinButton.Font = new Font("Segoe UI Semibold", 10f);
        _joinButton.Cursor = Cursors.Hand;
        _joinButton.AutoSize = true;
        _joinButton.Padding = new Padding(0, 8, 0, 8);
        _joinButton.Margin = new Padding(3, 20, 3, 3);
        _joinButton.Click += JoinButton_Click;
        AddRow(table, _joinButton, fill: true);

        AddRow(table, new Label { Text = "Status", ForeColor = Muted, Font = new Font("Segoe UI", 8.5f), AutoSize = true, Margin = new Padding(3, 16, 3, 0) });
        _statusLabel.Text = "Bereit";
        _statusLabel.AutoSize = true;
        AddRow(table, _statusLabel);

        _detailsLink.Text = "Details anzeigen";
        _detailsLink.AutoSize = true;
        _detailsLink.Visible = false;
        _detailsLink.LinkClicked += (_, _) => _detailsBox.Visible = !_detailsBox.Visible;
        AddRow(table, _detailsLink);

        _detailsBox.Multiline = true;
        _detailsBox.ReadOnly = true;
        _detailsBox.ScrollBars = ScrollBars.Vertical;
        _detailsBox.Visible = false;
        _detailsBox.Height = 70;
        AddRow(table, _detailsBox, fill: true);
    }

    private static void AddField(TableLayoutPanel table, string label, Control input)
    {
        AddRow(table, new Label { Text = label, ForeColor = Muted, Font = new Font("Segoe UI", 8.5f), AutoSize = true, Margin = new Padding(3, 10, 3, 2) });
        AddRow(table, input, fill: true);
    }

    private static void AddRow(TableLayoutPanel table, Control control, bool fill = false)
    {
        if (fill) control.Dock = DockStyle.Fill;
        table.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        table.Controls.Add(control);
    }

    private async void JoinButton_Click(object? sender, EventArgs e)
    {
        if (_config is null) return;

        var name = _nameBox.Text.Trim();
        var nameError = ComputerNameValidator.Validate(name);
        if (nameError is not null) { ShowStatus(nameError, ""); return; }
        if (_userBox.SelectedItem is not string user) { ShowStatus("Bitte einen AD-Benutzer auswählen.", ""); return; }
        if (_locationBox.SelectedIndex < 0) { ShowStatus("Bitte einen Standort auswählen.", ""); return; }
        var saved = _config.GetPassword(user);
        if (_config.HasPassword(user) && saved is null) { ShowStatus("Das hinterlegte Passwort ist beschädigt. Bitte neu mit dem Builder erstellen.", ""); return; }
        if (saved is null && _passwordBox.Text.Length == 0) { ShowStatus("Bitte das Passwort eingeben.", ""); return; }

        var location = _config.Locations[_locationBox.SelectedIndex];
        string? dnsName = null;
        if (_config.RunLdsSteps && _config.DnsOptions.Length > 0)
        {
            dnsName = _dnsBox.SelectedItem as string;
            if (dnsName is null || !LdsSteps.IsValidDnsName(dnsName)) { ShowStatus("Bitte eine DNS-Einstellung auswählen.", ""); return; }
        }
        name = name.ToUpperInvariant();
        var password = saved ?? _passwordBox.Text;

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
                details += " | Firewall: Port 445 (eingehend, Domänenprofil) geöffnet.";
            }
            else
            {
                message += " Port 445 konnte nicht geöffnet werden.";
                details += $" | Firewall-Fehler: {firewallError}";
            }

            var script = BuildPostScript(dnsName);
            if (script is not null)
            {
                var scriptError = await Task.Run(() => PostScript.Schedule(script));
                if (scriptError is null)
                {
                    details += " | Nachlauf-Skript: wird beim nächsten Start als SYSTEM ausgeführt.";
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

    /// <summary>Fester LDS-Ablauf (falls gewählt) gefolgt vom optionalen freien Skript.</summary>
    private byte[]? BuildPostScript(string? dnsName)
    {
        var parts = new List<byte[]>();
        if (_config!.RunLdsSteps) parts.Add(Encoding.ASCII.GetBytes(LdsSteps.Build(dnsName)));
        if (_config.PostScript is { Length: > 0 } custom) parts.Add(custom);
        if (parts.Count == 0) return null;

        using var ms = new MemoryStream();
        foreach (var part in parts)
        {
            ms.Write(part, 0, part.Length);
            var newline = Encoding.ASCII.GetBytes("\r\n");
            ms.Write(newline, 0, newline.Length);
        }
        return ms.ToArray();
    }

    /// <summary>Ist für den Benutzer ein Passwort hinterlegt, entfällt die Eingabe.</summary>
    private void UpdatePasswordField()
    {
        var user = _userBox.SelectedItem as string;
        var saved = _config is not null && user is not null && _config.HasPassword(user);
        _passwordBox.Enabled = !saved;
        _passwordBox.Clear();
        _passwordLabel.Text = saved ? "Passwort (im Programm hinterlegt)" : "Passwort";
    }

    private void SelectDefaultDns()
    {
        if (_config is null || _locationBox.SelectedIndex < 0 || _dnsBox.Items.Count == 0) return;
        var wanted = LdsSteps.DefaultDnsFor(_config.Locations[_locationBox.SelectedIndex].Name, _config.DnsOptions);
        _dnsBox.SelectedItem = wanted ?? _config.DnsOptions[0];
    }

    private void ShowStatus(string message, string details)
    {
        _statusLabel.Text = message;
        _detailsBox.Text = details;
        _detailsBox.Visible = false;
        _detailsLink.Visible = details.Length > 0;
    }
}
