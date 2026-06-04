"""
Persistencia del historial de conversaciones en un archivo JSON.

Cada conversación tiene un id, un título (la primera pregunta), un timestamp y una
lista de turnos. Un turno de usuario es {role:'user', content}. Un turno del
asistente guarda además las fuentes citadas, para poder re-renderizarlas al
reabrir la conversación: {role:'assistant', content, sources:[{url,title}]}.

El formato es deliberadamente simple (un solo .json) para que sea fácil de
inspeccionar y no agregue dependencias. La escritura es atómica (archivo temporal
+ replace) para no corromper el historial si el proceso muere a mitad de guardado.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent.parent / "history.json"


@dataclass
class Turn:
    role: str                       # 'user' | 'assistant'
    content: str
    sources: list[dict] = field(default_factory=list)  # [{url, title}], solo assistant


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str
    turns: list[Turn] = field(default_factory=list)

    @classmethod
    def new(cls, title: str) -> "Conversation":
        return cls(
            id=uuid.uuid4().hex[:12],
            title=title[:80],
            created_at=datetime.now().isoformat(timespec="seconds"),
            turns=[],
        )

    def add_user(self, content: str) -> None:
        self.turns.append(Turn(role="user", content=content))

    def add_assistant(self, content: str, sources: list[dict] | None = None) -> None:
        self.turns.append(Turn(role="assistant", content=content, sources=sources or []))

    def as_history(self) -> list[dict]:
        """Turnos en el formato que espera WebResearchAgent.ask(history=...)."""
        return [{"role": t.role, "content": t.content} for t in self.turns]


class HistoryStore:
    """Lee y escribe la lista de conversaciones en un único archivo JSON."""

    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)

    def load(self) -> list[Conversation]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        convs: list[Conversation] = []
        for item in raw:
            turns = [Turn(**t) for t in item.get("turns", [])]
            convs.append(Conversation(
                id=item["id"],
                title=item.get("title", "(sin título)"),
                created_at=item.get("created_at", ""),
                turns=turns,
            ))
        return convs

    def save_all(self, conversations: list[Conversation]) -> None:
        data = [asdict(c) for c in conversations]
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)  # reemplazo atómico

    def upsert(self, conversation: Conversation) -> None:
        """Inserta o actualiza una conversación por id (la más reciente queda primera)."""
        convs = [c for c in self.load() if c.id != conversation.id]
        convs.insert(0, conversation)
        self.save_all(convs)

    def delete(self, conversation_id: str) -> None:
        convs = [c for c in self.load() if c.id != conversation_id]
        self.save_all(convs)
