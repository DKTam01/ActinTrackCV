<#
ActinTrackCV - Windows one-folder build (PyInstaller).

PREREQUISITES (this script does NOT install anything for you):
  * Windows 10/11
  * Python 3.10+ on PATH (the same interpreter you run the app with)
  * Build environment (runtime deps + PyInstaller):
        python -m pip install -r requirements-build.txt

USAGE (from anywhere; the script finds the repo root itself):
  powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1

OPTIONS:
  -SkipTests   Skip the unittest run (not recommended).
  -KeepOld     Do not delete previous build/ and dist/ActinTrackCV/ first.

OUTPUT:
  dist\ActinTrackCV\ActinTrackCV.exe   (one-folder, windowed)
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$KeepOld
)

$ErrorActionPreference = "Stop"

# This script lives in <repo>\packaging\windows\ ; resolve the repo root from it.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
Set-Location $RepoRoot
Write-Host "Repo root: $RepoRoot"

$Spec = Join-Path $RepoRoot "packaging\windows\actintrackcv.spec"
if (-not (Test-Path $Spec)) { throw "Spec not found: $Spec" }

# Verify tooling is present (fail fast; do not auto-install).
Write-Host "Python version:"
python --version
if ($LASTEXITCODE -ne 0) { throw "Python was not found on PATH." }

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed in this environment. Run: python -m pip install -r requirements-build.txt"
}

if (-not $KeepOld) {
    Write-Host "Cleaning old build/ and dist/ActinTrackCV/ ..."
    $BuildDir = Join-Path $RepoRoot "build"
    $DistDir  = Join-Path $RepoRoot "dist\ActinTrackCV"
    if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
    if (Test-Path $DistDir)  { Remove-Item -Recurse -Force $DistDir }
}

if (-not $SkipTests) {
    Write-Host "Running unit tests ..."
    python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed - aborting build." }
}

Write-Host "Running PyInstaller (one-folder, windowed) ..."
python -m PyInstaller --clean --noconfirm $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$ExePath = Join-Path $RepoRoot "dist\ActinTrackCV\ActinTrackCV.exe"
if (Test-Path $ExePath) {
    Write-Host ""
    Write-Host "Build complete. Launch by double-clicking:"
    Write-Host "  $ExePath"
} else {
    throw "Build finished but expected EXE not found: $ExePath"
}
