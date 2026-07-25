"""Agente que une textos de segmentos ASR com deduplicação nas bordas."""

from __future__ import annotations

import re
from typing import Any


_TOKEN_RE = re.compile(r"\S+")


class MergerAgent:
    """Junta segmentos ASR com remoção simples de overlap nas fronteiras."""

    name = "merger"
    MAX_OVERLAP_TOKENS = 12

    def merge(self, segments: list[dict[str, Any]]) -> dict[str, Any]:
        """Une segmentos ordenados por index; retorna texto + segmentos com texto."""
        ordered = sorted(segments, key=lambda s: int(s.get("index", 0)))
        merged_parts: list[str] = []
        out_segments: list[dict[str, Any]] = []

        for seg in ordered:
            raw = str(seg.get("text") or "").strip()
            cleaned = self._normalize_spacing(raw)
            if merged_parts and cleaned:
                cleaned = self._dedupe_boundary(merged_parts[-1], cleaned)
            entry = {
                "index": int(seg.get("index", len(out_segments))),
                "start_s": float(seg.get("start_s", 0.0)),
                "end_s": float(seg.get("end_s", 0.0)),
                "text": cleaned,
                "reason": str(seg.get("reason") or ""),
            }
            out_segments.append(entry)
            if cleaned:
                merged_parts.append(cleaned)

        text = self._join_parts(merged_parts)
        return {"text": text, "segments": out_segments}

    def _dedupe_boundary(self, left: str, right: str) -> str:
        """Remove o maior prefixo de `right` que é sufixo de `left` (até N tokens)."""
        left_tokens = _TOKEN_RE.findall(left)
        right_tokens = _TOKEN_RE.findall(right)
        if not left_tokens or not right_tokens:
            return right

        max_n = min(self.MAX_OVERLAP_TOKENS, len(left_tokens), len(right_tokens))
        best = 0
        for n in range(max_n, 0, -1):
            if self._tokens_equal(left_tokens[-n:], right_tokens[:n]):
                best = n
                break

        if best == 0:
            return right

        # Reconstrói o restante de right a partir do overlap.
        remainder_tokens = right_tokens[best:]
        if not remainder_tokens:
            return ""

        # Preserva pontuação colada: usa posições do texto original quando possível.
        match = list(_TOKEN_RE.finditer(right))
        if len(match) >= best:
            start = match[best].start()
            return right[start:].lstrip()
        return " ".join(remainder_tokens)

    @staticmethod
    def _norm_token(tok: str) -> str:
        return tok.casefold().strip(".,!?;:\"'()[]{}") or tok.casefold()

    @classmethod
    def _tokens_equal(cls, a: list[str], b: list[str]) -> bool:
        if len(a) != len(b):
            return False
        return all(cls._norm_token(x) == cls._norm_token(y) for x, y in zip(a, b))

    @staticmethod
    def _normalize_spacing(text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        return text

    @staticmethod
    def _join_parts(parts: list[str]) -> str:
        if not parts:
            return ""
        out = parts[0]
        for part in parts[1:]:
            if not part:
                continue
            # Espaço entre partes; evita espaço duplo se a próxima começa com pontuação.
            if part[0] in ",.!?;:":
                out = out.rstrip() + part
            else:
                out = out.rstrip() + " " + part.lstrip()
        return out.strip()
