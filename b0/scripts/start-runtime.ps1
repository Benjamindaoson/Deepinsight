param([switch]$NativeTests)
$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python=Join-Path $root 'b0/.venv-win/Scripts/python.exe'
if(Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue){throw 'Port 7777 occupied; no process was terminated.'}
$folder=if($NativeTests){'b0/smoke-tests'}else{'b0/runtime-demo'}
$file=if($NativeTests){'native_runtime.py'}else{'agno_assist.py'}
$p=Start-Process -FilePath $python -ArgumentList @('-u',$file) -WorkingDirectory (Join-Path $root $folder) -RedirectStandardOutput (Join-Path $root 'b0/evidence/logs/runtime-stdout.log') -RedirectStandardError (Join-Path $root 'b0/evidence/logs/runtime-stderr.log') -WindowStyle Hidden -PassThru
$p.Id|Set-Content (Join-Path $root 'b0/evidence/logs/runtime.pid')
Write-Output "Runtime started PID=$($p.Id); log=b0/evidence/logs/runtime-stderr.log"
