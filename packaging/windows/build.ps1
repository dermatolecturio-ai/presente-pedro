# Build Windows — Presente do Victor Prudencio para O Pedro
# Execute no PowerShell (Windows 10/11 x64) a partir da raiz do repo OU desta pasta.
#
# O .exe resultante roda o modelo LOCALMENTE no PC do usuário (CUDA ou CPU).
# Não há servidor remoto de IA.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $RepoRoot

Write-Host "==> Repo: $RepoRoot"
Write-Host "==> Presente do Victor Prudencio para O Pedro (build Windows local)"

# --- Python ---
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python nao encontrado no PATH. Instale Python 3.12+ (64-bit) e marque 'Add to PATH'."
}

$ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "==> Python $ver"

# --- venv de build ---
$Venv = Join-Path $RepoRoot ".venv-win-build"
if (-not (Test-Path $Venv)) {
    Write-Host "==> Criando venv $Venv"
    python -m venv $Venv
}

$Pip = Join-Path $Venv "Scripts\pip.exe"
$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

Write-Host "==> Instalando dependencias (torch CUDA se disponivel)"
& $Pip install --upgrade pip wheel setuptools

# Torch: tenta index CUDA 12.x; se falhar, CPU
try {
    & $Pip install torch --index-url https://download.pytorch.org/whl/cu124
} catch {
    Write-Host "Aviso: falha no torch CUDA; instalando torch padrao (CPU)"
    & $Pip install torch
}

& $Pip install -r (Join-Path $RepoRoot "requirements.txt")
& $Pip install "pyinstaller>=6.0"

# --- ffmpeg essentials Windows ---
$FfmpegRoot = Join-Path $ScriptDir "ffmpeg"
$FfmpegBin = Join-Path $FfmpegRoot "bin"
$FfmpegExe = Join-Path $FfmpegBin "ffmpeg.exe"

if (-not (Test-Path $FfmpegExe)) {
    Write-Host "==> Baixando ffmpeg essentials (gyan.dev)"
    $Zip = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
    $Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    Invoke-WebRequest -Uri $Url -OutFile $Zip
    $Extract = Join-Path $env:TEMP "ffmpeg-extract"
    if (Test-Path $Extract) { Remove-Item -Recurse -Force $Extract }
    Expand-Archive -Path $Zip -DestinationPath $Extract -Force
    $Inner = Get-ChildItem $Extract -Directory | Select-Object -First 1
    if (-not $Inner) { Write-Error "Nao foi possivel extrair ffmpeg" }
    New-Item -ItemType Directory -Force -Path $FfmpegRoot | Out-Null
    if (Test-Path $FfmpegBin) { Remove-Item -Recurse -Force $FfmpegBin }
    Copy-Item -Recurse (Join-Path $Inner.FullName "bin") $FfmpegBin
    Write-Host "==> ffmpeg em $FfmpegBin"
} else {
    Write-Host "==> ffmpeg ja presente: $FfmpegExe"
}

# --- PyInstaller ---
Write-Host "==> PyInstaller (pode demorar e gerar pasta grande por causa do torch)"
$Spec = Join-Path $ScriptDir "PresentePedro.spec"
& $Python -m PyInstaller --noconfirm --clean $Spec

$Out = Join-Path $RepoRoot "dist\PresentePedro"
if (-not (Test-Path (Join-Path $Out "PresentePedro.exe"))) {
    Write-Error "Build falhou: PresentePedro.exe nao encontrado em $Out"
}

# Garante ffmpeg ao lado do exe (alem do bundle interno)
$OutFfmpeg = Join-Path $Out "ffmpeg"
if (-not (Test-Path (Join-Path $OutFfmpeg "bin\ffmpeg.exe"))) {
    Write-Host "==> Copiando ffmpeg para a pasta do exe"
    Copy-Item -Recurse -Force $FfmpegRoot $OutFfmpeg
}

# Atalho de texto
$ReadmeOut = Join-Path $Out "LEIA-ME.txt"
@"
Presente do Victor Prudencio para O Pedro
=========================================

TUDO RODA NO SEU PC (modelo local). Nao ha servidor remoto de IA.

1. Dê duplo clique em PresentePedro.exe
2. O navegador abre em http://127.0.0.1:8787
3. Use Link (YouTube/outros) ou Arquivo (video/audio local)
4. Feche a janela do programa para encerrar

Requisitos:
- Windows 10/11 64-bit
- GPU NVIDIA + drivers (recomendado). Sem GPU = CPU (lento)
- Internet na 1a vez (download do modelo Hugging Face ~1-2 GB)
- Pasta 'data' sera criada ao lado do .exe (cache/temp)

SmartScreen pode avisar (app nao assinado). Use 'Mais info' > Executar assim mesmo.
"@ | Set-Content -Path $ReadmeOut -Encoding UTF8

Write-Host ""
Write-Host "OK — pasta portatil:"
Write-Host "  $Out"
Write-Host "Copie a pasta PresentePedro inteira para o PC do usuario e rode PresentePedro.exe"
