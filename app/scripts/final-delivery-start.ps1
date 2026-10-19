param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
& (Join-Path $root 'tools/final_frozen_start.ps1') -NoBrowser:$NoBrowser
exit $LASTEXITCODE
