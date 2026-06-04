# 🌐 Web Research Agent

Hacé una pregunta en **lenguaje natural** y el agente investiga en la web por sí
mismo —busca, lee páginas y sintetiza— para responderte **con citas a las
fuentes**. Usa **tool-calling nativo** con la API de **DeepSeek**: el modelo
decide qué buscar y qué leer, y verás cada paso **en vivo**.

Funciona con **interfaz web** (Streamlit, con historial y memoria) o por **CLI**.

```
?  ¿Qué es el Model Context Protocol?

  🔍 buscando: Model Context Protocol Anthropic
  📄 leyendo: modelcontextprotocol.io
  📄 leyendo: anthropic.com

  Respuesta
  El MCP es un protocolo abierto que estandariza cómo las aplicaciones proveen
  contexto a los modelos de lenguaje [1]. Funciona como un "USB-C para IA",
  conectando modelos a fuentes de datos y herramientas [2].

  Fuentes
  [1] Introduction - Model Context Protocol — modelcontextprotocol.io
  [2] Introducing the Model Context Protocol — anthropic.com
```

El agente decidió por su cuenta la secuencia: buscó el tema, eligió las páginas
más relevantes, las leyó y citó cada afirmación con su fuente.

## El problema

Responder bien una pregunta con información de internet implica buscar, abrir
varias páginas, leerlas, contrastar y **citar de dónde salió cada dato**. Hacerlo
a mano es lento; pedírselo a un LLM "a secas" produce respuestas plausibles pero
**sin fuentes y con riesgo de alucinación**.

## La solución

Un **agente** (no un pipeline) que, dada una pregunta, decide por sí mismo qué
hacer usando un patrón **ReAct** (Reason + Act):

1. Recibe la pregunta junto con las herramientas disponibles.
2. El **modelo elige** una herramienta (`web_search` o `read_url`) y sus argumentos.
3. Se ejecuta y el resultado vuelve al modelo.
4. Se repite hasta que tiene suficiente para responder **con citas [N]**.

Cada página leída se numera como fuente en el orden en que se lee, y el sistema
anexa la **bibliografía** al final automáticamente: así cada afirmación es
**verificable** (anti-alucinación).

## Características

- 🔎 **Investigación autónoma**: el modelo decide qué buscar y qué leer (ReAct).
- 📚 **Respuestas con citas** verificables `[N]` + lista de fuentes.
- 🖥️ **Interfaz web** (Streamlit): pasos en vivo, fuentes clicables, tema oscuro.
- 💬 **Memoria conversacional**: dentro de una conversación podés hacer preguntas
  de seguimiento ("¿y quién lo creó?") y el agente recuerda el contexto.
- 🗂️ **Historial persistente**: cada conversación se guarda y se reabre desde el
  panel lateral.
- 🧪 **Tests sin red**: el CI no consume tu cuota de API.

## Herramientas

| Herramienta | Qué hace |
|-------------|----------|
| `web_search(query, max_results)` | Busca en la web (DuckDuckGo, sin API key) y devuelve título, URL y snippet |
| `read_url(url)` | Descarga una página, limpia el HTML (quita nav/scripts/footer) y devuelve su texto |

## Arquitectura

```
app.py            Interfaz web (Streamlit): historial + memoria + pasos en vivo.
src/
├── llm.py        Cliente DeepSeek (API compatible OpenAI): tool-calling.
├── tools.py      web_search + read_url + SourceRegistry (numera y deduplica citas).
├── agent.py      Loop ReAct: el modelo elige tools hasta poder responder con [N].
├── history.py    Persistencia de conversaciones en history.json (memoria).
└── main.py       CLI interactivo (rich) con streaming de pasos en vivo.
tests/            Tests con mocks (sin red real ni llamadas a la API).
```

## Requisitos

- **Python 3.10+**
- Una **API key de DeepSeek** → se obtiene en https://platform.deepseek.com

## Instalación

```bash
# 1. Clonar el repo
git clone https://github.com/mauriciodejuantrabajo/web-research-agent.git
cd web-research-agent

# 2. (Opcional) crear un entorno virtual
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar la API key (ver siguiente sección)
```

## Configuración

Copiá la plantilla de variables de entorno y completá tu API key:

```bash
cp .env.example .env       # en Windows: copy .env.example .env
```

Editá `.env` y poné tu key de DeepSeek:

```env
DEEPSEEK_API_KEY=sk-tu-key-real-aca
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

> 🔒 **El archivo `.env` está en `.gitignore` y nunca se sube al repo.** Tu API key
> queda solo en tu máquina. El archivo versionado es `.env.example`, que solo
> contiene un placeholder (`sk-...`).

## Uso

### Interfaz web (recomendada)

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`. Escribí tu pregunta, mirá cómo el agente busca
y lee en vivo, y obtené la respuesta con sus fuentes. Podés hacer **preguntas de
seguimiento** (recuerda la conversación) y reabrir **conversaciones anteriores**
desde el panel lateral.

### CLI

```bash
python -m src.main                                       # modo interactivo
python -m src.main "¿Qué es el Model Context Protocol?"  # pregunta única
```

Dentro del CLI verás cada búsqueda/lectura en vivo y, al final, la respuesta con
citas `[N]` y la lista de fuentes. `salir` para terminar.

## El modelo

Se usa la API de **DeepSeek** (formato compatible con OpenAI). El modelo es
configurable en `.env` sin tocar código:

```env
DEEPSEEK_MODEL=deepseek-v4-flash
```

Si tu cuenta tiene otro modelo, basta con poner su identificador exacto en
`DEEPSEEK_MODEL`.

## Tests

```bash
pytest
```

Los tests mockean `requests` y el buscador, y reemplazan el LLM por uno falso con
respuestas predefinidas: **no se hace ninguna llamada de red real**, así el CI es
reproducible y no consume tu cuota de API.

## Privacidad y datos

- `.env` (tu API key) y `history.json` (tus conversaciones) **no se versionan**:
  están en `.gitignore`.
- El historial se guarda solo en tu máquina, en `history.json`.

## Licencia

[MIT](LICENSE) © Mauricio De Juan
