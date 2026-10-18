$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path (Split-Path -Parent $projectRoot) 'b1/runtime.pid'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Output 'No B1 PID receipt'; exit 0 }
$runtimePid = [int](Get-Content -LiteralPath $pidPath)
$p = Get-CimInstance Win32_Process -Filter "ProcessId = $runtimePid"
if ($p -and $p.CommandLine -match 'london_data.runtime' -and $p.ExecutablePath -eq (Join-Path $projectRoot '.venv/Scripts/python.exe').Replace('/','\')) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $runtimePid"
    foreach ($child in $children) {
        if ($child.ExecutablePath -eq "$env:WINDIR\System32\conhost.exe") { continue }
        if ($child.CommandLine -notmatch '-m london_data.runtime') { throw 'Unexpected child; inspect before stopping' }
        Stop-Process -Id $child.ProcessId
    }
    Stop-Process -Id $runtimePid -ErrorAction SilentlyContinue
    Write-Output "Stopped B1 $runtimePid and verified runtime child"
}
elseif ($p) { throw 'PID identity mismatch; refusing to stop unrelated process' }
Remove-Item -LiteralPath $pidPath
