"""
CLI interactivo del Web Research Agent.

Uso:
    python -m src.main
    python -m src.main "¿Qué es el Model Context Protocol?"   # pregunta única
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .agent import WebResearchAgent
from .llm import LLMError, get_client
from .tools import SourceRegistry, WebTools

console = Console()


def answer_once(agent: WebResearchAgent, question: str) -> None:
    """Procesa una pregunta y muestra respuesta + fuentes."""
    try:
        result = agent.ask(question)
    except LLMError as exc:
        console.print(f"[red]Error de LLM:[/red] {exc}")
        return

    console.print(Panel(result.answer, title="Respuesta", border_style="green"))
    if result.sources:
        console.print(Panel(result.sources, title="Fuentes", border_style="cyan"))


def build_agent() -> WebResearchAgent:
    llm = get_client()
    # Un registro de fuentes por sesión de pregunta (se renueva en cada ask interactivo).
    tools = WebTools(registry=SourceRegistry())

    def show_step(step) -> None:
        if step.tool == "web_search":
            console.print(f"[dim]  🔍 buscando: {step.args.get('query', '')}[/dim]")
        elif step.tool == "read_url":
            console.print(f"[dim]  📄 leyendo: {step.args.get('url', '')}[/dim]")
        else:
            console.print(f"[dim]  → {step.tool}({step.args})[/dim]")

    return WebResearchAgent(tools, llm, on_step=show_step)


def main() -> None:
    parser = argparse.ArgumentParser(description="Web Research Agent (CLI)")
    parser.add_argument(
        "question", nargs="?", default=None,
        help="Pregunta única; si se omite, se entra en modo interactivo.",
    )
    args = parser.parse_args()

    load_dotenv()

    # Modo pregunta única (útil para demos y scripting).
    if args.question:
        answer_once(build_agent(), args.question)
        return

    console.print(Panel.fit(
        "[bold]Web Research Agent[/bold]\n"
        "Hago preguntas a la web, leo páginas y respondo con citas a las fuentes.\n"
        "[dim]Escribí tu pregunta. 'salir' para terminar.[/dim]",
        border_style="blue",
    ))

    while True:
        try:
            question = console.input("\n[bold cyan]?[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n¡Hasta luego!")
            break

        if not question:
            continue
        if question.lower() in {"salir", "exit", "quit", "q"}:
            console.print("¡Hasta luego!")
            break

        # Un agente nuevo por pregunta → registro de fuentes limpio.
        answer_once(build_agent(), question)


if __name__ == "__main__":
    main()
