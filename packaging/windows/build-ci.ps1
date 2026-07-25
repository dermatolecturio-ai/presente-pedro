# Build CI (AppVeyor / GitHub Actions) — gera PresentePedro-windows.zip na raiz do repo
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

$Python = $env:PYTHON
if (-not $Python -or -not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$Scripts = Join-Path (Split-Path -Parent $Python) "Scripts"
if (Test-Path $Scripts) {
    $env:PATH = "$Scripts;$env:PATH"
}

Write-Host "==> Python: $Python"
& $Python --version

# --- ffmpeg ---
$FfmpegRoot = Join-Path $PSScriptRoot "ffmpeg"
$FfmpegBin = Join-Path $FfmpegRoot "bin"
$FfmpegExe = Join-Path $FfmpegBin "ffmpeg.exe"

if (-not (Test-Path $FfmpegExe)) {
    Write-Host "==> Baixando ffmpeg essentials"
    $Zip = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
    $Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    Invoke-WebRequest -Uri $Url -OutFile $Zip
    $Extract = Join-Path $env:TEMP "ffmpeg-extract"
    if (Test-Path $Extract) { Remove-Item -Recurse -Force $Extract }
    Expand-Archive -Path $Zip -DestinationPath $Extract -Force
    $Inner = Get-ChildItem $Extract -Directory | Select-Object -First 1
    if (-not $Inner) { throw "ffmpeg extract failed" }
    New-Item -ItemType Directory -Force -Path $FfmpegRoot | Out-Null
    if (Test-Path $FfmpegBin) { Remove-Item -Recurse -Force $FfmpegBin }
    Copy-Item -Recurse (Join-Path $Inner.FullName "bin") $FfmpegBin
}

if (-not (Test-Path $FfmpegExe)) { throw "ffmpeg.exe missing" }
Write-Host "==> ffmpeg ok: $FfmpegExe"

# --- PyInstaller ---
Write-Host "==> PyInstaller (pode demorar)"
$Spec = Join-Path $PSScriptRoot "PresentePedro.spec"
& $Python -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit $LASTEXITCODE" }

$Out = Join-Path $RepoRoot "dist\PresentePedro"
$Exe = Join-Path $Out "PresentePedro.exe"
if (-not (Test-Path $Exe)) { throw "PresentePedro.exe missing at $Exe" }

$OutFfmpeg = Join-Path $Out "ffmpeg"
if (-not (Test-Path (Join-Path $OutFfmpeg "bin\ffmpeg.exe"))) {
    Copy-Item -Recurse -Force $FfmpegRoot $OutFfmpeg
}

Copy-Item (Join-Path $RepoRoot "GUIA-PARA-O-PEDRO.md") (Join-Path $Out "GUIA-PARA-O-PEDRO.md") -Force
Set-Content -Path (Join-Path $Out "LEIA-ME.txt") -Encoding UTF8 -Value @(
    "Presente do Victor Prudencio para O Pedro",
    "1) Extraia este zip",
    "2) Abra PresentePedro.exe",
    "3) Leia GUIA-PARA-O-PEDRO.md",
    "Tudo roda LOCAL no PC (modelo no dispositivo)."
)

$Artifact = Join-Path $RepoRoot "PresentePedro-windows.zip"
if (Test-Path $Artifact) { Remove-Item $Artifact -Force }
Write-Host "==> Zip -> $Artifact"
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Artifact -Force

$item = Get-Item $Artifact
Write-Host ("OK artifact: {0} ({1:N1} MB)" -f $item.FullName, ($item.Length / 1MB))
