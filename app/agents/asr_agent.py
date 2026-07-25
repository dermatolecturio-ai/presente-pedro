"""Agente ASR por chunk — streaming de texto parcial via `app.asr.engine`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.agents.base import AgentEvent, Emitter
from app.asr import engine

PartialCallback = Callable[[str], None]


class AsrChunkAgent:
    """Transcreve um chunk de áudio com emissão de texto em tempo real."""

    name = "asr"

    def __init__(self, *, chunks_dir: str | Path | None = None) -> None:
        self.chunks_dir = Path(chunks_dir) if chunks_dir else None

    def transcribe_chunk(
        self,
        audio: np.ndarray,
        sampling_rate: int,
        language: str,
        emit: Emitter | None,
        chunk_index: int,
        total_chunks: int,
        *,
        tmp_dir: str | Path | None = None,
        on_partial: PartialCallback | None = None,
    ) -> str:
        """Transcreve um chunk; `on_partial` recebe o texto crescente do trecho."""
        del tmp_dir

        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="asr",
                    message=f"Transcrevendo chunk {chunk_index + 1}/{total_chunks}…",
                    data={
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                    },
                )
            )

        result: dict[str, Any] = engine.transcribe_waveform(
            audio,
            sampling_rate=sampling_rate,
            language=language,
            on_partial=on_partial,
        )
        text = str(result.get("text") or "").strip()

        if on_partial:
            on_partial(text)

        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="asr",
                    message=f"Chunk {chunk_index + 1}/{total_chunks} pronto",
                    data={
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                        "chars": len(text),
                    },
                )
            )
        return text
