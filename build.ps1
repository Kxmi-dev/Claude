# Baut den LKDS AD Join Builder als einzelne EXE (inklusive eingebetteter Join-Vorlage).
# Ergebnis: artifacts\LKDS-AD-Join-Builder.exe
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out  = Join-Path $root 'artifacts'
$tmp  = Join-Path $out 'join-vorlage'

if (Test-Path $out) { Remove-Item $out -Recurse -Force }

# 1. Join-EXE (Vorlage) als Single-File bauen
dotnet publish "$root\src\JoinApp\JoinApp.csproj" -c Release -o $tmp
if ($LASTEXITCODE -ne 0) { throw 'Build der Join-Vorlage fehlgeschlagen.' }
$template = Join-Path $tmp 'LKDS-Join-Vorlage.exe'

# 2. Builder als Single-File bauen, Vorlage wird eingebettet
dotnet publish "$root\src\Builder\Builder.csproj" -c Release -o $out "-p:JoinTemplatePath=$template"
if ($LASTEXITCODE -ne 0) { throw 'Build des Builders fehlgeschlagen.' }

Remove-Item $tmp -Recurse -Force
Write-Host "Fertig: $out\LKDS-AD-Join-Builder.exe"
