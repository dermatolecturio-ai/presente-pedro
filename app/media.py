"""Download e preparação de mídia (URL via yt-dlp ou arquivo local via ffmpeg)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, UnsupportedError

ProgressCallback = Callable[[str, dict[str, Any]], None]

ALLOWED_UPLOAD_SUFFIXES = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".mpeg",
    ".mpg",
}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500MB

YOUTUBE_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+",
    re.IGNORECASE,
)


def is_http_url(url: str) -> bool:
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_RE.match((url or "").strip()))


def _emit(
    on_progress: ProgressCallback | None,
    stage: str,
    data: dict[str, Any],
) -> None:
    if on_progress:
        on_progress(stage, data)


def _ffmpeg_bin() -> str:
    """Resolve ffmpeg: FFMPEG_BINARY, PATH, ou bundling Windows."""
    env = os.environ.get("FFMPEG_BINARY")
    if env and Path(env).is_file():
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    # Fallbacks relativos ao launcher
    root = Path(os.environ.get("PRESENT_PEDRO_ROOT") or Path.cwd())
    for candidate in (
        root / "ffmpeg" / "bin" / "ffmpeg.exe",
        root / "ffmpeg" / "ffmpeg.exe",
        root / "ffmpeg" / "bin" / "ffmpeg",
    ):
        if candidate.is_file():
            return str(candidate)
    return "ffmpeg"


def _ffprobe_bin() -> str:
    env = os.environ.get("FFPROBE_BINARY")
    if env and Path(env).is_file():
        return env
    which = shutil.which("ffprobe")
    if which:
        return which
    ffmpeg = Path(_ffmpeg_bin())
    sibling = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")
    if sibling.is_file():
        return str(sibling)
    return "ffprobe"


def _probe_duration_seconds(path: Path) -> float | None:
    """Retorna duração em segundos via ffprobe, ou None se indisponível."""
    try:
        result = subprocess.run(
            [
                _ffprobe_bin(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        raw = (result.stdout or "").strip()
        if not raw:
            return None
        return float(raw)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return None


def _ffmpeg_to_wav(input_path: Path, output_path: Path) -> None:
    try:
        result = subprocess.run(
            [
                _ffmpeg_bin(),
                "-y",
                "-i",
                str(input_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg não encontrado. No Windows, use o pacote PresentePedro "
            "(ffmpeg incluso) ou instale o ffmpeg no PATH."
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail.splitlines()[-1] if detail else "erro desconhecido"
        raise RuntimeError(f"Falha ao converter mídia com ffmpeg: {detail}")


def fetch_audio_from_url(
    url: str,
    output_dir: Path | str,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Baixa áudio de qualquer URL http(s) suportada pelo yt-dlp (WAV mono 16 kHz)."""
    cleaned = (url or "").strip()
    if not is_http_url(cleaned):
        raise RuntimeError("URL inválida. Informe um endereço http:// ou https://.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s.%(ext)s")

    def _hook(d: dict[str, Any]) -> None:
        if not on_progress:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = round(downloaded / total * 100, 1) if total else 0
            on_progress(
                "download",
                {
                    "percent": pct,
                    "speed": d.get("_speed_str"),
                    "eta": d.get("_eta_str"),
                },
            )
        elif status == "finished":
            on_progress("download", {"percent": 100, "message": "Download concluído"})

    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "postprocessor_args": {
            "ffmpeg": ["-ac", "1", "-ar", "16000"],
        },
    }

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(cleaned, download=True)
    except UnsupportedError as exc:
        raise RuntimeError(
            "URL não suportada. Use um link de vídeo/áudio de site reconhecido "
            "(YouTube, Vimeo, X/Twitter, Instagram, Twitch, Facebook, etc.) "
            "ou um arquivo de mídia direto."
        ) from exc
    except DownloadError as exc:
        msg = str(exc).strip() or "falha no download"
        lower = msg.lower()
        if "unsupported url" in lower or "no suitable" in lower:
            raise RuntimeError(
                "URL não suportada ou sem áudio disponível para download."
            ) from exc
        raise RuntimeError(f"Falha ao baixar mídia: {msg}") from exc
    except Exception as exc:  # noqa: BLE001 — surfacing yt-dlp failures in PT
        raise RuntimeError(f"Falha ao baixar mídia: {exc}") from exc

    if info is None:
        raise RuntimeError("Não foi possível obter informações do vídeo.")

    video_id = info.get("id") or hashlib.sha1(cleaned.encode()).hexdigest()[:12]
    title = info.get("title") or "Sem título"
    duration = info.get("duration") or 0
    uploader = info.get("uploader") or info.get("channel") or ""
    webpage_url = info.get("webpage_url") or cleaned
    extractor = info.get("extractor")

    audio_path = output_dir / f"{video_id}.wav"
    if not audio_path.exists():
        # yt-dlp às vezes deixa a extensão original antes do pós-processamento
        candidates = list(output_dir.glob(f"{video_id}.*"))
        wavs = [p for p in candidates if p.suffix.lower() == ".wav"]
        if wavs:
            audio_path = wavs[0]
        elif candidates:
            raise RuntimeError(
                f"Áudio baixado, mas conversão para WAV falhou: {candidates[0].name}"
            )
        else:
            raise RuntimeError("Arquivo de áudio não encontrado após o download.")

    return {
        "id": video_id,
        "title": title,
        "duration": duration,
        "uploader": uploader,
        "url": webpage_url,
        "audio_path": str(audio_path),
        "source": "url",
        "extractor": extractor,
    }


