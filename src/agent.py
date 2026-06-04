"""
El agente: un loop ReAct sobre las herramientas de búsqueda y lectura web.

Flujo:
    1. Se envía la pregunta al modelo junto con las tools disponibles.
    2. Si el modelo responde con `tool_calls` (web_search / read_url), se ejecutan
       y el resultado se agrega a la conversación.
    3. Se repite hasta que el modelo responde con texto final (sin tool_calls)
       o se alcanza el tope de iteraciones.

El modelo decide qué buscar, qué páginas leer y cuándo tiene suficiente para
responder con citas. Las fuentes se numeran en el orden en que se leen
(ver SourceRegistry en tools.py) y se anexan al final como bibliografía.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .llm import DeepSeekClient
from .tools import TOOL_SCHEMAS, SourceRegistry, WebTools

SYSTEM_PROMPT = """\
Sos un asistente de investigación que responde preguntas usando la web.

Tenés dos herramientas:
- web_search(query): busca y devuelve resultados con título, URL y snippet.
- read_url(url): descarga una página y devuelve su texto.

Cómo trabajar:
- Empezá buscando con web_search para descubrir fuentes relevantes.
- Leé con read_url las páginas más prometedoras antes de responder (al menos 2
  fuentes distintas cuando sea posible).
- No inventes datos: afirmá solo lo que viste en una página que leíste.
- Cuando una página se lee, su contenido empieza con "[Fuente N]". Usá ese número
  para citar: poné [N] justo después de cada afirmación que provenga de esa fuente.
- Respondé en español, de forma clara y concreta, con las citas [N] intercaladas.
- No agregues vos la lista de fuentes al final: el sistema la anexa automáticamente.
"""


@dataclass
class Step:
    """Un paso de herramienta ejecutado, para mostrar la traza al usuario."""
    tool: str
    args: dict
    result_preview: str


@dataclass
class AgentResult:
    answer: str
    steps: list[Step] = field(default_factory=list)
    sources: str = ""


class WebResearchAgent:
    def __init__(
        self,
        tools: WebTools,
        llm: DeepSeekClient,
        max_iters: int = 8,
        on_step: Callable[[Step], None] | None = None,
    ) -> None:
        self.tools = tools
        self.llm = llm
        self.max_iters = max_iters
        # Callback opcional: se invoca con cada Step apenas se ejecuta (streaming).
        self.on_step = on_step
        self._dispatch = {
            "web_search": self.tools.web_search,
            "read_url": self.tools.read_url,
        }

    def _run_tool(self, name: str, args: dict) -> str:
        fn = self._dispatch.get(name)
        if fn is None:
            return f"Error: herramienta desconocida '{name}'."
        try:
            return fn(**args)
        except TypeError as exc:
            return f"Error: argumentos inválidos para '{name}': {exc}"
        except Exception as exc:  # noqa: BLE001 — el resultado vuelve al modelo
            return f"Error al ejecutar '{name}': {exc}"

    def _finalize(self, answer: str, steps: list[Step]) -> AgentResult:
        return AgentResult(
            answer=answer,
            steps=steps,
            sources=self.tools.registry.bibliography(),
        )

    def ask(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> AgentResult:
        """Responde `question`.

        `history` es una lista opcional de turnos previos de la conversación, en
        formato {'role': 'user'|'assistant', 'content': str}. Si se pasa, el agente
        lo incluye como contexto → puede responder preguntas de seguimiento
        ("¿y quién lo creó?") recordando lo dicho antes.
        """
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            # Solo arrastramos texto de user/assistant (no tool_calls ni fuentes):
            # alcanza para dar contexto y mantiene el prompt liviano.
            for turn in history:
                role = turn.get("role")
                content = (turn.get("content") or "").strip()
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": question})
        steps: list[Step] = []

        for _ in range(self.max_iters):
            msg = self.llm.chat(messages, tools=TOOL_SCHEMAS)
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                # El modelo dio su respuesta final.
                return self._finalize(msg.get("content", "").strip(), steps)

            # Registrar el turno del asistente (con sus tool_calls) en el historial.
            messages.append(msg)

            # Ejecutar cada tool pedida y devolver su resultado.
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {}) or {}
                if isinstance(args, str):  # OpenAI/DeepSeek mandan los args como JSON string
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                result = self._run_tool(name, args)
                step = Step(tool=name, args=args, result_preview=result[:200])
                steps.append(step)
                if self.on_step is not None:
                    self.on_step(step)  # streaming: avisar apenas ocurre
                # El formato OpenAI exige devolver el tool_call_id en la respuesta.
                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": call.get("id", ""),
                    "name": name,
                })

        return self._finalize(
            "(No llegué a una respuesta final dentro del límite de pasos.)",
            steps,
        )
