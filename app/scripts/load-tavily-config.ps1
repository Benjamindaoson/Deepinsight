param([string]$ConfigPath = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'secrets/tavily.json'))
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        if (-not ($config.api_key -is [string]) -or [string]::IsNullOrWhiteSpace($config.api_key) -or -not ($config.enabled -is [bool])) {
            throw 'Invalid configuration'
        }
    } catch {
        throw 'Invalid local Tavily configuration; expected api_key string and enabled boolean.'
    }
    # This project file is authoritative; never inherit an old/generic key.
    $env:LONDON_TAVILY_API_KEY = $config.api_key.Trim()
    $env:LONDON_TAVILY_ENABLED = if ($config.enabled) { '1' } else { '0' }
}
