"""
Tests de las herramientas web y del loop del agente.

No se hace ninguna llamada de red real: `requests` y `DDGS` se mockean, y el LLM
se reemplaza por un cliente falso que devuelve tool_calls predefinidos. Así el CI
es reproducible y no depende de internet ni de la API de DeepSeek.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent import WebResearchAgent
from src.tools import SourceRegistry, WebTools


# ---------- SourceRegistry ----------

def test_registry_numbers_and_dedupes():
    reg = SourceRegistry()
    assert reg.add("https://a.com", "A") == 1
    assert reg.add("https://b.com", "B") == 2
    # La misma URL no se vuelve a numerar.
    assert reg.add("https://a.com", "A otra vez") == 1
    assert len(reg.sources) == 2


def test_registry_bibliography_format():
    reg = SourceRegistry()
    reg.add("https://a.com", "Título A")
    bib = reg.bibliography()
    assert "[1] Título A" in bib
    assert "https://a.com" in bib


def test_empty_registry_has_no_bibliography():
    assert SourceRegistry().bibliography() == ""


# ---------- read_url ----------

def test_read_url_rejects_invalid_scheme():
    tools = WebTools()
    out = tools.read_url("ftp://nope.com")
    assert "URL inválida" in out


def test_read_url_strips_noise_and_truncates():
    html = (
        "<html><head><title>Mi Página</title></head>"
        "<body><nav>menu</nav><p>Contenido importante.</p>"
        "<script>alert(1)</script><footer>pie</footer></body></html>"
    )
    fake_resp = MagicMock(status_code=200, text=html)
    fake_resp.headers = {"Content-Type": "text/html"}
    fake_resp.raise_for_status = MagicMock()

    tools = WebTools()
    with patch.object(tools.session, "get", return_value=fake_resp):
        out = tools.read_url("https://example.com")

    assert "Contenido importante." in out
    assert "alert(1)" not in out  # el <script> se eliminó
    assert "menu" not in out       # el <nav> se eliminó
    assert "[Fuente 1]" in out     # quedó registrada como fuente citable
    assert tools.registry.sources[0].title == "Mi Página"


def test_read_url_rejects_non_text_content():
    fake_resp = MagicMock(status_code=200, text="")
    fake_resp.headers = {"Content-Type": "application/pdf"}
    fake_resp.raise_for_status = MagicMock()

    tools = WebTools()
    with patch.object(tools.session, "get", return_value=fake_resp):
        out = tools.read_url("https://example.com/doc.pdf")
    assert "no es una página de texto" in out


# ---------- web_search ----------

def test_web_search_formats_results():
    fake_results = [
        {"title": "Resultado 1", "href": "https://r1.com", "body": "snippet 1"},
        {"title": "Resultado 2", "href": "https://r2.com", "body": "snippet 2"},
    ]
    tools = WebTools()
    with patch("src.tools.DDGS") as ddgs_cls:
        ddgs_cls.return_value.__enter__.return_value.text.return_value = fake_results
        out = tools.web_search("una consulta")

    assert "Resultado 1" in out
    assert "https://r1.com" in out
    assert "una consulta" in out


def test_web_search_empty_query():
    assert "vacía" in WebTools().web_search("   ")


# ---------- Agent loop ----------

class FakeLLM:
    """LLM falso: devuelve, en orden, los mensajes que se le configuran."""

    def __init__(self, scripted_messages):
        self._messages = list(scripted_messages)
        self.calls = 0

    def chat(self, messages, tools=None):
        msg = self._messages[self.calls]
        self.calls += 1
        return msg


def test_agent_runs_tools_then_answers():
    # Turno 1: el modelo pide leer una URL. Turno 2: responde con texto final.
    scripted = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "function": {"name": "read_url", "arguments": {"url": "https://x.com"}},
            }],
        },
        {"role": "assistant", "content": "La respuesta es 42 [1]."},
    ]
    llm = FakeLLM(scripted)

    tools = WebTools()
    fake_resp = MagicMock(status_code=200, text="<title>X</title><p>dato</p>")
    fake_resp.headers = {"Content-Type": "text/html"}
    fake_resp.raise_for_status = MagicMock()

    with patch.object(tools.session, "get", return_value=fake_resp):
        agent = WebResearchAgent(tools, llm, max_iters=5)
        result = agent.ask("¿cuál es la respuesta?")

    assert "42" in result.answer
    assert len(result.steps) == 1
    assert result.steps[0].tool == "read_url"
    assert "[1]" in result.sources  # la fuente leída quedó en la bibliografía


def test_agent_respects_max_iters():
    # El modelo siempre pide una tool → nunca termina solo.
    loop_msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "c",
            "function": {"name": "web_search", "arguments": {"query": "x"}},
        }],
    }
    llm = FakeLLM([loop_msg] * 10)
    tools = WebTools()
    with patch("src.tools.DDGS") as ddgs_cls:
        ddgs_cls.return_value.__enter__.return_value.text.return_value = []
        agent = WebResearchAgent(tools, llm, max_iters=3)
        result = agent.ask("loop infinito")

    assert llm.calls == 3
    assert "límite de pasos" in result.answer


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
