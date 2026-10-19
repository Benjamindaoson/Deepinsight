param([int]$BackendPort=8000,[int]$FrontendPort=3101)
$root=Split-Path $PSScriptRoot -Parent
$record=Join-Path $root "reports/offline-process-$BackendPort-$FrontendPort.json"
if(!(Test-Path $record)){throw "No launcher receipt for $BackendPort/$FrontendPort"}
$state=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach($id in @($state.backend_pid,$state.frontend_pid)){
  $p=Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
  if($p -and $p.CommandLine -match 'london_product\.offline_runtime|node_modules[\\/]next[\\/]dist[\\/]bin[\\/]next'){
    Stop-Process -Id $id -ErrorAction Stop
    Write-Output "Stopped PID $id"
  }elseif($p){Write-Warning "PID $id no longer matches the launcher receipt; left running."}
}
