"""Contratos compartilhados entre agentes do pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class AgentEvent:
    """Evento de progresso/status emitido por um agente."""

    agent: str
    stage: str
    message: str
    percent: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


class Agent(Protocol):
    """Protocolo mínimo para agentes nomeados do pipeline."""

    name: str


Emitter = Callable[[AgentEvent], None]
