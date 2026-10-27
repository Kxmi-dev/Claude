# Baut Join-Vorlage und Builder als Single-File-EXEs. Benötigt das .NET SDK 9.
$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'artifacts'
if (Test-Path $out) { Remove-Item $out -Recurse -Force }

dotnet publish "$PSScriptRoot\src\JoinApp"  -c Release -o "$out\joinapp"
dotnet publish "$PSScriptRoot\src\Builder"  -c Release -o "$out\LKDS-Join-Builder"

# Die Join-EXE ist die Vorlage, an die der Builder die Konfiguration anhängt.
Copy-Item "$out\joinapp\JoinApp.exe" "$out\LKDS-Join-Builder\JoinApp.template"
Write-Host "Fertig: $out\LKDS-Join-Builder"
