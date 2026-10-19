param([switch]$Build,[string]$ReleasePointer)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'app/.venv/Scripts/python.exe'
$resolveArgs = @((Join-Path $PSScriptRoot 'release_manifest.py'))
if ($ReleasePointer) { $resolveArgs += @('--pointer',$ReleasePointer) }
$releaseJson = & $pythonPath @resolveArgs
if ($LASTEXITCODE -ne 0) { throw 'Official release validation failed; no service was started.' }
$release = $releaseJson | ConvertFrom-Json
$frontendRoot = $release.frontend
$nodePath = (Get-Command node).Source
$nextPath = Join-Path $frontendRoot 'node_modules/next/dist/bin/next'
$env:NEXT_PUBLIC_AGENT_OS_URL = 'http://127.0.0.1:7788'
$env:NEXT_PUBLIC_MARKET_API_URL = 'http://127.0.0.1:7788/api/market'
$env:DEEPINSIGHT_NEXT_DIST_DIR = $release.build_dir
$env:NEXT_TELEMETRY_DISABLED = '1'
if ($ReleasePointer) { $env:LONDON_RELEASE_POINTER = $ReleasePointer }
else { Remove-Item Env:LONDON_RELEASE_POINTER -ErrorAction SilentlyContinue }
if (-not $env:LONDON_MODEL_CONFIG) { $env:LONDON_MODEL_CONFIG = Join-Path $projectRoot 'secrets/model.deepseek-acceptance-20261019.json' }
foreach ($portNumber in @(7788, 3105)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $portNumber -ErrorAction SilentlyContinue) { throw "Port $portNumber is already running. Existing services were not terminated. Open http://127.0.0.1:3105 or inspect the saved PID file." }
}
if ($Build) {
    throw 'An accepted release is immutable. Build and verify a new candidate before changing the active release.'
}
if (-not (Test-Path (Join-Path $frontendRoot "$($release.build_dir)/BUILD_ID"))) { throw 'Verified production build is missing.' }
$logRoot = Join-Path $projectRoot 'app/data/personal-model-launch'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendLog = Join-Path $logRoot "backend-$runStamp.log"
$frontendLog = Join-Path $logRoot "frontend-$runStamp.log"
$backendProcess = $null
$frontendProcess = $null
try {
$backendProcess = Start-Process -WindowStyle Hidden -FilePath $pythonPath -ArgumentList @('scripts/run_personal_model_product.py') -WorkingDirectory $projectRoot -RedirectStandardOutput $backendLog -RedirectStandardError (Join-Path $logRoot "backend-error-$runStamp.log") -PassThru
$frontendProcess = Start-Process -WindowStyle Hidden -FilePath $nodePath -ArgumentList @($nextPath, 'start', '-H', '127.0.0.1', '-p', '3105') -WorkingDirectory $frontendRoot -RedirectStandardOutput $frontendLog -RedirectStandardError (Join-Path $logRoot "frontend-error-$runStamp.log") -PassThru
@{ backend = $backendProcess.Id; frontend = $frontendProcess.Id; url = 'http://127.0.0.1:3105'; scheduler = 'disabled'; backend_log = $backendLog; frontend_log = $frontendLog } | ConvertTo-Json | Set-Content (Join-Path $logRoot 'processes.json')
$startupDeadline = [DateTime]::UtcNow.AddSeconds(30)
$serviceReady = $false
do {
    try {
        $apiHealth = Invoke-RestMethod 'http://127.0.0.1:7788/api/market/release' -TimeoutSec 2
        $webHealth = Invoke-WebRequest 'http://127.0.0.1:3105' -UseBasicParsing -TimeoutSec 2
        if ($apiHealth.manifest_sha256 -eq $release.manifest_sha256 -and $webHealth.StatusCode -eq 200 -and $webHealth.Content.Contains($release.release_id)) { $serviceReady = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $startupDeadline)
if (-not $serviceReady) { throw "Startup did not pass health checks. Inspect $logRoot; no success was claimed." }
# Windows venv launchers can own a child interpreter which binds the port.
# Persist the listeners as well as launcher PIDs so later cleanup is precise.
$actualBackend = (Get-NetTCPConnection -State Listen -LocalPort 7788 | Select-Object -First 1).OwningProcess
$actualFrontend = (Get-NetTCPConnection -State Listen -LocalPort 3105 | Select-Object -First 1).OwningProcess
@{ backend = $actualBackend; backend_launcher = $backendProcess.Id; frontend = $actualFrontend; frontend_launcher = $frontendProcess.Id; url = 'http://127.0.0.1:3105'; scheduler = 'disabled'; backend_log = $backendLog; frontend_log = $frontendLog } | ConvertTo-Json | Set-Content (Join-Path $logRoot 'processes.json')
Write-Host 'DeepInsight Lite: http://127.0.0.1:3105/?agent=london-market-agent&db_id=london-product'
} catch {
    foreach ($createdProcess in @($frontendProcess,$backendProcess)) {
        if ($null -ne $createdProcess) {
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$($createdProcess.Id)" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id $createdProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
    throw
}
