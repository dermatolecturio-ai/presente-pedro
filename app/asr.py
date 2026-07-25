"""Transcrição com nvidia/nemotron-3.5-asr-streaming-0.6b."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch

logger = logging.getLogger(__name__)

MODEL_ID = "nvidia/nemotron-3.5-asr-streaming-0.6b"
ProgressCallback = Callable[[str, dict[str, Any]], None]

LANGUAGES = [
    ("auto", "Detectar automaticamente"),
    ("pt-BR", "Português (Brasil)"),
    ("pt-PT", "Português (Portugal)"),
    ("en-US", "English (US)"),
    ("en-GB", "English (UK)"),
    ("es-ES", "Español (España)"),
    ("es-US", "Español (LatAm)"),
    ("fr-FR", "Français"),
    ("de-DE", "Deutsch"),
    ("it-IT", "Italiano"),
    ("ja-JP", "日本語"),
    ("ko-KR", "한국어"),
    ("zh-CN", "中文"),
    ("ru-RU", "Русский"),
    ("ar-AR", "العربية"),
    ("hi-IN", "हिन्दी"),
]


class AsrEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._processor = None
        self._device: torch.device | None = None
        self._load_error: str | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None and self._processor is not None

    @property
    def status(self) -> dict[str, Any]:
        device = str(self._device) if self._device else None
        warning = None
        if self._device is not None and self._device.type == "cpu":
            warning = (
                "Modo CPU — o modelo roda localmente no seu PC, "
                "mas sem GPU NVIDIA pode demorar bastante."
            )
        elif self._device is not None and self._device.type == "cuda":
            try:
                gpu_name = torch.cuda.get_device_name(0)
            except Exception:  # noqa: BLE001
                gpu_name = "CUDA"
            warning = None
            device = f"cuda ({gpu_name})"
        return {
            "ready": self.ready,
            "model_id": MODEL_ID,
            "device": device,
            "local_inference": True,
            "warning": warning,
            "error": self._load_error,
        }

    def ensure_loaded(self, on_progress: ProgressCallback | None = None) -> None:
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            try:
                if on_progress:
                    on_progress("model", {"message": "Carregando modelo Nemotron 3.5 ASR…"})
                self._load()
                if on_progress:
                    on_progress(
                        "model",
                        {
                            "message": f"Modelo pronto em {self._device} (local)",
                            "device": str(self._device),
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                self._load_error = str(exc)
                raise

    def _pick_device(self) -> torch.device:
        # Windows / Linux: CUDA primeiro. macOS: MPS. Sempre local — nunca nuvem.
        if torch.cuda.is_available():
            logger.info("Usando CUDA local: %s", torch.cuda.get_device_name(0))
            return torch.device("cuda")
        if sys.platform == "darwin":
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                logger.info("Usando Apple MPS local")
                return torch.device("mps")
        logger.warning(
            "Nenhuma GPU acelerada disponível — inferência local em CPU (mais lenta)"
        )
        return torch.device("cpu")

    def _load(self) -> None:
        from transformers import AutoModelForRNNT, AutoProcessor

        device = self._pick_device()
        logger.info("Loading %s on %s", MODEL_ID, device)

        processor = AutoProcessor.from_pretrained(MODEL_ID)
        # device_map="auto" is uneven on MPS; load then move.
        dtype = torch.float16 if device.type in {"cuda", "mps"} else torch.float32
        model = AutoModelForRNNT.from_pretrained(MODEL_ID, torch_dtype=dtype)
        model.to(device)
        model.eval()

        self._processor = processor
        self._model = model
        self._device = device
        self._load_error = None
        logger.info("Model loaded on %s", device)

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str = "pt-BR",
        on_progress: ProgressCallback | None = None,
        on_partial: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        self.ensure_loaded(on_progress=on_progress)
        assert self._processor is not None

        from transformers.audio_utils import load_audio

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Áudio não encontrado: {path}")

        if on_progress:
            on_progress("transcribe", {"message": "Lendo áudio…", "percent": 5})

        sampling_rate = self._processor.feature_extractor.sampling_rate
        audio = load_audio(str(path), sampling_rate=sampling_rate)
        if isinstance(audio, tuple):
            audio = audio[0]
        audio = np.asarray(audio, dtype=np.float32)

        return self.transcribe_waveform(
            audio,
            sampling_rate=sampling_rate,
            language=language,
            on_progress=on_progress,
            on_partial=on_partial,
        )

    def transcribe_waveform(
        self,
        audio: np.ndarray,
        *,
        sampling_rate: int,
        language: str = "pt-BR",
        on_progress: ProgressCallback | None = None,
        on_partial: Callable[[str], None] | None = None,
        lookahead_tokens: int = 6,
    ) -> dict[str, Any]:
        """Transcreve waveform com streaming de texto (parcial → final)."""
        self.ensure_loaded(on_progress=on_progress)
        assert self._model is not None and self._processor is not None and self._device is not None

        from transformers import TextIteratorStreamer

        wave = np.asarray(audio, dtype=np.float32).reshape(-1)
        duration_s = float(len(wave) / sampling_rate) if sampling_rate else 0.0
        lang = language or "auto"
        skip_special = lang != "auto"

        if on_progress:
            on_progress(
                "transcribe",
                {
                    "message": f"Transcrevendo ({duration_s:.0f}s de áudio)…",
                    "percent": 20,
                    "duration_s": duration_s,
                },
            )

        with self._lock:
            processor = self._processor
            model = self._model
            try:
                processor.set_num_lookahead_tokens(lookahead_tokens)
            except Exception:  # noqa: BLE001
                pass

            first_n = int(getattr(processor, "num_samples_first_audio_chunk", len(wave)))
            first_chunk = wave[: min(len(wave), first_n)]
            first_chunk_inputs = processor(
                first_chunk,
                sampling_rate=sampling_rate,
                is_streaming=True,
                is_first_audio_chunk=True,
                language=lang,
                return_tensors="pt",
            )
            first_chunk_inputs = first_chunk_inputs.to(self._device, dtype=model.dtype)

            mel_first = int(
                getattr(
                    processor,
                    "num_mel_frames_first_audio_chunk",
                    first_chunk_inputs.input_features.shape[1],
                )
            )
            hop_length = int(processor.feature_extractor.hop_length)
            n_fft = int(processor.feature_extractor.n_fft)
            samples_per_chunk = int(
                getattr(processor, "num_samples_per_audio_chunk", first_n)
            )
            mel_per_chunk = int(
                getattr(processor, "num_mel_frames_per_audio_chunk", mel_first)
            )

            def input_features_generator():
                yield first_chunk_inputs.input_features[:, :mel_first, :]
                mel_frame_idx = mel_first
                start_idx = mel_frame_idx * hop_length - n_fft // 2
                while True:
                    end_idx = start_idx + samples_per_chunk
                    if end_idx > wave.shape[0]:
                        # último pedaço parcial, se ainda houver áudio útil
                        if start_idx < wave.shape[0] and wave.shape[0] - start_idx > hop_length:
                            tail = wave[max(0, start_idx) :]
                            inputs = processor(
                                tail,
                                sampling_rate=sampling_rate,
                                is_streaming=True,
                                is_first_audio_chunk=False,
                                language=lang,
                                return_tensors="pt",
                            )
                            inputs = inputs.to(self._device, dtype=model.dtype)
                            yield inputs.input_features
                        break
                    inputs = processor(
                        wave[start_idx:end_idx],
                        sampling_rate=sampling_rate,
                        is_streaming=True,
                        is_first_audio_chunk=False,
                        language=lang,
                        return_tensors="pt",
                    )
                    inputs = inputs.to(self._device, dtype=model.dtype)
                    yield inputs.input_features
                    mel_frame_idx += mel_per_chunk
                    start_idx = mel_frame_idx * hop_length - n_fft // 2

            streamer = TextIteratorStreamer(
                processor.tokenizer,
                skip_special_tokens=skip_special,
            )
            generate_kwargs = {
                **first_chunk_inputs,
                "input_features": input_features_generator(),
                "streamer": streamer,
            }

            collected: list[str] = []
            error_box: list[BaseException] = []

            def _run_generate() -> None:
                try:
                    with torch.inference_mode():
                        model.generate(**generate_kwargs)
                except BaseException as exc:  # noqa: BLE001
                    error_box.append(exc)

            worker = threading.Thread(target=_run_generate, daemon=True)
            worker.start()

            for piece in streamer:
                if not piece:
                    continue
                collected.append(piece)
                if on_partial:
                    on_partial("".join(collected))

            worker.join()
            if error_box:
                raise error_box[0]

            text = "".join(collected).strip()
            if not text:
                # Fallback offline se o streamer não emitiu tokens
                inputs = processor(
                    wave,
                    sampling_rate=sampling_rate,
                    language=lang,
                    return_tensors="pt",
                )
                inputs = inputs.to(self._device, dtype=model.dtype)
                with torch.inference_mode():
                    output = model.generate(**inputs, return_dict_in_generate=True)
                text = processor.decode(
                    output.sequences,
                    skip_special_tokens=skip_special,
                )
                if isinstance(text, list):
                    text = text[0] if text else ""
                text = (text or "").strip()
                if on_partial and text:
                    on_partial(text)

        if on_progress:
            on_progress("transcribe", {"message": "Transcrição concluída", "percent": 100})

        return {
            "text": text,
            "language": lang,
            "duration_s": duration_s,
            "device": str(self._device),
            "model_id": MODEL_ID,
        }


engine = AsrEngine()
