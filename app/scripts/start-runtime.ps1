$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$b1Root = Join-Path (Split-Path -Parent $projectRoot) 'b1'
$logs = Join-Path $b1Root 'evidence/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
if (Get-NetTCPConnection -State Listen -LocalPort 7778 -ErrorAction SilentlyContinue) { throw 'Port 7778 occupied; inspect before starting another runtime.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$p = Start-Process -FilePath (Join-Path $projectRoot '.venv/Scripts/python.exe') -ArgumentList @('-m','london_data.runtime') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "runtime-$stamp.out.log") -RedirectStandardError (Join-Path $logs "runtime-$stamp.err.log")
$p.Id | Set-Content (Join-Path $b1Root 'runtime.pid')
Write-Output "B1 Runtime process $($p.Id), loopback http://127.0.0.1:7778"
