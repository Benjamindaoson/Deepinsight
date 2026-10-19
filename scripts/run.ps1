param([int]$BackendPort=8000,[int]$FrontendPort=3101,[string]$BuildDir='.next',[switch]$Offline)
$ErrorActionPreference='Stop'
if (-not $Offline) {
  & (Join-Path $PSScriptRoot 'run-chat-models.ps1')
  return
}
$root=Split-Path $PSScriptRoot -Parent
$app=Join-Path $root 'app'
$front=Join-Path $app 'frontend'
$py=Join-Path $app '.venv/Scripts/python.exe'
$next=Join-Path $front 'node_modules/next/dist/bin/next'
if(!(Test-Path $py)){throw 'Project .venv missing; install app/requirements-product.lock.txt into app/.venv first.'}
if(!(Test-Path $next)){throw 'Frontend node_modules missing; run pnpm install --frozen-lockfile in app/frontend first.'}
if(!(Test-Path (Join-Path $front "$BuildDir/BUILD_ID"))){throw "Frontend production build $BuildDir missing; run pnpm build in app/frontend first."}
foreach($port in @($BackendPort,$FrontendPort)){
  $probe=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$port)
  try{$probe.Start()}catch{throw "Port $port cannot be bound on loopback ($($_.Exception.InnerException.Message)); no existing process was restarted."}finally{$probe.Stop()}
}
New-Item -ItemType Directory -Force (Join-Path $root 'reports') | Out-Null
$env:NEXT_PUBLIC_MARKET_API_URL="http://127.0.0.1:$BackendPort/api/market"
$env:NEXT_PUBLIC_AGENT_OS_URL="http://127.0.0.1:$BackendPort"
$env:NEXT_TELEMETRY_DISABLED='1'
$env:DEEPINSIGHT_NEXT_DIST_DIR=$BuildDir
# The offline compatibility routes never call a model or search API. Clear
# credentials only in this launcher process so the demonstration is provably offline.
foreach($name in @(
  'OPENAI_API_KEY','TOAPIS_API_KEY','TAVILY_API_KEY','LONDON_TAVILY_API_KEY',
  'LONDON_JEV_API_KEY','LONDON_EPC_TOKEN','LONDON_NOTIFICATION_URL'
)){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
$env:LONDON_TAVILY_ENABLED='0'
$env:LONDON_JEV_SHADOW_ENABLED='0'
$env:LONDON_JEV_ROUTING_ENABLED='0'
$back=$null
$ui=$null
try {
  $back=Start-Process -FilePath $py -ArgumentList @('-m','london_product.offline_runtime','--port',"$BackendPort",'--frontend-port',"$FrontendPort") -WorkingDirectory $app -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'reports/offline-backend.out.log') -RedirectStandardError (Join-Path $root 'reports/offline-backend.err.log') -PassThru
  $node=(Get-Command node.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
  $ui=Start-Process -FilePath $node -ArgumentList @('node_modules/next/dist/bin/next','start','-p',"$FrontendPort",'-H','127.0.0.1') -WorkingDirectory $front -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'reports/offline-frontend.out.log') -RedirectStandardError (Join-Path $root 'reports/offline-frontend.err.log') -PassThru
  @{backend_pid=$back.Id;frontend_pid=$ui.Id;backend_port=$BackendPort;frontend_port=$FrontendPort;started_at=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root "reports/offline-process-$BackendPort-$FrontendPort.json") -Encoding utf8
  $ready=$false
  for($attempt=0;$attempt -lt 45;$attempt++){
    try{
      $health=Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
      $page=Invoke-WebRequest "http://127.0.0.1:$FrontendPort/ask" -UseBasicParsing -TimeoutSec 2
      if($health.mode -eq 'mock' -and $page.StatusCode -eq 200){$ready=$true;break}
    }catch{}
    Start-Sleep -Seconds 1
  }
  if(!$ready){throw 'Offline product did not become ready; inspect reports/offline-*.log.'}
  Write-Output "Offline product ready: http://127.0.0.1:$FrontendPort/ask (API $BackendPort)"
} catch {
  foreach($process in @($ui,$back)){
    if($null -ne $process -and !$process.HasExited){Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue}
  }
  throw
}
