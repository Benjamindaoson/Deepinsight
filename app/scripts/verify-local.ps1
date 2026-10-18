$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$evidenceRoot = Join-Path (Split-Path -Parent $projectRoot) 'b1/evidence/tests'
New-Item -ItemType Directory -Force $evidenceRoot | Out-Null
Push-Location $projectRoot
try {
    $commands = @(
        @{ name='locked-environment'; executable='uv'; arguments=@('pip','sync','--python','.venv/Scripts/python.exe','requirements.lock.txt') },
        @{ name='dependency-compatibility'; executable='uv'; arguments=@('pip','check','--python','.venv/Scripts/python.exe') },
        @{ name='compile'; executable='.venv/Scripts/python.exe'; arguments=@('-m','compileall','-q','london_data','scripts','tests') },
        @{ name='pytest'; executable='.venv/Scripts/python.exe'; arguments=@('-m','pytest','-q','--junitxml=../b1/evidence/tests/junit.xml') },
        @{ name='openspec'; executable='openspec'; arguments=@('validate','b1-market-data-foundation','--strict') },
        @{ name='cli-query'; executable='.venv/Scripts/python.exe'; arguments=@('-m','london_data.cli','query') },
        @{ name='boundaries'; executable='.venv/Scripts/python.exe'; arguments=@('scripts/verify_delivery.py') }
    )
    $results = @()
    foreach ($command in $commands) {
        $started = [DateTime]::UtcNow.ToString('o')
        $log = Join-Path $evidenceRoot ($command.name + '.log')
        $runArguments = $command.arguments
        & $command.executable @runArguments *> $log
        $exitCode = $LASTEXITCODE
        $results += @{ name=$command.name; command=($command.executable+' '+($command.arguments -join ' ')); cwd=$projectRoot; started_at=$started; finished_at=[DateTime]::UtcNow.ToString('o'); exit_code=$exitCode; log=$log }
        Write-Output ($command.name+': exit '+$exitCode)
    }
    $results | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $evidenceRoot 'command-results.json')
    if ($results | Where-Object { $_.exit_code -ne 0 }) { exit 1 }
} finally { Pop-Location }
