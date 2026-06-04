"""
Tests de persistencia del historial y de la memoria conversacional del agente.

No tocan red ni la API: el LLM se reemplaza por uno falso y el store escribe en
un archivo temporal (tmp_path de pytest).
"""

from __future__ import annotations

from unittest.mock import patch

from src.agent import WebResearchAgent
from src.history import Conversation, HistoryStore
from src.tools import WebTools


# ---------- HistoryStore ----------

def test_upsert_and_load_roundtrip(tmp_path):
    store = HistoryStore(path=tmp_path / "history.json")
    conv = Conversation.new(title="¿Qué es MCP?")
    conv.add_user("¿Qué es MCP?")
    conv.add_assistant("Es un protocolo [1].", sources=[{"url": "https://a.com", "title": "A"}])
    store.upsert(conv)

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].title == "¿Qué es MCP?"
    assert loaded[0].turns[1].sources[0]["url"] == "https://a.com"


def test_upsert_updates_same_id_and_orders_recent_first(tmp_path):
    store = HistoryStore(path=tmp_path / "history.json")
    a = Conversation.new(title="primera")
    b = Conversation.new(title="segunda")
    store.upsert(a)
    store.upsert(b)
    # Re-guardar 'a' no la duplica, pero la lleva al frente.
    a.add_user("seguimiento")
    store.upsert(a)

    loaded = store.load()
    assert [c.id for c in loaded] == [a.id, b.id]
    assert len(loaded) == 2


def test_delete(tmp_path):
    store = HistoryStore(path=tmp_path / "history.json")
    conv = Conversation.new(title="borrame")
    store.upsert(conv)
    store.delete(conv.id)
    assert store.load() == []


def test_load_missing_file_is_empty(tmp_path):
    assert HistoryStore(path=tmp_path / "nope.json").load() == []


def test_as_history_format():
    conv = Conversation.new(title="x")
    conv.add_user("hola")
    conv.add_assistant("chau", sources=[{"url": "u", "title": "t"}])
    hist = conv.as_history()
    assert hist == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "chau"},
    ]


# ---------- Memoria conversacional en el agente ----------

class FakeLLM:
    """Captura los mensajes recibidos para verificar que el historial llegó."""

    def __init__(self, reply: str):
        self.reply = reply
        self.last_messages = None

    def chat(self, messages, tools=None):
        self.last_messages = messages
        return {"role": "assistant", "content": self.reply}


def test_agent_includes_history_as_context():
    llm = FakeLLM("Lo creó Anthropic.")
    agent = WebResearchAgent(WebTools(), llm, max_iters=3)

    history = [
        {"role": "user", "content": "¿Qué es MCP?"},
        {"role": "assistant", "content": "Es un protocolo abierto."},
    ]
    result = agent.ask("¿Y quién lo creó?", history=history)

    # El prompt enviado al modelo debe contener system + los 2 turnos previos + la nueva pregunta.
    roles = [m["role"] for m in llm.last_messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert llm.last_messages[1]["content"] == "¿Qué es MCP?"
    assert llm.last_messages[-1]["content"] == "¿Y quién lo creó?"
    assert result.answer == "Lo creó Anthropic."


def test_agent_without_history_is_unchanged():
    llm = FakeLLM("respuesta")
    agent = WebResearchAgent(WebTools(), llm, max_iters=3)
    agent.ask("pregunta sola")
    roles = [m["role"] for m in llm.last_messages]
    assert roles == ["system", "user"]
