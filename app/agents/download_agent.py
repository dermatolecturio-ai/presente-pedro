"""Agente de ingestão: URL (YouTube/web) ou arquivo local."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.base import AgentEvent, Emitter


class DownloadAgent:
    """Ingere mídia de URL ou arquivo local e emite progresso via Emitter."""

    name = "download"

    def run(
        self,
        *,
        url: str | None = None,
        local_path: str | Path | None = None,
        original_name: str | None = None,
        output_dir: str | Path,
        emit: Emitter | None = None,
    ) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if local_path is not None:
            return self._run_local(
                local_path=local_path,
                original_name=original_name,
                output_dir=out,
                emit=emit,
            )
        if url:
            return self._run_url(url=url, output_dir=out, emit=emit)
        raise ValueError("Informe url ou local_path.")

    def _run_local(
        self,
        *,
        local_path: str | Path,
        original_name: str | None,
        output_dir: Path,
        emit: Emitter | None,
    ) -> dict[str, Any]:
        from app.media import prepare_local_media

        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="ingest",
                    message="Preparando arquivo local…",
                    percent=0.0,
                )
            )

        def on_progress(stage: str, data: dict[str, Any]) -> None:
            if not emit:
                return
            emit(
                AgentEvent(
                    agent=self.name,
                    stage=stage,
                    message=str(data.get("message") or "Preparando…"),
                    percent=float(data["percent"]) if "percent" in data else None,
                    data={k: v for k, v in data.items() if k not in {"message", "percent"}},
                )
            )

        meta = prepare_local_media(
            local_path,
            output_dir,
            original_name=original_name,
            on_progress=on_progress,
        )

        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="ingest",
                    message="Arquivo local pronto",
                    percent=100.0,
                    data={
                        "title": meta.get("title"),
                        "duration": meta.get("duration"),
                        "audio_path": meta.get("audio_path"),
                        "source": meta.get("source", "local"),
                        "original_name": meta.get("original_name"),
                    },
                )
            )
        return meta

    def _run_url(
        self,
        *,
        url: str,
        output_dir: Path,
        emit: Emitter | None,
    ) -> dict[str, Any]:
        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="download",
                    message="Baixando mídia…",
                    percent=0.0,
                )
            )

        def on_progress(stage: str, data: dict[str, Any]) -> None:
            if not emit:
                return
            emit(
                AgentEvent(
                    agent=self.name,
                    stage=stage,
                    message=str(data.get("message") or "Baixando…"),
                    percent=float(data["percent"]) if "percent" in data else None,
                    data={k: v for k, v in data.items() if k not in {"message", "percent"}},
                )
            )

        try:
            from app.media import fetch_audio_from_url as _fetch
        except ImportError:
            from app.youtube import fetch_audio as _fetch  # type: ignore[no-redef]

        meta = _fetch(url, output_dir, on_progress=on_progress)
        meta.setdefault("source", "url")

        if emit:
            emit(
                AgentEvent(
                    agent=self.name,
                    stage="download",
                    message="Download concluído",
                    percent=100.0,
                    data={
                        "title": meta.get("title"),
                        "duration": meta.get("duration"),
                        "audio_path": meta.get("audio_path"),
                        "source": meta.get("source", "url"),
                        "extractor": meta.get("extractor"),
                    },
                )
            )
        return meta


# Alias conceitual: ingestão multi-fonte.
IngestAgent = DownloadAgent
