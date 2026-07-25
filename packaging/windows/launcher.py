"""
Launcher Windows — Presente do Victor Prudencio para O Pedro

Sobe o app FastAPI em 127.0.0.1 (tudo local: modelo + inferência no PC do usuário),
abre o navegador e mantém uma janela simples até o usuário fechar.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


APP_TITLE = "Presente do Victor Prudencio para O Pedro"
HOST = "127.0.0.1"
PORT = 8787
URL = f"http://{HOST}:{PORT}"


def _app_root() -> Path:
    """Diretório raiz do app (dev) ou pasta do executável (PyInstaller)."""
    if getattr(sys, "frozen", False):
        # one-folder: exe ao lado de _internal/; recursos em sys._MEIPASS
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # noqa: SLF001
    return _app_root()


def _prepare_environment() -> None:
    root = _app_root()
    res = _resource_root()

    # Garante imports `app.*` e data dir gravável ao lado do .exe
    if str(res) not in sys.path:
        sys.path.insert(0, str(res))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("PRESENT_PEDRO_ROOT", str(root))

    # ffmpeg / ffprobe empacotados (pasta ffmpeg/bin ao lado do exe ou em _MEIPASS)
    for candidate in (
        root / "ffmpeg" / "bin",
        res / "ffmpeg" / "bin",
        root / "ffmpeg",
        res / "ffmpeg",
    ):
        if candidate.is_dir():
            path = str(candidate)
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            os.environ["FFMPEG_BINARY"] = str(candidate / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
            break

    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "tmp").mkdir(parents=True, exist_ok=True)


def _wait_until_ready(timeout_s: float = 90.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.35)
    return False


def _run_server() -> None:
    import uvicorn

    # Importa depois de preparar path/env
    from app.main import app  # noqa: WPS433

    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False,
        workers=1,
    )
    server = uvicorn.Server(config)
    # Exposto para shutdown limpo
    global _UVICORN_SERVER  # noqa: PLW0603
    _UVICORN_SERVER = server
    server.run()


_UVICORN_SERVER = None


def _device_banner() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return f"GPU NVIDIA detectada: {name}\nO modelo roda 100% no seu PC (CUDA)."
        return (
            "Nenhuma GPU NVIDIA detectada.\n"
            "O modelo vai rodar na CPU (mais lento, mas local — sem nuvem)."
        )
    except Exception:  # noqa: BLE001
        return "PyTorch ainda não carregado. O modelo rodará localmente no seu PC."


def _gui_loop() -> None:
    """Janela Tkinter mínima (stdlib) — fechar encerra o servidor local."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("520x280")
    root.resizable(False, False)

    banner = _device_banner()
    text = (
        f"{APP_TITLE}\n\n"
        "Tudo roda no seu computador:\n"
        "• modelo de transcrição local\n"
        "• sem enviar áudio para a nuvem\n\n"
        f"Interface: {URL}\n\n"
        f"{banner}\n\n"
        "Feche esta janela para encerrar o programa."
    )

    label = tk.Label(root, text=text, justify="left", padx=18, pady=16, anchor="nw")
    label.pack(fill="both", expand=True)

    def open_ui() -> None:
        webbrowser.open(URL)

    btn = tk.Button(root, text="Abrir no navegador", command=open_ui)
    btn.pack(pady=(0, 14))

    def on_close() -> None:
        if messagebox.askokcancel("Sair", "Encerrar o programa local?"):
            try:
                if _UVICORN_SERVER is not None:
                    _UVICORN_SERVER.should_exit = True
            except Exception:  # noqa: BLE001
                pass
            root.destroy()
            # Força saída do processo (encerra thread do uvicorn)
            os._exit(0)  # noqa: SLF001

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


def main() -> int:
    try:
        _prepare_environment()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1

    server_thread = threading.Thread(target=_run_server, name="uvicorn", daemon=True)
    server_thread.start()

    if _wait_until_ready():
        webbrowser.open(URL)
    else:
        print(f"Aviso: servidor não respondeu a tempo em {URL}", flush=True)

    try:
        _gui_loop()
    except Exception:  # noqa: BLE001
        # Ambiente sem display: mantém processo vivo no console
        traceback.print_exc()
        print(f"Servidor local em {URL} — Ctrl+C para sair.", flush=True)
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
