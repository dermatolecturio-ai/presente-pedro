"""Compatibilidade: reexporta helpers de mídia (antigo módulo YouTube-only)."""

from __future__ import annotations

from app.media import fetch_audio_from_url as fetch_audio
from app.media import is_http_url, is_youtube_url

__all__ = ["fetch_audio", "is_http_url", "is_youtube_url"]
