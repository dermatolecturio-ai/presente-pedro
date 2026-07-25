"""API local: URL (YouTube/web) ou arquivo → pipeline multiagente Nemotron 3.5 ASR."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.agents.base import AgentEvent
from app.agents.orchestrator import PipelineOrchestrator
from app.agents.segmenter import DEFAULT_MAX_ENCODER_FRAMES, SegmenterAgent
from app.asr import LANGUAGES, engine
from app.media import (
    ALLOWED_UPLOAD_SUFFIXES,
    MAX_UPLOAD_BYTES,
    is_http_url,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Em PyInstaller / launcher Windows, PRESENT_PEDRO_ROOT aponta para a pasta do .exe
_ENV_ROOT = os.environ.get("PRESENT_PEDRO_ROOT")
ROOT = Path(_ENV_ROOT).resolve() if _ENV_ROOT else Path(__file__).resolve().parent.parent
# Código/static vêm do pacote; dados graváveis ficam em ROOT/data
STATIC = Path(__file__).resolve().parent / "static"
DATA = ROOT / "data"
TMP = DATA / "tmp"

MAX_DURATION_S = 45 * 60  # 45 minutos — segurança com memória limitada


def _json_safe(value: Any) -> Any:
    """Garante que o payload SSE seja serializável."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@asynccontextmanager
async def lifespan(_app: FastAPI):
    TMP.mkdir(parents=True, exist_ok=True)
    asyncio.create_task(asyncio.to_thread(engine.ensure_loaded))
    yield


app = FastAPI(
    title="Presente do Victor Prudencio para O Pedro",
    description=(
        "Presente do Victor Prudencio para O Pedro — "
        "YouTube, URL genérica ou arquivo local → texto "
        "com pipeline multiagente (Nemotron 3.5 ASR)"
    ),
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class TranscribeRequest(BaseModel):
    url: str = Field(..., min_length=8)
    language: str = Field(default="pt-BR")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not is_http_url(cleaned):
            raise ValueError("Informe uma URL http(s) válida.")
        return cleaned


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    segmenter = SegmenterAgent()
    max_chunk_s = segmenter.max_duration_s(16000, DEFAULT_MAX_ENCODER_FRAMES)
    return {
        "ok": True,
        "asr": engine.status,
        "languages": [{"code": c, "label": l} for c, l in LANGUAGES],
        "max_duration_s": MAX_DURATION_S,
        "inputs": ["youtube", "web_url", "local_file"],
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "allowed_upload_suffixes": sorted(ALLOWED_UPLOAD_SUFFIXES),
        "deployment": {
            "mode": "local",
            "description": (
                "Inferência 100% no dispositivo do usuário — "
                "sem servidor remoto de IA."
            ),
        },
        "pipeline": [
            "download",
            "prepare",
            "segment",
            "asr",
            "merge",
            "polish",
        ],
        "chunking": {
            "max_encoder_frames": DEFAULT_MAX_ENCODER_FRAMES,
            "hard_limit_frames": 5000,
            "max_chunk_seconds": round(max_chunk_s, 1),
            "strategy": "vad_energy_near_budget",
        },
    }


def _sse_streaming_response(
    *,
    job_id: str,
    job_dir: Path,
    language: str,
    url: str | None = None,
    local_path: Path | None = None,
    original_name: str | None = None,
) -> StreamingResponse:
    """Runner SSE compartilhado para transcribe por URL e por upload."""
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    emitted_error = False

    def emit_agent(event: AgentEvent) -> None:
        nonlocal emitted_error
        if event.stage == "error":
            emitted_error = True

        payload: dict[str, Any] = {
            "stage": event.stage,
            "agent": event.agent,
            "message": event.message,
            "job_id": job_id,
        }
        if event.percent is not None:
            payload["percent"] = event.percent

        data = dict(event.data or {})
        if event.stage == "done":
            payload.update(data)
            payload["chunk_count"] = len(data.get("segments") or [])
        elif event.stage == "partial":
            if "partial_text" in data:
                payload["partial_text"] = data["partial_text"]
            payload["data"] = data
            payload["live"] = bool(data.get("live", True))
        elif data:
            payload["data"] = data

        loop.call_soon_threadsafe(queue.put_nowait, _json_safe(payload))

    def run_job() -> None:
        nonlocal emitted_error
        try:
            emit_agent(
                AgentEvent(
                    agent="orchestrator",
                    stage="started",
                    message="Iniciando pipeline multiagente…",
                    percent=0.0,
                    data={"job_id": job_id},
                )
            )

            orchestrator = PipelineOrchestrator()
            orchestrator.run(
                language,
                job_dir,
                emit=emit_agent,
                url=url,
                local_path=local_path,
                original_name=original_name,
                max_duration_s=MAX_DURATION_S,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            if not emitted_error:
                emit_agent(
                    AgentEvent(
                        agent="orchestrator",
                        stage="error",
                        message=str(exc) or "Falha desconhecida",
                    )
                )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
            loop.call_soon_threadsafe(queue.put_nowait, None)

    async def event_stream():
        task = asyncio.create_task(asyncio.to_thread(run_job))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/transcribe")
async def transcribe(req: TranscribeRequest) -> StreamingResponse:
    job_id = uuid.uuid4().hex[:12]
    job_dir = TMP / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return _sse_streaming_response(
        job_id=job_id,
        job_dir=job_dir,
        language=req.language,
        url=req.url,
    )


@app.post("/api/transcribe/upload")
async def transcribe_upload(
    file: UploadFile = File(...),
    language: str = Form(default="pt-BR"),
) -> StreamingResponse:
    original_name = Path(file.filename or "upload.bin").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extensão não permitida: {suffix or '(sem extensão)'}. "
                f"Permitidas: {', '.join(sorted(ALLOWED_UPLOAD_SUFFIXES))}"
            ),
        )

    job_id = uuid.uuid4().hex[:12]
    job_dir = TMP / job_id
    uploads_dir = job_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / original_name

    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Arquivo excede o limite de "
                            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MiB."
                        ),
                    )
                out.write(chunk)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await file.close()

    if size <= 0:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    return _sse_streaming_response(
        job_id=job_id,
        job_dir=job_dir,
        language=language,
        local_path=dest,
        original_name=original_name,
    )


@app.post("/api/warmup")
async def warmup() -> dict[str, Any]:
    try:
        await asyncio.to_thread(engine.ensure_loaded)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return engine.status
