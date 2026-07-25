"""Agente de polimento leve e determinístico do texto final (sem LLM)."""

from __future__ import annotations

import re


_SENTENCE_LANG_PREFIXES = (
    "pt",
    "en",
    "es",
    "fr",
    "de",
    "it",
    "ru",
    "nl",
    "pl",
    "sv",
    "no",
    "da",
    "fi",
    "tr",
    "ro",
    "cs",
    "hu",
    "el",
)


class PolishAgent:
    """Limpeza determinística: whitespace, pontuação espaçada, ponto final."""

    name = "polish"

    def polish(self, text: str, language: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r" +\n", "\n", cleaned)
        cleaned = re.sub(r"\n +", "\n", cleaned)

        # "palavra ," → "palavra,"
        cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
        # "( palavra" / "palavra )"
        cleaned = re.sub(r"([(\[{])\s+", r"\1", cleaned)
        cleaned = re.sub(r"\s+([)\]}])", r"\1", cleaned)
        # Aspas / pontuação colada a espaços internos óbvios
        cleaned = re.sub(r"\s{2,}", " ", cleaned)

        if self._looks_sentence_like(language) and cleaned:
            if cleaned[-1] not in ".!?…»:\"')]}":
                # Evita forçar ponto em títulos curtos sem letras.
                if re.search(r"[A-Za-zÀ-ÿ]", cleaned):
                    cleaned = cleaned + "."

        return cleaned.strip()

    @staticmethod
    def _looks_sentence_like(language: str) -> bool:
        lang = (language or "").strip().lower()
        if not lang or lang == "auto":
            return True
        # "pt-BR" → "pt"
        primary = lang.split("-", 1)[0]
        return primary in _SENTENCE_LANG_PREFIXES
