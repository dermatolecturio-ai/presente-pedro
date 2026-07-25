# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — rode no Windows via packaging/windows/build.ps1
# Gera pasta portátil dist/PresentePedro/ com PresentePedro.exe
# Inferência 100% local no PC do usuário (CUDA ou CPU).

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

SPECDIR = Path(SPEC).resolve().parent  # type: ignore[name-defined]
ROOT = SPECDIR.parents[1]

datas = []
binaries = []
hiddenimports = []

# Código e UI
datas += [
    (str(ROOT / "app"), "app"),
    (str(ROOT / "requirements.txt"), "."),
]

# ffmpeg Windows (baixado pelo build.ps1 para packaging/windows/ffmpeg)
ffmpeg_dir = SPECDIR / "ffmpeg"
if ffmpeg_dir.is_dir():
    datas += [(str(ffmpeg_dir), "ffmpeg")]

# Pacotes pesados / dados
for pkg in ("transformers", "torch", "librosa", "sklearn", "certifi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

try:
    datas += collect_data_files("yt_dlp")
except Exception:
    pass

hiddenimports += collect_submodules("app")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "sklearn.utils._cython_blas",
]

a = Analysis(
    [str(SPECDIR / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PresentePedro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # janela Tk; use True para debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPECDIR / "icon.ico") if (SPECDIR / "icon.ico").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PresentePedro",
)
