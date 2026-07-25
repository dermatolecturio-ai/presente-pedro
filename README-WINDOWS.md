# Windows — Presente do Victor Prudencio para O Pedro

Programa **100% local** no PC Windows: o modelo Nemotron 3.5 ASR roda **no dispositivo do usuário** (GPU NVIDIA ou CPU). Não há servidor remoto de IA; a interface abre em `http://127.0.0.1:8787` só na máquina dele.

```text
PresentePedro.exe
    → sobe app local (uvicorn em 127.0.0.1)
    → carrega o modelo no PC (CUDA/CPU)
    → abre o navegador
```

## O que o usuário final faz

1. Recebe a pasta `PresentePedro\` (gerada no build)
2. Duplo clique em `PresentePedro.exe`
3. Usa **Link** (YouTube / outros sites) ou **Arquivo** (vídeo/áudio local)
4. Fecha a janela do programa para encerrar

Na **primeira execução** o Windows baixa o modelo do Hugging Face (~1–2 GB) para o cache local. Depois funciona offline (exceto download de URLs).

## Requisitos do PC

| Item | Detalhe |
|------|---------|
| SO | Windows 10/11 **64-bit** |
| GPU | **NVIDIA + drivers** fortemente recomendados |
| Sem GPU | Funciona em **CPU** (bem mais lento) |
| Disco | ~4–8 GB livres (modelo + deps) |
| Rede | Só na 1ª vez (modelo) e para baixar vídeos por link |

## Como gerar o `.exe` pelo Mac (AppVeyor — grátis)

O GitHub Actions desta conta pode estar bloqueado por billing. Alternativa gratuita com VM Windows:

1. Suba o repo (público) no GitHub com o arquivo [`appveyor.yml`](appveyor.yml)
2. Crie conta em [ci.appveyor.com](https://ci.appveyor.com) → **Login with GitHub**
3. **New Project** → autorize → escolha `presente-pedro`
4. Espere o build (PyTorch + PyInstaller: 30–90+ min)
5. Em **Artifacts**, baixe `PresentePedro-windows.zip`

No Mac, depois do build verde:

```bash
export APPVEYOR_TOKEN=seu_token   # https://ci.appveyor.com/api-token
./scripts/download-appveyor-artifact.sh
```

## Como gerar o `.exe` (máquina Windows de build)

1. Instale [Python 3.12+](https://www.python.org/downloads/) (marque **Add python.exe to PATH**)
2. Clone/copie este repositório
3. Abra **PowerShell** na pasta do projeto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\packaging\windows\build.ps1
```

4. Saída portátil:

```text
dist\PresentePedro\
  PresentePedro.exe
  ffmpeg\
  LEIA-ME.txt
  _internal\          (libs PyInstaller)
```

5. Copie a pasta **inteira** `PresentePedro` para o PC do Pedro (pendrive/zip).

### Gerar o `.exe` a partir do Mac (recomendado)

No Mac **não** dá para criar um `.exe` Windows nativo com PyInstaller de forma confiável.  
O caminho certo é o **GitHub Actions** (já configurado neste repo):

1. Suba o código para o GitHub (`git push`)
2. No repositório: **Actions → Build Windows exe → Run workflow**
3. Espere o job no runner `windows-latest`
4. Baixe o artifact **`PresentePedro-windows`** (zip)
5. Mande o zip para o Pedro + o arquivo [`GUIA-PARA-O-PEDRO.md`](GUIA-PARA-O-PEDRO.md)

### Observações de build

- O script tenta instalar **PyTorch com CUDA 12.4**; se falhar, usa torch CPU
- Baixa **ffmpeg essentials** automaticamente para `packaging\windows\ffmpeg\`
- O pacote fica **grande** (torch + transformers) — esperado
- O Windows SmartScreen pode avisar (app não assinado): *Mais informações → Executar assim mesmo*

## Rodar sem gerar `.exe` (dev no Windows)

```powershell
cd caminho\do\repo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Preferível com CUDA:
# pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
$env:PRESENT_PEDRO_ROOT = (Get-Location).Path
python packaging\windows\launcher.py
```

Ou o servidor clássico:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

## Privacidade

- Áudio e texto ficam no PC
- O “servidor” é só `127.0.0.1` local
- Links de vídeo usam `yt-dlp` na própria máquina
- Arquivos locais são convertidos com o `ffmpeg` empacotado

## Solução de problemas

| Sintoma | O que fazer |
|---------|-------------|
| Muito lento | Instalar driver NVIDIA recente; confirmar GPU em *Gerenciador de dispositivos* |
| “ffmpeg não encontrado” | Manter pasta `ffmpeg\bin` ao lado do `.exe` |
| SmartScreen bloqueia | *Mais info → Executar assim mesmo* |
| Porta 8787 ocupada | Fechar outra instância do app |
| Modelo não baixa | Liberar firewall/rede na 1ª execução |

## Nome do produto

**Presente do Victor Prudencio para O Pedro** — homenagem com a foto do Pedro na interface.
