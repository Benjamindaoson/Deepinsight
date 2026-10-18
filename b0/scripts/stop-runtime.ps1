$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$listeners=@(Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue)
foreach($listener in $listeners){
  $p=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
  $ownedLauncher=[int](Get-Content (Join-Path $root 'b0/evidence/logs/runtime.pid'))
  $parent=Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
  $ownedChild=($p.ParentProcessId -eq $ownedLauncher -and $parent.ExecutablePath -like "$root\b0\.venv-win\*" -and $p.CommandLine -match '(agno_assist|native_runtime)\.py')
  $ownedDirect=($p.ProcessId -eq $ownedLauncher -and $p.ExecutablePath -like "$root\b0\.venv-win\*" -and $p.CommandLine -match '(agno_assist|native_runtime)\.py')
  if(-not ($ownedDirect -or $ownedChild)){throw 'Listener does not belong to recorded B0 launcher; refusing to stop it.'}
  Stop-Process -Id $p.ProcessId
  Write-Output "Stopped B0 listener PID=$($p.ProcessId)"
}
