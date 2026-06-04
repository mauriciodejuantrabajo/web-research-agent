"""
Interfaz web del Web Research Agent (Streamlit).

Reutiliza el mismo agente que el CLI (src/agent.py). Suma:
  - Memoria conversacional: el agente recibe los turnos previos de la conversación
    activa, así puede responder preguntas de seguimiento ("¿y quién lo creó?").
  - Historial persistente: cada conversación se guarda en history.json y puede
    reabrirse desde el panel lateral.

Lanzar con:
    streamlit run app.py
"""

from __future__ import annotations

from urllib.parse import urlparse

from dotenv import load_dotenv

import streamlit as st

from src.agent import WebResearchAgent
from src.history import Conversation, HistoryStore
from src.llm import LLMError, get_client
from src.tools import SourceRegistry, WebTools

load_dotenv()

st.set_page_config(
    page_title="Web Research Agent",
    page_icon="🌐",
    layout="centered",
    initial_sidebar_state="expanded",
)

store = HistoryStore()

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(1200px 600px at 10% -10%, rgba(99,102,241,.18), transparent 60%),
          radial-gradient(1000px 500px at 110% 10%, rgba(14,165,233,.16), transparent 55%),
          #0b0f1a;
      }
      .block-container { padding-top: 2.2rem; max-width: 820px; }

      .hero { text-align: center; margin-bottom: 1.4rem; }
      .hero h1 {
        font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0;
        background: linear-gradient(90deg, #818cf8, #38bdf8 55%, #34d399);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
      }
      .hero p {
        color: #94a3b8; font-size: 1.02rem; margin: .55rem auto 0;
        max-width: 560px; line-height: 1.5;
      }

      .examples-label {
        color: #64748b; font-size: .8rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: .08em; margin: .4rem 0 .5rem;
      }
      div[data-testid="stButton"] > button {
        background: rgba(148,163,184,.06);
        border: 1px solid rgba(148,163,184,.18);
        color: #cbd5e1; border-radius: 12px; padding: .65rem .8rem;
        font-size: .86rem; font-weight: 500; text-align: left;
        line-height: 1.3; transition: all .18s ease; min-height: 64px;
      }
      div[data-testid="stButton"] > button:hover {
        border-color: rgba(129,140,248,.6); background: rgba(99,102,241,.12);
        color: #e0e7ff; transform: translateY(-2px);
      }

      /* Sidebar / historial */
      section[data-testid="stSidebar"] { background: #0d1220; }
      section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        min-height: 0; padding: .5rem .7rem; font-size: .82rem;
        border-radius: 10px;
      }

      div[data-testid="stChatMessage"] {
        background: rgba(255,255,255,.025);
        border: 1px solid rgba(148,163,184,.12);
        border-radius: 16px; padding: .4rem .2rem;
      }
      .answer-card { font-size: 1.04rem; line-height: 1.7; color: #e2e8f0; }

      .sources-title {
        color: #94a3b8; font-size: .82rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .08em; margin: 1.2rem 0 .5rem;
      }
      .source-card {
        display: block; text-decoration: none;
        background: rgba(255,255,255,.03);
        border: 1px solid rgba(148,163,184,.16);
        border-radius: 12px; padding: .7rem .9rem; margin-bottom: .55rem;
        transition: all .16s ease;
      }
      .source-card:hover {
        border-color: rgba(56,189,248,.55); background: rgba(56,189,248,.08);
        transform: translateX(3px);
      }
      .source-card .row { display: flex; align-items: baseline; gap: .55rem; }
      .source-card .num {
        flex: 0 0 auto; display: inline-flex; align-items: center;
        justify-content: center; width: 22px; height: 22px;
        font-size: .72rem; font-weight: 700; color: #0b0f1a;
        background: #38bdf8; border-radius: 6px;
      }
      .source-card .title { color: #e2e8f0; font-weight: 600; font-size: .92rem; line-height: 1.35; }
      .source-card .domain {
        color: #64748b; font-size: .78rem; margin-top: .15rem;
        padding-left: calc(22px + .55rem);
      }

      footer, #MainMenu { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers de render
# ---------------------------------------------------------------------------
def _domain(url: str) -> str:
    try:
        net = urlparse(url).netloc
        return net[4:] if net.startswith("www.") else net or url
    except Exception:  # noqa: BLE001
        return url


def render_step_label(step) -> str:
    if step.tool == "web_search":
        return f"🔍 **Buscando** · _{step.args.get('query', '')}_"
    if step.tool == "read_url":
        return f"📄 **Leyendo** · {_domain(step.args.get('url', ''))}"
    return f"→ {step.tool}({step.args})"


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    st.markdown('<div class="sources-title">📚 Fuentes</div>', unsafe_allow_html=True)
    for i, src in enumerate(sources, start=1):
        url, title = src["url"], src["title"]
        st.markdown(
            f"""
            <a class="source-card" href="{url}" target="_blank" rel="noopener">
              <div class="row"><span class="num">{i}</span>
                <span class="title">{title}</span></div>
              <div class="domain">{_domain(url)}</div>
            </a>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Estado de sesión: conversación activa
# ---------------------------------------------------------------------------
if "conv" not in st.session_state:
    st.session_state.conv = None  # type: ignore[assignment]


def start_new_conversation() -> None:
    st.session_state.conv = None


def open_conversation(conv_id: str) -> None:
    for c in store.load():
        if c.id == conv_id:
            st.session_state.conv = c
            return


# ---------------------------------------------------------------------------
# Sidebar: historial de conversaciones
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💬 Conversaciones")
    if st.button("＋ Nueva conversación", use_container_width=True):
        start_new_conversation()

    st.divider()
    saved = store.load()
    if not saved:
        st.caption("Todavía no hay conversaciones guardadas.")
    active_id = st.session_state.conv.id if st.session_state.conv else None
    for c in saved:
        label = ("🟢 " if c.id == active_id else "") + c.title
        if st.button(label, key=f"open_{c.id}", use_container_width=True):
            open_conversation(c.id)
        st.caption(c.created_at.replace("T", "  ·  "))


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>🌐 Web Research Agent</h1>
      <p>Hago una pregunta a la web, leo las páginas y respondo
         <b>con citas a las fuentes</b>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Render del hilo de la conversación activa
# ---------------------------------------------------------------------------
conv = st.session_state.conv
if conv:
    for turn in conv.turns:
        if turn.role == "user":
            st.chat_message("user", avatar="🧑").write(turn.content)
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(f'<div class="answer-card">{turn.content}</div>',
                            unsafe_allow_html=True)
                render_sources(turn.sources)


# ---------------------------------------------------------------------------
# Ejemplos rápidos (solo en una conversación nueva/vacía)
# ---------------------------------------------------------------------------
example_clicked = None
if not conv:
    EXAMPLES = [
        "¿Qué es el Model Context Protocol?",
        "¿Qué novedades trae Python 3.13?",
        "¿Quién ganó el último Balón de Oro y por qué?",
    ]
    st.markdown('<div class="examples-label">Probá un ejemplo</div>', unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, ex in zip(cols, EXAMPLES):
        if col.button(ex, use_container_width=True):
            example_clicked = ex

placeholder = "Preguntá algo de seguimiento…" if conv else "Escribí tu pregunta…"
question = st.chat_input(placeholder) or example_clicked


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------
if question:
    # Crear la conversación si es la primera pregunta.
    if st.session_state.conv is None:
        st.session_state.conv = Conversation.new(title=question)
    conv = st.session_state.conv

    st.chat_message("user", avatar="🧑").write(question)

    try:
        llm = get_client()
    except LLMError as exc:
        st.error(str(exc))
        st.stop()

    tools = WebTools(registry=SourceRegistry())

    with st.chat_message("assistant", avatar="🤖"):
        steps_box = st.status("🔎 Investigando…", expanded=True)

        def on_step(step) -> None:
            steps_box.markdown(render_step_label(step))

        agent = WebResearchAgent(tools, llm, on_step=on_step)

        try:
            # Memoria: pasamos los turnos previos de esta conversación como contexto.
            result = agent.ask(question, history=conv.as_history())
        except LLMError as exc:
            steps_box.update(label="Error", state="error")
            st.error(f"Error de LLM: {exc}")
            st.stop()

        steps_box.update(
            label=f"✅ Investigación completa · {len(result.steps)} pasos",
            state="complete", expanded=False,
        )

        st.markdown(f'<div class="answer-card">{result.answer}</div>',
                    unsafe_allow_html=True)

        sources = [{"url": s.url, "title": s.title} for s in tools.registry.sources]
        render_sources(sources)

    # Persistir el turno en la conversación y en disco.
    conv.add_user(question)
    conv.add_assistant(result.answer, sources=sources)
    store.upsert(conv)
    st.rerun()  # refresca el sidebar (título/orden) y el hilo ya persistido
