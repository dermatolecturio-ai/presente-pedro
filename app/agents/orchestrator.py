"""Orquestrador multi-agente: ingest → segment → ASR → merge → polish."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import time

import numpy as np

from app.agents.asr_agent import AsrChunkAgent
from app.agents.base import AgentEvent, Emitter
from app.agents.download_agent import DownloadAgent
from app.agents.merger_agent import MergerAgent
from app.agents.polish_agent import PolishAgent
from app.asr import MODEL_ID, engine


def _noop_emit(_event: AgentEvent) -> None:
    return None


class PipelineOrchestrator:
    """Pipeline multi-fonte (URL / arquivo local) → texto, com eventos por agente."""

    name = "orchestrator"

    def __init__(self) -> None:
        self.download_agent = DownloadAgent()
        self.asr_agent = AsrChunkAgent()
        self.merger_agent = MergerAgent()
        self.polish_agent = PolishAgent()

    def run(
        self,
        language: str,
        tmp_dir: str | Path,
        emit: Emitter | None = None,
        *,
        url: str | None = None,
        local_path: str | Path | None = None,
        original_name: str | None = None,
        max_duration_s: float = 45 * 60,
    ) -> dict[str, Any]:
        """Executa o pipeline e retorna o payload final."""
        emit_fn: Emitter = emit or _noop_emit
        work = Path(tmp_dir)
        work.mkdir(parents=True, exist_ok=True)
        agent_trace: list[dict[str, Any]] = []

        def trace(stage: str, message: str, **extra: Any) -> None:
            agent_trace.append({"stage": stage, "message": message, **extra})

        try:
            # 1. ingest (URL ou arquivo local)
            starting_msg = (
                "Preparando arquivo local…"
                if local_path is not None
                else "Iniciando download…"
            )
            emit_fn(
                AgentEvent(
                    agent=self.download_agent.name,
                    stage="download",
                    message=starting_msg,
                    percent=0.0,
                )
            )
            meta = self.download_agent.run(
                url=url,
                local_path=local_path,
                original_name=original_name,
                output_dir=work,
                emit=emit_fn,
            )
            title = str(meta.get("title") or "")
            audio_path = Path(meta["audio_path"])
            source = str(meta.get("source") or ("local" if local_path else "url"))
            extractor = meta.get("extractor")
            meta_duration = float(meta.get("duration") or 0)
            if meta_duration and meta_duration > max_duration_s:
                raise RuntimeError(
                    f"Mídia muito longa ({int(meta_duration) // 60} min). "
                    f"Limite local: {int(max_duration_s) // 60} min."
                )
            trace(
                "download",
                "ok",
                title=title,
                duration=meta.get("duration"),
                source=source,
                extractor=extractor,
            )

            # 2. prepare — carrega áudio mono float32
            emit_fn(
                AgentEvent(
                    agent=self.name,
                    stage="prepare",
                    message="Carregando áudio…",
                    percent=10.0,
                )
            )
            audio, sampling_rate = self._load_audio(audio_path)
            duration_s = float(len(audio) / sampling_rate) if sampling_rate else 0.0
            if duration_s > max_duration_s:
                raise RuntimeError(
                    f"Mídia muito longa ({int(duration_s) // 60} min). "
                    f"Limite local: {int(max_duration_s) // 60} min."
                )
            trace("prepare", "ok", samples=len(audio), sampling_rate=sampling_rate)

            # 3. segment
            emit_fn(
                AgentEvent(
                    agent="segmenter",
                    stage="segment",
                    message="Segmentando áudio…",
                    percent=15.0,
                )
            )
            segments = self._segment(audio, sampling_rate, emit_fn)
            trace("segment", "ok", segments=len(segments))

            # 4. asr — sequencial (evita OOM MPS) + texto parcial ao vivo
            total = len(segments)
            asr_segments: list[dict[str, Any]] = []
            self.asr_agent.chunks_dir = work
            device = None
            model_id = MODEL_ID
            live_parts: list[str] = [""] * total

            def emit_live_transcript(active_index: int) -> None:
                # Junta partes já fechadas + trecho atual em streaming.
                pieces = [p for p in live_parts if p]
                merged_live = self.merger_agent.merge(
                    [
                        {
                            "index": j,
                            "start_s": segments[j]["start_s"],
                            "end_s": segments[j]["end_s"],
                            "text": live_parts[j],
                            "reason": segments[j].get("reason", ""),
                        }
                        for j in range(total)
                        if live_parts[j]
                    ]
                )["text"]
                emit_fn(
                    AgentEvent(
                        agent=self.asr_agent.name,
                        stage="partial",
                        message=f"Transcrição ao vivo · trecho {active_index + 1}/{total}",
                        percent=20.0 + (70.0 * (active_index + 0.35) / max(total, 1)),
                        data={
                            "partial_text": merged_live,
                            "chunk_index": active_index,
                            "total_chunks": total,
                            "live": True,
                        },
                    )
                )

            for i, seg in enumerate(segments):
                pct = 20.0 + (70.0 * i / max(total, 1))
                emit_fn(
                    AgentEvent(
                        agent=self.asr_agent.name,
                        stage="asr",
                        message=f"ASR chunk {i + 1}/{total}",
                        percent=pct,
                        data={"chunk_index": i, "total_chunks": total},
                    )
                )

                last_flush = 0.0

                def on_chunk_partial(chunk_text: str, idx: int = i) -> None:
                    nonlocal last_flush
                    live_parts[idx] = chunk_text
                    now = time.monotonic()
                    if now - last_flush >= 0.15:
                        last_flush = now
                        emit_live_transcript(idx)

                text = self.asr_agent.transcribe_chunk(
                    seg["audio"],
                    sampling_rate,
                    language,
                    emit_fn,
                    chunk_index=i,
                    total_chunks=total,
                    tmp_dir=work,
                    on_partial=on_chunk_partial,
                )
                live_parts[i] = text
                emit_live_transcript(i)

                asr_segments.append(
                    {
                        "index": seg["index"],
                        "start_s": seg["start_s"],
                        "end_s": seg["end_s"],
                        "text": text,
                        "reason": seg.get("reason", ""),
                    }
                )
                if engine.status.get("device"):
                    device = engine.status["device"]

            emit_fn(
                AgentEvent(
                    agent=self.asr_agent.name,
                    stage="asr",
                    message="ASR concluído",
                    percent=90.0,
                    data={"chunks": total},
                )
            )
            trace("asr", "ok", chunks=total)

            # 5. merge
            emit_fn(
                AgentEvent(
                    agent=self.merger_agent.name,
                    stage="merge",
                    message="Unindo segmentos…",
                    percent=93.0,
                )
            )
            merged = self.merger_agent.merge(asr_segments)
            trace("merge", "ok")

            # 6. polish
            emit_fn(
                AgentEvent(
                    agent=self.polish_agent.name,
                    stage="polish",
                    message="Polindo texto…",
                    percent=96.0,
                )
            )
            final_text = self.polish_agent.polish(merged["text"], language)
            # Segmentos: só normaliza espaçamento (sem forçar ponto final em meio de frase).
            polished_segments = [
                {
                    **s,
                    "text": MergerAgent._normalize_spacing(str(s.get("text") or "")),
                }
                for s in merged["segments"]
            ]
            trace("polish", "ok")

            if device is None:
                device = engine.status.get("device")

            result: dict[str, Any] = {
                "text": final_text,
                "title": title,
                "segments": polished_segments,
                "language": language,
                "device": device,
                "model_id": model_id,
                "duration_s": duration_s,
                "uploader": meta.get("uploader"),
                "url": meta.get("url"),
                "source": source,
                "agent_trace": agent_trace,
            }
            if extractor is not None:
                result["extractor"] = extractor

            # 7. done
            emit_fn(
                AgentEvent(
                    agent=self.name,
                    stage="done",
                    message="Pronto",
                    percent=100.0,
                    data=result,
                )
            )
            return result

        except Exception as exc:  # noqa: BLE001
            emit_fn(
                AgentEvent(
                    agent=self.name,
                    stage="error",
                    message=str(exc),
                    data={"error": str(exc)},
                )
            )
            raise

    def _load_audio(self, path: Path) -> tuple[np.ndarray, int]:
        """Carrega áudio mono float32; prefere transformers.audio_utils."""
        try:
            from transformers.audio_utils import load_audio

            # Sampling rate do modelo (16 kHz típico); se engine ainda não carregou,
            # usa 16000 — o download já força 16 kHz no youtube.py.
            sr = 16000
            if engine.ready and engine._processor is not None:  # noqa: SLF001
                sr = int(engine._processor.feature_extractor.sampling_rate)  # noqa: SLF001

            audio = load_audio(str(path), sampling_rate=sr)
            if isinstance(audio, tuple):
                audio = audio[0]
            wave = np.asarray(audio, dtype=np.float32).reshape(-1)
            return wave, sr
        except Exception:
            import soundfile as sf

            data, file_sr = sf.read(str(path), dtype="float32", always_2d=False)
            wave = np.asarray(data, dtype=np.float32)
            if wave.ndim > 1:
                wave = wave.mean(axis=1).astype(np.float32)
            return wave.reshape(-1), int(file_sr)

    def _segment(
        self,
        audio: np.ndarray,
        sampling_rate: int,
        emit: Emitter,
    ) -> list[dict[str, Any]]:
        """Usa SegmenterAgent se disponível; fallback em chunks iguais pelo budget."""
        try:
            from app.agents.segmenter import SegmenterAgent

            segmenter = SegmenterAgent()

            def on_progress(stage: str, data: dict[str, Any]) -> None:
                emit(
                    AgentEvent(
                        agent="segmenter",
                        stage=stage,
                        message=str(data.get("message") or "Segmentando…"),
                        percent=float(data["percent"]) if "percent" in data else None,
                        data={
                            k: v
                            for k, v in data.items()
                            if k not in {"message", "percent"}
                        },
                    )
                )

            segs = segmenter.segment(
                audio,
                sampling_rate,
                max_encoder_frames=4800,
                on_progress=on_progress,
            )
            return [
                {
                    "index": s.index,
                    "start_s": s.start_s,
                    "end_s": s.end_s,
                    "audio": s.audio,
                    "reason": s.reason,
                }
                for s in segs
            ]
        except ImportError:
            return self._equal_chunk_fallback(audio, sampling_rate)

    @staticmethod
    def _equal_chunk_fallback(
        audio: np.ndarray,
        sampling_rate: int,
        *,
        max_encoder_frames: int = 4800,
        hop: int = 160,
        subsample: int = 8,
    ) -> list[dict[str, Any]]:
        """Fallback: cortes iguais com max_samples = frames * subsample * hop."""
        max_samples = max_encoder_frames * subsample * hop
        wave = np.asarray(audio, dtype=np.float32).reshape(-1)
        n = len(wave)
        if n == 0:
            return []

        segments: list[dict[str, Any]] = []
        start = 0
        idx = 0
        while start < n:
            end = min(n, start + max_samples)
            chunk = np.ascontiguousarray(wave[start:end], dtype=np.float32)
            segments.append(
                {
                    "index": idx,
                    "start_s": start / sampling_rate,
                    "end_s": end / sampling_rate,
                    "audio": chunk,
                    "reason": "equal_chunk_fallback",
                }
            )
            start = end
            idx += 1
        return segments
