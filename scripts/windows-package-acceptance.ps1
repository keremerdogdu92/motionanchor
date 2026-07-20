param([switch]$Build)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if ($Build) { npm run tauri:build; if ($LASTEXITCODE -ne 0) { throw "tauri build failed" } }
$release = Join-Path $repo "src-tauri\target\release"
$app = Join-Path $release "motionanchor.exe"
$worker = Join-Path $release "motionanchor-worker.exe"
$msi = Get-ChildItem (Join-Path $release "bundle\msi") -Filter "MotionAnchor_*.msi" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$nsis = Get-ChildItem (Join-Path $release "bundle\nsis") -Filter "MotionAnchor_*-setup.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
foreach ($path in @($app, $worker)) { if (-not (Test-Path $path -PathType Leaf)) { throw "missing package artifact: $path" } }
if (-not $msi -or -not $nsis) { throw "MSI or NSIS bundle is missing" }
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $worker
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$sidecar = [System.Diagnostics.Process]::new(); $sidecar.StartInfo = $psi
if (-not $sidecar.Start()) { throw "failed to start packaged worker" }
$ready = $sidecar.StandardOutput.ReadLine() | ConvertFrom-Json
if ($ready.type -ne "worker.ready") { throw "unexpected worker handshake: $($ready.type)" }
$pingId = "package-acceptance-ping"
$sidecar.StandardInput.WriteLine((@{protocol_version="1.0";message_id=$pingId;type="worker.ping";job_id=$null;payload=@{}} | ConvertTo-Json -Compress))
$pong = $sidecar.StandardOutput.ReadLine() | ConvertFrom-Json
if ($pong.type -ne "worker.pong" -or $pong.message_id -ne $pingId) { throw "packaged worker ping failed" }
$sidecar.StandardInput.WriteLine((@{protocol_version="1.0";message_id="package-acceptance-stop";type="worker.shutdown";job_id=$null;payload=@{}} | ConvertTo-Json -Compress))
$stopped = $sidecar.StandardOutput.ReadLine() | ConvertFrom-Json
if ($stopped.type -ne "worker.stopped") { throw "packaged worker shutdown failed" }
$sidecar.WaitForExit(10000) | Out-Null
if (-not $sidecar.HasExited -or $sidecar.ExitCode -ne 0) { throw "packaged worker did not exit cleanly" }
$appProcess = Start-Process -FilePath $app -PassThru
Start-Sleep -Seconds 4
if ($appProcess.HasExited) { throw "release application exited during launch smoke test with code $($appProcess.ExitCode)" }
Stop-Process -Id $appProcess.Id -Force
$extractRoot = Join-Path $repo "artifacts\acceptance\windows-package\msi-extract"
if (Test-Path $extractRoot) { Remove-Item $extractRoot -Recurse -Force }
New-Item -ItemType Directory -Force $extractRoot | Out-Null
$msiArgs = "/a `"$($msi.FullName)`" /qn TARGETDIR=`"$extractRoot`""
$msiProcess = Start-Process msiexec.exe -ArgumentList $msiArgs -Wait -PassThru
if ($msiProcess.ExitCode -ne 0) { throw "MSI administrative extraction failed: $($msiProcess.ExitCode)" }
$installedApp = Get-ChildItem $extractRoot -Recurse -Filter "motionanchor.exe" | Select-Object -First 1
$installedWorker = Get-ChildItem $extractRoot -Recurse -Filter "motionanchor-worker.exe" | Select-Object -First 1
if (-not $installedApp -or -not $installedWorker) { throw "MSI payload does not contain application and worker" }
$reportPath = Join-Path $repo "artifacts\acceptance\windows-package\report.json"
$report = [ordered]@{passed=$true;generated_at=(Get-Date).ToUniversalTime().ToString("o");app=@{path=$app;sha256=(Get-FileHash $app -Algorithm SHA256).Hash;bytes=(Get-Item $app).Length};worker=@{path=$worker;sha256=(Get-FileHash $worker -Algorithm SHA256).Hash;bytes=(Get-Item $worker).Length;protocol=$ready.protocol_version};msi=@{path=$msi.FullName;sha256=(Get-FileHash $msi.FullName -Algorithm SHA256).Hash;bytes=$msi.Length;extracted_app=$installedApp.FullName;extracted_worker=$installedWorker.FullName};nsis=@{path=$nsis.FullName;sha256=(Get-FileHash $nsis.FullName -Algorithm SHA256).Hash;bytes=$nsis.Length}}
$report | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $reportPath
Write-Output "[PASS] release application launch"
Write-Output "[PASS] packaged worker ready/ping/shutdown"
Write-Output "[PASS] MSI payload application + worker"
Write-Output "[PASS] MSI and NSIS hashes recorded"
Write-Output "Report: $reportPath"
