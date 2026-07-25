"""Agente de segmentação inteligente de áudio para respeitar max_position_embeddings."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

ProgressCallback = Callable[[str, dict[str, Any]], None]

# Defaults alinhados ao FastConformer (mel hop @ 16 kHz, subsampling 8×).
DEFAULT_HOP_LENGTH = 160
DEFAULT_SUBSAMPLE_FACTOR = 8
# Limite duro do modelo ≈ 5000; margem de segurança.
DEFAULT_MAX_ENCODER_FRAMES = 4800
DEFAULT_ENERGY_WINDOW_MS = 30.0
DEFAULT_OVERLAP_S = 0.4
DEFAULT_MIN_SEGMENT_S = 1.5
# Janela (em fração do budget) para procurar silêncio perto do corte ideal.
DEFAULT_SEARCH_FRACTION = 0.12
DEFAULT_MIN_SEARCH_S = 2.0


@dataclass
class AudioSegment:
    """Trecho de áudio pronto para ASR, com metadados do corte."""

    index: int
    start_s: float
    end_s: float
    audio: np.ndarray  # float32 mono
    reason: str
    overlap_s: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class SegmenterAgent:
    """Divide áudio longo em chunks que cabem no budget de encoder frames.

    Estratégia:
    - Estima frames do encoder (mel hop + subsampling).
    - Prefere cortes em regiões de baixa energia (quase-silêncio) perto do budget.
    - Evita migalhas finais curtas (< min_segment_s) fundindo no segmento anterior.
    - Aplica overlap opcional nas bordas para continuidade do ASR.
    """

    def __init__(
        self,
        *,
        hop_length: int = DEFAULT_HOP_LENGTH,
        subsample_factor: int = DEFAULT_SUBSAMPLE_FACTOR,
        energy_window_ms: float = DEFAULT_ENERGY_WINDOW_MS,
        overlap_s: float = DEFAULT_OVERLAP_S,
        min_segment_s: float = DEFAULT_MIN_SEGMENT_S,
        search_fraction: float = DEFAULT_SEARCH_FRACTION,
        min_search_s: float = DEFAULT_MIN_SEARCH_S,
    ) -> None:
        if hop_length < 1:
            raise ValueError("hop_length must be >= 1")
        if subsample_factor < 1:
            raise ValueError("subsample_factor must be >= 1")
        if energy_window_ms <= 0:
            raise ValueError("energy_window_ms must be > 0")
        if overlap_s < 0:
            raise ValueError("overlap_s must be >= 0")
        if min_segment_s < 0:
            raise ValueError("min_segment_s must be >= 0")

        self.hop_length = int(hop_length)
        self.subsample_factor = int(subsample_factor)
        self.energy_window_ms = float(energy_window_ms)
        self.overlap_s = float(overlap_s)
        self.min_segment_s = float(min_segment_s)
        self.search_fraction = float(search_fraction)
        self.min_search_s = float(min_search_s)

    def estimate_encoder_frames(
        self,
        n_samples: int,
        sampling_rate: int,  # noqa: ARG002 — API pública; hop é em samples @ rate do modelo
    ) -> int:
        """Estima frames do encoder: ceil(n_samples / hop / subsample)."""
        n = max(0, int(n_samples))
        if n == 0:
            return 0
        denom = self.hop_length * self.subsample_factor
        return int(math.ceil(n / denom))

    def max_samples_for_budget(
        self,
        sampling_rate: int,  # noqa: ARG002 — mantido para API simétrica
        max_encoder_frames: int = DEFAULT_MAX_ENCODER_FRAMES,
    ) -> int:
        """Máximo de samples que cabem no budget de encoder frames."""
        frames = max(1, int(max_encoder_frames))
        return frames * self.hop_length * self.subsample_factor

    def max_duration_s(
        self,
        sampling_rate: int,
        max_encoder_frames: int = DEFAULT_MAX_ENCODER_FRAMES,
    ) -> float:
        """Duração máxima (segundos) por chunk com o budget dado."""
        sr = max(1, int(sampling_rate))
        return self.max_samples_for_budget(sr, max_encoder_frames) / sr

    def segment(
        self,
        audio: np.ndarray,
        sampling_rate: int,
        *,
        max_encoder_frames: int = DEFAULT_MAX_ENCODER_FRAMES,
        on_progress: ProgressCallback | None = None,
    ) -> list[AudioSegment]:
        """Segmenta áudio preferindo cortes em baixa energia perto do budget."""
        if sampling_rate < 1:
            raise ValueError("sampling_rate must be >= 1")

        wave = np.asarray(audio, dtype=np.float32).reshape(-1)
        n = int(wave.shape[0])
        if n == 0:
            return []

        max_samples = self.max_samples_for_budget(sampling_rate, max_encoder_frames)
        total_frames = self.estimate_encoder_frames(n, sampling_rate)

        if on_progress:
            on_progress(
                "segment",
                {
                    "message": "Analisando áudio para segmentação…",
                    "samples": n,
                    "duration_s": n / sampling_rate,
                    "estimated_encoder_frames": total_frames,
                    "max_encoder_frames": max_encoder_frames,
                    "max_samples": max_samples,
                },
            )

        if n <= max_samples:
            seg = AudioSegment(
                index=0,
                start_s=0.0,
                end_s=n / sampling_rate,
                audio=wave.copy(),
                reason="fits_budget",
                overlap_s=0.0,
                meta={"encoder_frames": total_frames},
            )
            if on_progress:
                on_progress(
                    "segment",
                    {
                        "message": "Áudio cabe no budget; um único segmento",
                        "segments": 1,
                        "percent": 100,
                    },
                )
            return [seg]

        # Energia por janela curta (~30 ms) para achar quase-silêncio.
        win = max(1, int(round(sampling_rate * self.energy_window_ms / 1000.0)))
        rms = self._frame_rms(wave, win)
        search_radius = self._search_radius_samples(max_samples, sampling_rate)

        cuts: list[tuple[int, int, str]] = []  # (start, end, reason) sem overlap
        cursor = 0
        while cursor < n:
            remaining = n - cursor
            if remaining <= max_samples:
                cuts.append((cursor, n, "tail"))
                break

            ideal_end = cursor + max_samples
            # Não cortar além do fim; busca silêncio antes do hard limit.
            hard_end = min(n, ideal_end)
            split_at, reason = self._best_split(
                rms=rms,
                win=win,
                search_start=max(cursor + win, ideal_end - search_radius),
                search_end=hard_end,
                fallback=hard_end,
            )

            # Garante progresso mínimo (evita loop se o split voltar ao cursor).
            min_advance = max(win, int(0.25 * sampling_rate))
            if split_at <= cursor + min_advance:
                split_at = min(n, cursor + max_samples)
                reason = "hard_budget"

            cuts.append((cursor, split_at, reason))
            cursor = split_at

            if on_progress:
                on_progress(
                    "segment",
                    {
                        "message": f"Corte em {split_at / sampling_rate:.1f}s ({reason})",
                        "percent": min(95, int(100 * split_at / n)),
                        "cuts": len(cuts),
                    },
                )

        cuts = self._merge_short_tails(cuts, sampling_rate, max_samples)
        segments = self._materialize(wave, cuts, sampling_rate, max_encoder_frames)

        if on_progress:
            on_progress(
                "segment",
                {
                    "message": f"Segmentação concluída: {len(segments)} trecho(s)",
                    "segments": len(segments),
                    "percent": 100,
                },
            )
        return segments

    # ------------------------------------------------------------------ helpers

    def _search_radius_samples(self, max_samples: int, sampling_rate: int) -> int:
        frac = max(0.0, self.search_fraction) * max_samples
        floor = self.min_search_s * sampling_rate
        return max(1, int(round(max(frac, floor))))

    @staticmethod
    def _frame_rms(wave: np.ndarray, win: int) -> np.ndarray:
        """RMS por janela não sobreposta; último frame incompleto é descartado do índice."""
        n = int(wave.shape[0])
        n_frames = n // win
        if n_frames == 0:
            return np.array([float(np.sqrt(np.mean(wave**2)))], dtype=np.float64)
        trimmed = wave[: n_frames * win].reshape(n_frames, win).astype(np.float64, copy=False)
        return np.sqrt(np.mean(trimmed * trimmed, axis=1))

    def _best_split(
        self,
        *,
        rms: np.ndarray,
        win: int,
        search_start: int,
        search_end: int,
        fallback: int,
    ) -> tuple[int, str]:
        """Escolhe o fim do segmento no frame de menor energia na janela de busca."""
        if search_end <= search_start:
            return fallback, "hard_budget"

        frame_a = max(0, search_start // win)
        frame_b = min(len(rms), max(frame_a + 1, search_end // win))
        if frame_a >= frame_b:
            return fallback, "hard_budget"

        region = rms[frame_a:frame_b]
        # Empate: preferir o corte mais próximo do budget (último mínimo).
        local = int(np.argmin(region[::-1]))
        best_frame = frame_b - 1 - local
        split_at = min(fallback, (best_frame + 1) * win)

        # Se a energia mínima não for claramente baixa, ainda assim usamos o
        # ponto mais quieto — melhor que um corte cego no meio da fala.
        quiet = float(region.min())
        median = float(np.median(region)) if region.size else quiet
        if median > 0 and quiet <= 0.35 * median:
            reason = "low_energy"
        else:
            reason = "lowest_energy_near_budget"
        return max(1, split_at), reason

    def _merge_short_tails(
        self,
        cuts: list[tuple[int, int, str]],
        sampling_rate: int,
        max_samples: int,
    ) -> list[tuple[int, int, str]]:
        """Funde o último pedaço se for migalha (< min_segment_s), sem estourar o budget."""
        if len(cuts) < 2:
            return cuts

        min_samples = int(round(self.min_segment_s * sampling_rate))
        start, end, reason = cuts[-1]
        if (end - start) >= min_samples:
            return cuts

        prev_start, _prev_end, prev_reason = cuts[-2]
        # Nunca fundir se o segmento resultante ultrapassar o budget do encoder.
        if (end - prev_start) > max_samples:
            return cuts

        merged = (prev_start, end, f"{prev_reason}+merged_short_tail")
        return cuts[:-2] + [merged]

    def _materialize(
        self,
        wave: np.ndarray,
        cuts: list[tuple[int, int, str]],
        sampling_rate: int,
        max_encoder_frames: int,
    ) -> list[AudioSegment]:
        """Copia samples com overlap opcional e reindexa após merges."""
        n = int(wave.shape[0])
        overlap = int(round(self.overlap_s * sampling_rate))
        max_samples = self.max_samples_for_budget(sampling_rate, max_encoder_frames)
        segments: list[AudioSegment] = []

        for i, (start, end, reason) in enumerate(cuts):
            # Overlap: estende início (exceto o 1º) e fim (exceto o último),
            # sem estourar o budget de samples do encoder.
            left = start
            right = end
            applied_overlap = 0.0

            if overlap > 0 and i > 0:
                left = max(0, start - overlap)
            if overlap > 0 and i < len(cuts) - 1:
                right = min(n, end + overlap)

            # Se overlap + núcleo estourar o budget, encolhe o overlap simétrico.
            span = right - left
            if span > max_samples:
                excess = span - max_samples
                trim_left = min(start - left, excess // 2)
                left += trim_left
                excess -= trim_left
                trim_right = min(right - end, excess)
                right -= trim_right

            if i > 0 and left < start:
                applied_overlap = (start - left) / sampling_rate
            elif i < len(cuts) - 1 and right > end:
                applied_overlap = (right - end) / sampling_rate

            chunk = np.ascontiguousarray(wave[left:right], dtype=np.float32)
            frames = self.estimate_encoder_frames(len(chunk), sampling_rate)
            segments.append(
                AudioSegment(
                    index=i,
                    start_s=left / sampling_rate,
                    end_s=right / sampling_rate,
                    audio=chunk,
                    reason=reason,
                    overlap_s=applied_overlap,
                    meta={
                        "core_start_s": start / sampling_rate,
                        "core_end_s": end / sampling_rate,
                        "encoder_frames": frames,
                        "max_encoder_frames": max_encoder_frames,
                    },
                )
            )

        return segments
