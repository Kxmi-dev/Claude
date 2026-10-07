using Lkds.Shared;
using Xunit;

public class SharedTests
{
    private static readonly JoinConfig Config = new(
        "ad.lkds.de",
        "OU=PCs,OU=Computer,OU=LKDS,DC=ad,DC=lkds,DC=de",
        ["test-wadm", "support-wadm"],
        [new LocationEntry("LNBE", "OU=LNBE,OU=PCs,OU=Computer,OU=LKDS,DC=ad,DC=lkds,DC=de")]);

    [Fact]
    public void Konfiguration_wird_aus_angehaengter_EXE_gelesen()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllBytes(path, [0x4D, 0x5A, 1, 2, 3, 4, 5]);
            ConfigPayload.AppendTo(path, Config);

            var read = ConfigPayload.ReadFrom(path);

            Assert.NotNull(read);
            Assert.Equal(Config.Domain, read.Domain);
            Assert.Equal(Config.Users, read.Users);
            Assert.Equal(Config.Locations.Select(l => l.Dn), read.Locations.Select(l => l.Dn));
            Assert.Null(read.PostScript);
        }
        finally { File.Delete(path); }
    }

    [Fact]
    public void Skript_wird_mit_eingebettet_und_alte_Konfiguration_bleibt_lesbar()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllBytes(path, [0x4D, 0x5A]);
            ConfigPayload.AppendTo(path, new JoinConfig(Config.Domain, Config.BaseOu, Config.Users, Config.Locations, "@echo hallo"u8.ToArray()));
            Assert.Equal("@echo hallo"u8.ToArray(), ConfigPayload.ReadFrom(path)!.PostScript);

        }
        finally { File.Delete(path); }
    }

    [Fact]
    public void EXE_ohne_Konfiguration_ergibt_null()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllBytes(path, new byte[100]);
            Assert.Null(ConfigPayload.ReadFrom(path));
        }
        finally { File.Delete(path); }
    }

    [Fact]
    public void Konfiguration_enthaelt_kein_Passwortfeld()
    {
        var text = System.Text.Encoding.UTF8.GetString(ConfigPayload.Build(Config));
        Assert.DoesNotContain("assword", text, StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData("PC-123456", true)]
    [InlineData("NB01", true)]
    [InlineData("", false)]
    [InlineData("123456", false)]
    [InlineData("-PC", false)]
    [InlineData("PC_01", false)]
    [InlineData("PC-ÄÖÜ", false)]
    [InlineData("EinSehrLangerComputername", false)]
    public void Computername_wird_geprueft(string name, bool gueltig)
        => Assert.Equal(gueltig, ComputerNameValidator.Validate(name) is null);

    [Fact]
    public void Vor_dem_Join_werden_OES_und_gewaehlte_DNS_Datei_importiert()
    {
        Assert.Equal([@"C:\LDS\REG\OES.reg", @"C:\LDS\REG\DNS-KWBR.reg"], LdsSteps.PreJoinRegFiles("KWBR"));
        Assert.Equal([@"C:\LDS\REG\OES.reg"], LdsSteps.PreJoinRegFiles(null));
    }

    [Fact]
    public void DNS_Vorauswahl_nach_Standort()
    {
        string[] options = ["LNBE", "LNRE", "KWBR"];
        Assert.Equal("LNBE", LdsSteps.DefaultDnsFor("LNBE", options));
        Assert.Equal("LNRE", LdsSteps.DefaultDnsFor("lnws", options));
        Assert.Equal("KWBR", LdsSteps.DefaultDnsFor("KWBR", options));
        Assert.Null(LdsSteps.DefaultDnsFor("LNSU", options));
    }

    [Theory]
    [InlineData("LNBE", true)]
    [InlineData("..\\x", false)]
    [InlineData("", false)]
    public void DNS_Name_darf_kein_Pfad_sein(string name, bool gueltig)
        => Assert.Equal(gueltig, LdsSteps.IsValidDnsName(name));

    [Fact]
    public void Nachlauf_nach_Neustart_enthaelt_diese_Dateien_nicht_mehr()
    {
        var script = LdsSteps.Build();
        Assert.DoesNotContain("OES.reg", script);
        Assert.DoesNotContain("DNS-", script);
        Assert.Contains("ZENworkspassivLogin.reg", script);
    }

    [Fact]
    public void LDS_Schalter_bleibt_in_der_Konfiguration_erhalten()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllBytes(path, [0x4D, 0x5A]);
            ConfigPayload.AppendTo(path, new JoinConfig("d", "o", ["u"], [], null, true, ["LNBE", "KWBR"]));
            var read = ConfigPayload.ReadFrom(path)!;
            Assert.True(read.RunLdsSteps);
            Assert.Equal(new[] { "LNBE", "KWBR" }, read.DnsOptions);
        }
        finally { File.Delete(path); }
    }
}
