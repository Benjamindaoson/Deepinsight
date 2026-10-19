param([string]$ReceiptPath, [string]$BaselinePath)

# Read-only pre/post deployment check for the URLs and access method already
# shared with reviewers. Credentials are read from Railway in this process and
# are never printed or written to the receipt.
$ErrorActionPreference = 'Stop'

$miniUrl = 'https://deepinsight-mini-web-production.up.railway.app/'
$liteUrl = 'https://lite-frontend-production.up.railway.app/'

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    throw 'Railway CLI is required for the demo contract check.'
}

$queryPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'deploy/railway/demo-contract.graphql'
$railwayResult = & railway api --allow-errors --file $queryPath
if ($LASTEXITCODE -ne 0) { throw 'Railway API check failed.' }
$railwayPayload = ($railwayResult -join "`n") | ConvertFrom-Json
if ($railwayPayload.errors) { throw 'Railway API returned GraphQL errors.' }
$data = $railwayPayload.data
if (-not $data) { throw 'Railway API returned no data.' }

$miniDomains = @($data.mini.domains.serviceDomains | ForEach-Object { $_.domain })
$liteDomains = @($data.liteFrontend.domains.serviceDomains | ForEach-Object { $_.domain })
if ($miniDomains -notcontains ([uri]$miniUrl).Host) { throw 'Mini demo URL is no longer bound to its original service.' }
if ($liteDomains -notcontains ([uri]$liteUrl).Host) { throw 'Lite demo URL is no longer bound to its original service.' }
foreach ($service in @('mini', 'liteFrontend', 'liteBackend')) {
    if ($data.$service.latestDeployment.status -ne 'SUCCESS') { throw "$service latest deployment is not SUCCESS." }
}
if ($data.miniAuto.enabled -or $data.liteAuto.enabled) {
    throw 'Unexpected GitHub auto-deploy is enabled; review deployment isolation before release.'
}

$miniToken = [string]$data.miniVariables.MINI_ADMIN_TOKEN
$litePassword = [string]$data.liteVariables.LONDON_SITE_PASSWORD
if (-not $miniToken -or -not $litePassword) { throw 'An existing demo access variable is missing.' }

if (-not $BaselinePath) {
    $BaselinePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'secrets/demo-access-baseline.json'
}
if (-not (Test-Path -LiteralPath $BaselinePath)) {
    throw 'Protected demo access baseline is missing; credential continuity cannot be verified.'
}
$baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
if ($baseline.schema_version -ne 1) { throw 'Unsupported demo access baseline format.' }
function Get-SaltedDigest([string]$salt, [string]$value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($salt + ':' + $value)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}
if ((Get-SaltedDigest $baseline.mini.salt $miniToken) -ne $baseline.mini.digest) {
    throw 'Mini access code changed from the protected reviewer baseline.'
}
if ((Get-SaltedDigest $baseline.lite.salt $litePassword) -ne $baseline.lite.digest) {
    throw 'Lite reviewer password changed from the protected reviewer baseline.'
}

Add-Type -AssemblyName System.Net.Http
$miniHandler = [System.Net.Http.HttpClientHandler]::new()
$miniHandler.AllowAutoRedirect = $true
$miniHandler.UseCookies = $true
$miniClient = [System.Net.Http.HttpClient]::new($miniHandler)
$liteClient = [System.Net.Http.HttpClient]::new()
$miniClient.Timeout = [TimeSpan]::FromSeconds(20)
$liteClient.Timeout = [TimeSpan]::FromSeconds(20)
try {
    $miniPublic = $miniClient.GetAsync($miniUrl).GetAwaiter().GetResult()
    $miniPublicBody = $miniPublic.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if ([int]$miniPublic.StatusCode -ne 200 -or $miniPublicBody -notmatch '<title>Sign in</title>') {
        throw 'Mini public login page changed or is unavailable.'
    }

    $formValues = [System.Collections.Generic.Dictionary[string,string]]::new()
    $formValues.Add('token', $miniToken)
    $form = [System.Net.Http.FormUrlEncodedContent]::new($formValues)
    try {
        $miniSignedIn = $miniClient.PostAsync($miniUrl + 'login', $form).GetAwaiter().GetResult()
        $miniSignedInBody = $miniSignedIn.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if ([int]$miniSignedIn.StatusCode -ne 200 -or $miniSignedInBody -match '<title>Sign in</title>') {
            throw 'Mini existing access token did not open the demo.'
        }
    } finally { $form.Dispose() }

    $litePublic = $liteClient.GetAsync($liteUrl).GetAwaiter().GetResult()
    $challenge = [string]$litePublic.Headers.WwwAuthenticate
    if ([int]$litePublic.StatusCode -ne 401 -or $challenge -notmatch '^Basic\s') {
        throw 'Lite Basic authentication gate changed unexpectedly.'
    }
    $authorization = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('reviewer:' + $litePassword))
    $liteRequest = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $liteUrl)
    $liteRequest.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Basic', $authorization)
    try {
        $liteSignedIn = $liteClient.SendAsync($liteRequest).GetAwaiter().GetResult()
        if ([int]$liteSignedIn.StatusCode -ne 200) { throw 'Lite existing reviewer credential did not open the demo.' }
    } finally { $liteRequest.Dispose() }

    $overviewRequest = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $liteUrl + 'api/market/overview')
    $overviewRequest.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Basic', $authorization)
    try {
        $overview = $liteClient.SendAsync($overviewRequest).GetAwaiter().GetResult()
        if ([int]$overview.StatusCode -ne 200) { throw 'Lite frontend cannot reach its market backend.' }
    } finally { $overviewRequest.Dispose() }

    $receipt = [ordered]@{
        checked_at_utc = [DateTime]::UtcNow.ToString('o')
        status = 'PASS'
        mini_url = $miniUrl
        mini_service = 'deepinsight-mini-web'
        mini_public_status = [int]$miniPublic.StatusCode
        mini_authenticated_status = [int]$miniSignedIn.StatusCode
        lite_url = $liteUrl
        lite_service = 'lite-frontend'
        lite_public_status = [int]$litePublic.StatusCode
        lite_authenticated_status = [int]$liteSignedIn.StatusCode
        lite_overview_status = [int]$overview.StatusCode
        railway_auto_deploy = $false
        credential_baseline_matched = $true
        credential_values_recorded = $false
    }
    $json = $receipt | ConvertTo-Json -Depth 4
    if ($ReceiptPath) {
        $parent = Split-Path -Parent $ReceiptPath
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Set-Content -LiteralPath $ReceiptPath -Value $json -Encoding utf8
    }
    Write-Output $json
} finally {
    $miniClient.Dispose()
    $liteClient.Dispose()
    $miniToken = $null
    $litePassword = $null
}
