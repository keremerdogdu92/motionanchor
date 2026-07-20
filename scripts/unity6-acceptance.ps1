param(
    [string]$UnityPath = "C:\Program Files\Unity\Hub\Editor\6000.5.3f1\Editor\Unity.exe"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if (-not (Test-Path $UnityPath -PathType Leaf)) { throw "Unity 6 editor not found: $UnityPath" }
$root = Join-Path $repo "artifacts\acceptance\unity6"
$project = Join-Path $root "project"
$log = Join-Path $root "unity.log"
if (Test-Path $root) { Remove-Item $root -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $project "Assets") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $project "ProjectSettings") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $project "Packages") | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)`r`n[System.IO.File]::WriteAllText((Join-Path $project "ProjectSettings\ProjectVersion.txt"), "m_EditorVersion: 6000.5.3f1`nm_EditorVersionWithRevision: 6000.5.3f1`n", $utf8NoBom)`r`n[System.IO.File]::WriteAllText((Join-Path $project "Packages\manifest.json"), '{"dependencies":{}}`n', $utf8NoBom)
$env:MOTIONANCHOR_UNITY_ACCEPTANCE_ROOT = $project
cargo test --manifest-path src-tauri/Cargo.toml unity_export::tests::writes_unity_6_acceptance_fixture_when_requested -- --exact
if ($LASTEXITCODE -ne 0) { throw "MotionAnchor Unity export fixture generation failed" }
$editorDir = Join-Path $project "Assets\Editor"
New-Item -ItemType Directory -Force $editorDir | Out-Null
Copy-Item (Join-Path $repo "scripts\unity6\MotionAnchorUnity6Acceptance.cs") (Join-Path $editorDir "MotionAnchorUnity6Acceptance.cs") -Force
Get-Process Unity,UnityPackageManager -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$arguments = @("-batchmode", "-nographics", "-projectPath", $project, "-executeMethod", "MotionAnchorUnity6Acceptance.Run", "-logFile", $log)
$unityProcess = Start-Process -FilePath $UnityPath -ArgumentList $arguments -PassThru -Wait
$unityExit = $unityProcess.ExitCode
if ($unityExit -ne 0) {
    if (Test-Path $log) { Get-Content $log -Tail 200 | Out-Host }
    throw "Unity 6 batch acceptance failed with exit code $unityExit"
}
$report = Join-Path $project "artifacts\acceptance\unity6\report.json"
if (-not (Test-Path $report -PathType Leaf)) {
    Get-Content $log -Tail 200 | Out-Host
    throw "Unity 6 acceptance report was not produced"
}
$result = Get-Content $report -Raw | ConvertFrom-Json
if (-not $result.passed) { throw "Unity 6 acceptance report failed: $($result.message)" }
Copy-Item $report (Join-Path $root "report.json") -Force
Write-Output "[PASS] Unity editor: $($result.unityVersion)"
Write-Output "[PASS] AnimationClip: $($result.frameCount) frames at $($result.frameRate) FPS"
Write-Output "[PASS] Loop=$($result.loop), PPU=$($result.pixelsPerUnit), Pivot=$($result.pivot)"
Write-Output "Report: $(Join-Path $root 'report.json')"
