<#
.SYNOPSIS
  Remove agent-filtered repos from labeling_samples/Python (per CSV) and merge in relabeling_samples/Python.

.DESCRIPTION
  1. Deletes each repo folder listed in removed_repos_in_python_labeling_samples.csv from
     outputs/rq3/labeling_samples/Python/<subfolder>/<owner>__<repo>/.
  2. Copies every file under outputs/rq3/relabeling_samples/Python into
     outputs/rq3/labeling_samples/Python preserving relative paths. Existing destination files
     are skipped (merge, no overwrite).

.PARAMETER RepoRoot
  Path to the repository root. Defaults to the parent of the utils/ directory containing this script.

.PARAMETER DryRun
  If set, only prints actions without deleting or copying.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "",
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$csvPath = Join-Path $RepoRoot "outputs\raw_data_filtered_out\removed_repos_in_python_labeling_samples.csv"
$labelingRoot = Join-Path $RepoRoot "outputs\rq3\labeling_samples\Python"
$relabelingRoot = Join-Path $RepoRoot "outputs\rq3\relabeling_samples\Python"

if (-not (Test-Path $csvPath)) {
    throw "CSV not found: $csvPath"
}
if (-not (Test-Path $labelingRoot)) {
    throw "Labeling root not found: $labelingRoot"
}
if (-not (Test-Path $relabelingRoot)) {
    throw "Relabeling root not found: $relabelingRoot"
}

function Get-RelativePathFromRoot {
    param([string] $Root, [string] $FullPath)
    $rootNorm = $Root.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    if (-not $FullPath.StartsWith($rootNorm, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path not under root: $FullPath"
    }
    $rel = $FullPath.Substring($rootNorm.Length).TrimStart([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    return $rel
}

# --- Step 1: delete repo folders from CSV ---
$rows = Import-Csv -Path $csvPath
$deleted = @()
$missing = @()

foreach ($row in $rows) {
    $repo = ($row.repo).Trim()
    $subfolder = ($row.subfolder).Trim()
    if (-not $repo -or -not $subfolder) { continue }

    $dirName = $repo.Replace("/", "__")
    $target = Join-Path (Join-Path $labelingRoot $subfolder) $dirName

    if (-not (Test-Path $target)) {
        $missing += $target
        Write-Warning "Expected folder not found (skip delete): $target"
        continue
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would remove: $target"
    }
    else {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Host "Removed: $target"
    }
    $deleted += $target
}

Write-Host ""
Write-Host "=== Delete summary ==="
Write-Host "Folders removed: $($deleted.Count)"
if ($missing.Count -gt 0) {
    Write-Host "Missing on disk: $($missing.Count)"
}

# --- Step 2: merge relabeling_samples into labeling_samples ---
$copied = 0
$skipped = 0
$failed = @()

$relabelingRootNorm = $relabelingRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$allFiles = Get-ChildItem -LiteralPath $relabelingRoot -Recurse -File -Force
foreach ($file in $allFiles) {
    try {
        $rel = Get-RelativePathFromRoot -Root $relabelingRootNorm -FullPath $file.FullName
    }
    catch {
        $failed += "Relative path failed for $($file.FullName): $_"
        continue
    }

    $dest = Join-Path -Path $labelingRoot -ChildPath $rel

    if (Test-Path -LiteralPath $dest) {
        Write-Warning "Skip existing file: $dest"
        $skipped++
        continue
    }

    $destDir = Split-Path -Parent $dest
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would copy: $($file.FullName) -> $dest"
    }
    else {
        if (-not (Test-Path -LiteralPath $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
    }
    $copied++
}

Write-Host ""
Write-Host "=== Copy summary ==="
Write-Host "Files copied: $copied"
Write-Host "Files skipped (already exist): $skipped"
if ($failed.Count -gt 0) {
    Write-Host "Errors:"
    $failed | ForEach-Object { Write-Host $_ }
}

# --- Final counts ---
if (-not $DryRun) {
    Write-Host ""
    Write-Host "=== SKILL.md counts under labeling_samples/Python ==="
    foreach ($bucket in @("A", "B", "both")) {
        $bucketPath = Join-Path $labelingRoot $bucket
        if (Test-Path $bucketPath) {
            $n = (Get-ChildItem -LiteralPath $bucketPath -Recurse -Filter "SKILL.md" -File -Force | Measure-Object).Count
            Write-Host "  $bucket : $n"
        }
    }
}
