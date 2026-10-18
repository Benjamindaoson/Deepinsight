$ErrorActionPreference='Stop'
$appRoot=Split-Path $PSScriptRoot -Parent
$listener=Get-NetTCPConnection -LocalPort 7780 -State Listen -ErrorAction SilentlyContinue
if(!$listener){Write-Output 'Product port 7780 is not listening';exit 0}
$target=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
if($target.CommandLine -notmatch 'london_product\.runtime' -or $target.ExecutablePath -notlike '*python*'){
    throw 'Port owner is not the expected product runtime; no process stopped'
}
Stop-Process -Id $target.ProcessId
Write-Output "Stopped verified London product runtime PID $($target.ProcessId)"
