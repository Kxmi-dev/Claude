# Baut den LKDS AD Join Builder als einzelne EXE (inklusive eingebetteter Join-Vorlage).
# Ergebnis: artifacts\LKDS-AD-Join-Builder.exe
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out  = Join-Path $root 'artifacts'
$tmp  = Join-Path $out 'join-vorlage'

if (-not (Test-Path "$root\src\JoinApp\JoinApp.csproj")) {
    throw "Der Ordner 'src' fehlt neben build.ps1 ($root). Bitte das komplette ZIP entpacken und build.cmd aus dem entpackten Ordner starten, nicht einzelne Dateien kopieren."
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }

# 1. Join-EXE (Vorlage) bauen: .NET Framework 4.7.2, nur wenige KB groß
dotnet build "$root\src\JoinApp\JoinApp.csproj" -c Release -o $tmp
if ($LASTEXITCODE -ne 0) { throw 'Build der Join-Vorlage fehlgeschlagen.' }
$template = Join-Path $tmp 'LKDS-Join-Vorlage.exe'

# 2. Builder als Single-File bauen, Vorlage wird eingebettet
dotnet publish "$root\src\Builder\Builder.csproj" -c Release -o $out "-p:JoinTemplatePath=$template"
if ($LASTEXITCODE -ne 0) { throw 'Build des Builders fehlgeschlagen.' }

Remove-Item $tmp -Recurse -Force
Write-Host "Fertig: $out\LKDS-AD-Join-Builder.exe"
