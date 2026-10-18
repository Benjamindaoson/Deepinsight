param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$appRoot=Split-Path $PSScriptRoot -Parent
$dataRoot=Join-Path $appRoot 'data/product'
$backendReady=$false
try{$response=Invoke-RestMethod http://127.0.0.1:7780/api/market/overview -TimeoutSec 2;$backendReady=$null -ne $response.counts}catch{}
if(!$backendReady){& (Join-Path $PSScriptRoot 'product-start.ps1')}
$uiReady=$false
try{$uiReady=(Invoke-WebRequest http://127.0.0.1:3101 -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200}catch{}
if(!$uiReady){
  Start-Process -FilePath wsl.exe -ArgumentList 'bash','/mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataRoot 'evidence/ui-launch.out.log') -RedirectStandardError (Join-Path $dataRoot 'evidence/ui-launch.err.log') | Out-Null
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
