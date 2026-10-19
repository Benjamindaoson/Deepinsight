param(
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\')
$frontend = Join-Path $root 'app\frontend'
$delivery = Join-Path $root 'docs\delivery'
$receiptDir = Join-Path $root 'reports\cleanup'

function Assert-WorkspaceTarget([string]$candidate) {
    $path = [IO.Path]::GetFullPath($candidate)
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing a path outside the workspace: $path"
    }
    if ($path -eq $root -or $path -eq $frontend -or $path -eq $delivery) {
        throw "Refusing a protected directory: $path"
    }
    $parent = Split-Path -Parent $path
    while ($parent.Length -gt $root.Length) {
        $item = Get-Item -LiteralPath $parent -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing a target below a reparse point: $path"
        }
        $parent = Split-Path -Parent $parent
    }
    return $path
}

$candidates = [System.Collections.Generic.List[object]]::new()
Get-ChildItem -LiteralPath $frontend -Force -Directory | Where-Object {
    $_.Name -like '.next-*' -or $_.Name -eq 'node_modules.failed'
} | ForEach-Object { $candidates.Add($_) }

if (Test-Path -LiteralPath $delivery) {
    Get-ChildItem -LiteralPath $delivery -Force -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like '.next*' -or $_.Name -in @('node_modules', 'node_modules.failed', '__pycache__', '.pytest_cache', '.mypy_cache')
        } | ForEach-Object { $candidates.Add($_) }
}

foreach ($area in @('app', 'b0', 'b1', 'reports')) {
    $base = Join-Path $root $area
    if (-not (Test-Path -LiteralPath $base)) { continue }
    Get-ChildItem -LiteralPath $base -Force -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('__pycache__', '.pytest_cache', '.mypy_cache') } |
        ForEach-Object { $candidates.Add($_) }
}

$targets = [System.Collections.Generic.List[object]]::new()
foreach ($candidate in ($candidates | Sort-Object { $_.FullName.Length })) {
    $path = Assert-WorkspaceTarget $candidate.FullName
    $nested = $false
    foreach ($existing in $targets) {
        if ($path.StartsWith($existing.path + '\', [StringComparison]::OrdinalIgnoreCase)) {
            $nested = $true
            break
        }
    }
    if ($nested) { continue }
    $size = 0L
    if (-not ($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        $measure = Get-ChildItem -LiteralPath $path -Force -Recurse -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum
        $size = [long]$measure.Sum
    }
    $targets.Add([pscustomobject]@{
        path = $path
        kind = if ($candidate.Name -like '.next*') { 'next_build' } elseif ($candidate.Name -like 'node_modules*') { 'dependency_copy' } else { 'python_cache' }
        size_bytes = $size
        reparse_point = [bool]($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint)
        status = 'pending'
    })
}

New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$receipt = Join-Path $receiptDir ("generated-artifacts-$stamp.json")
$manifest = [ordered]@{
    workspace = $root
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    mode = if ($Execute) { 'execute' } else { 'dry_run' }
    protected = @('app/frontend/.next', 'app/frontend/node_modules', 'app/data', 'b0/evidence', 'b1/evidence', 'upstream', '.git')
    total_targets = $targets.Count
    measured_bytes = [long](($targets | Measure-Object -Property size_bytes -Sum).Sum)
    targets = $targets
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8

if ($Execute) {
    foreach ($target in $targets) {
        try {
            $path = Assert-WorkspaceTarget $target.path
            if ($target.reparse_point) {
                Remove-Item -LiteralPath $path -Force -ErrorAction Stop
            } else {
                Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
            }
            $target.status = 'removed'
        } catch {
            $target.status = 'failed'
            $target | Add-Member -NotePropertyName error -NotePropertyValue $_.Exception.GetType().Name -Force
        }
    }
    $manifest.targets = $targets
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
}

[pscustomobject]@{
    receipt = $receipt
    mode = $manifest.mode
    total_targets = $targets.Count
    measured_gib = [math]::Round($manifest.measured_bytes / 1GB, 3)
    removed = @($targets | Where-Object status -eq 'removed').Count
    failed = @($targets | Where-Object status -eq 'failed').Count
} | ConvertTo-Json

if ($Execute -and @($targets | Where-Object status -eq 'failed').Count) { exit 1 }
