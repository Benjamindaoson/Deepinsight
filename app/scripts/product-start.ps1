$ErrorActionPreference='Stop'
$appRoot=Split-Path $PSScriptRoot -Parent
$dataRoot=Join-Path $appRoot 'data/product'
New-Item -ItemType Directory -Path (Join-Path $dataRoot 'evidence') -Force | Out-Null
$listener=Get-NetTCPConnection -LocalPort 7780 -State Listen -ErrorAction SilentlyContinue
if($listener){throw 'Port 7780 already occupied. Reuse the running product or run product-stop.ps1 first.'}
. (Join-Path $PSScriptRoot 'load-tavily-config.ps1')
$tag=Get-Date -Format 'yyyyMMdd-HHmmss'
$stdout=Join-Path $dataRoot "evidence/runtime-$tag.out.log"
$stderr=Join-Path $dataRoot "evidence/runtime-$tag.err.log"
$process=Start-Process -FilePath (Join-Path $appRoot '.venv/Scripts/python.exe') -ArgumentList '-m','london_product.runtime' -WorkingDirectory $appRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
@{launcher_pid=$process.Id;app_root=$appRoot;stdout=$stdout;stderr=$stderr;started_at=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dataRoot 'runtime-process.json') -Encoding utf8
Write-Output "Starting London product: http://127.0.0.1:7780; logs $stderr"
