param([switch]$NoBrowser,[switch]$Legacy)
$ErrorActionPreference='Stop'
if (-not $Legacy) {
  $projectRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
  & (Join-Path $projectRoot 'scripts/run-chat-models.ps1')
  return
}
$appRoot=Split-Path $PSScriptRoot -Parent
$dataRoot=Join-Path $appRoot 'data/product'
$backendReady=$false
try{$response=Invoke-RestMethod http://127.0.0.1:7780/api/market/overview -TimeoutSec 2;$backendReady=$null -ne $response.counts}catch{}
if(!$backendReady){& (Join-Path $PSScriptRoot 'product-start.ps1')}
$uiReady=$false
try{$uiReady=(Invoke-WebRequest http://127.0.0.1:3101 -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200}catch{}
if(!$uiReady){
  $uiRoot=Join-Path $appRoot 'frontend'
  $uiStdout=Join-Path $dataRoot 'evidence/ui-launch.out.log'
  $uiStderr=Join-Path $dataRoot 'evidence/ui-launch.err.log'
  $nextBin=Join-Path $uiRoot 'node_modules/next/dist/bin/next'
  $nodeCmd=$null
  $detected=Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if($detected){$nodeCmd=$detected.Source}
  if(!$nodeCmd -and (Test-Path 'C:\Program Files\nodejs\node.exe')){$nodeCmd='C:\Program Files\nodejs\node.exe'}
  if($nodeCmd -and (Test-Path $nextBin)){
    $env:NEXT_TELEMETRY_DISABLED='1'
    $argLine='"' + $nextBin + '" start --port 3101 --hostname 127.0.0.1'
    Start-Process -FilePath $nodeCmd -ArgumentList $argLine -WorkingDirectory $uiRoot -WindowStyle Hidden -RedirectStandardOutput $uiStdout -RedirectStandardError $uiStderr | Out-Null
    Write-Output "Product UI starting via local Node: $nodeCmd"
  }else{
    Write-Output 'Local Node or Next build not found; falling back to WSL'
    Start-Process -FilePath wsl.exe -ArgumentList 'bash','/mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh' -WindowStyle Hidden -RedirectStandardOutput $uiStdout -RedirectStandardError $uiStderr | Out-Null
  }
}
for($attempt=0;$attempt -lt 15;$attempt++){
  try{
    $ready=Invoke-RestMethod http://127.0.0.1:7780/api/market/overview -TimeoutSec 2
    $page=Invoke-WebRequest http://127.0.0.1:3101 -UseBasicParsing -TimeoutSec 2
    if($ready.counts -and $page.StatusCode -eq 200){
      if(!$NoBrowser){Start-Process 'http://127.0.0.1:3101'}
      Write-Output 'London Market ready: http://127.0.0.1:3101';exit 0
    }
  }catch{}
  Start-Sleep -Seconds 1
}
throw 'Product did not become ready. Inspect app/data/product/evidence runtime and UI logs.'
