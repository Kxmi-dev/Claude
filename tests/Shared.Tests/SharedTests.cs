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
            Assert.Equal(Config.Locations, read.Locations);
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
        var json = System.Text.Encoding.UTF8.GetString(ConfigPayload.Build(Config));
        Assert.DoesNotContain("assword", json, StringComparison.OrdinalIgnoreCase);
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
}