def prepare_local_media(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    original_name: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Copia mídia local e converte para WAV mono 16 kHz via ffmpeg."""
    source = Path(source_path)
    if not source.is_file():
        raise RuntimeError(f"Arquivo local não encontrado: {source}")

    display_name = original_name or source.name
    suffix = Path(display_name).suffix.lower() or source.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise RuntimeError(
            f"Formato não suportado ({suffix or 'sem extensão'}). "
            f"Formatos aceitos: {allowed}."
        )

    try:
        size = source.stat().st_size
    except OSError as exc:
        raise RuntimeError(f"Não foi possível ler o arquivo: {exc}") from exc
    if size > MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"Arquivo muito grande ({size} bytes). Limite: {MAX_UPLOAD_BYTES} bytes."
        )
    if size <= 0:
        raise RuntimeError("Arquivo vazio.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    media_id = hashlib.sha1(f"{display_name}:{size}".encode()).hexdigest()[:12]
    stem = Path(display_name).stem or "audio"
    staged = out_dir / f"{media_id}_src{suffix}"
    audio_path = out_dir / f"{media_id}.wav"

    _emit(
        on_progress,
        "local",
        {"percent": 5, "message": "Copiando arquivo local…"},
    )

    try:
        shutil.copy2(source, staged)
    except OSError as exc:
        raise RuntimeError(f"Falha ao copiar arquivo local: {exc}") from exc

    _emit(
        on_progress,
        "local",
        {"percent": 40, "message": "Convertendo para WAV mono 16 kHz…"},
    )

    try:
        _ffmpeg_to_wav(staged, audio_path)
    finally:
        if staged.exists() and staged.resolve() != audio_path.resolve():
            staged.unlink(missing_ok=True)

    if not audio_path.is_file():
        raise RuntimeError("Conversão concluída, mas o WAV não foi gerado.")

    _emit(
        on_progress,
        "local",
        {"percent": 85, "message": "Lendo duração…"},
    )

    duration = _probe_duration_seconds(audio_path) or 0

    _emit(
        on_progress,
        "local",
        {"percent": 100, "message": "Arquivo local pronto"},
    )

    return {
        "id": media_id,
        "title": stem,
        "duration": duration,
        "uploader": "arquivo local",
        "url": audio_path.resolve().as_uri(),
        "audio_path": str(audio_path),
        "source": "local",
        "original_name": display_name,
    }


# Alias histórico para youtube.py / download_agent
fetch_audio = fetch_audio_from_url
