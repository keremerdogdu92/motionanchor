$ErrorActionPreference = "Stop"

$WorkerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $WorkerRoot
$Python = Join-Path $WorkerRoot ".venv\Scripts\python.exe"
$DistDir = Join-Path $RepoRoot "src-tauri\binaries"
$WorkDir = Join-Path $WorkerRoot "build"
$SpecDir = Join-Path $WorkerRoot "build"

if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $WorkerRoot ".venv")
}

& $Python -m pip install -r (Join-Path $WorkerRoot "requirements-build.txt")
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name "motionanchor-worker-x86_64-pc-windows-msvc" `
    --paths $WorkerRoot `
    --distpath $DistDir `
    --workpath $WorkDir `
    --specpath $SpecDir `
    (Join-Path $WorkerRoot "entrypoint.py")

Write-Host "Built worker: $DistDir\motionanchor-worker-x86_64-pc-windows-msvc.exe"
