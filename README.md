> **Idioma / Language:** **English** · [Español](README.es.md)

# 🌐 Web Research Agent

Ask a question in **natural language** and the agent researches the web on its own
—it searches, reads pages and synthesizes— to answer you **with citations to the
sources**. It uses **native tool-calling** with the **DeepSeek** API: the model
decides what to search and what to read, and you'll see every step **live**.

It works with a **web interface** (Streamlit, with history and memory) or via
**CLI**.

```
?  What is the Model Context Protocol?

  🔍 searching: Model Context Protocol Anthropic
  📄 reading: modelcontextprotocol.io
  📄 reading: anthropic.com

  Answer
  MCP is an open protocol that standardizes how applications provide context to
  language models [1]. It works like a "USB-C for AI", connecting models to data
  sources and tools [2].

  Sources
  [1] Introduction - Model Context Protocol — modelcontextprotocol.io
  [2] Introducing the Model Context Protocol — anthropic.com
```

The agent figured out the sequence on its own: it searched the topic, picked the
most relevant pages, read them and cited each statement with its source.

## The problem

Answering a question well with information from the internet means searching,
opening several pages, reading them, contrasting and **citing where each fact
came from**. Doing it by hand is slow; asking an LLM "as is" produces plausible
answers but **without sources and with a risk of hallucination**.

## The solution

An **agent** (not a pipeline) that, given a question, decides on its own what to
do using a **ReAct** pattern (Reason + Act):

1. It receives the question along with the available tools.
2. The **model picks** a tool (`web_search` or `read_url`) and its arguments.
3. It runs and the result goes back to the model.
4. This repeats until it has enough to answer **with citations [N]**.

Each page read is numbered as a source in the order it's read, and the system
appends the **bibliography** at the end automatically: this makes every statement
**verifiable** (anti-hallucination).

## Features

- 🔎 **Autonomous research**: the model decides what to search and read (ReAct).
- 📚 **Answers with verifiable citations** `[N]` + source list.
- 🖥️ **Web interface** (Streamlit): live steps, clickable sources, dark theme.
- 💬 **Conversational memory**: within a conversation you can ask follow-up
  questions ("and who created it?") and the agent remembers the context.
- 🗂️ **Persistent history**: each conversation is saved and reopened from the side
  panel.
- 🧪 **Network-free tests**: the CI doesn't consume your API quota.

## Tools

| Tool | What it does |
|------|--------------|
| `web_search(query, max_results)` | Searches the web (DuckDuckGo, no API key) and returns title, URL and snippet |
| `read_url(url)` | Downloads a page, cleans the HTML (removes nav/scripts/footer) and returns its text |

## Architecture

```
app.py            Web interface (Streamlit): history + memory + live steps.
src/
├── llm.py        DeepSeek client (OpenAI-compatible API): tool-calling.
├── tools.py      web_search + read_url + SourceRegistry (numbers and dedupes citations).
├── agent.py      ReAct loop: the model picks tools until it can answer with [N].
├── history.py    Conversation persistence in history.json (memory).
└── main.py       Interactive CLI (rich) with live step streaming.
tests/            Tests with mocks (no real network, no API calls).
```

## Requirements

- **Python 3.10+**
- A **DeepSeek API key** → get it at https://platform.deepseek.com

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/mauriciodejuantrabajo/web-research-agent.git
cd web-research-agent

# 2. (Optional) create a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the API key (see next section)
```

## Configuration

Copy the environment variables template and fill in your API key:

```bash
cp .env.example .env       # on Windows: copy .env.example .env
```

Edit `.env` and set your DeepSeek key:

```env
DEEPSEEK_API_KEY=sk-your-real-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

> 🔒 **The `.env` file is in `.gitignore` and is never committed.** Your API key
> stays only on your machine. The versioned file is `.env.example`, which only
> contains a placeholder (`sk-...`).

## Usage

### Web interface (recommended)

```bash
streamlit run app.py
```

It opens at `http://localhost:8501`. Type your question, watch the agent search
and read live, and get the answer with its sources. You can ask **follow-up
questions** (it remembers the conversation) and reopen **previous conversations**
from the side panel.

### CLI

```bash
python -m src.main                                       # interactive mode
python -m src.main "What is the Model Context Protocol?"  # single question
```

Inside the CLI you'll see each search/read live and, at the end, the answer with
`[N]` citations and the source list. `salir` to exit.

## The model

It uses the **DeepSeek** API (OpenAI-compatible format). The model is configurable
in `.env` without touching code:

```env
DEEPSEEK_MODEL=deepseek-v4-flash
```

If your account has a different model, just put its exact identifier in
`DEEPSEEK_MODEL`.

## Tests

```bash
pytest
```

The tests mock `requests` and the search engine, and replace the LLM with a fake
one with predefined responses: **no real network call is made**, so the CI is
reproducible and doesn't consume your API quota.

## Privacy and data

- `.env` (your API key) and `history.json` (your conversations) **are not
  versioned**: they're in `.gitignore`.
- The history is saved only on your machine, in `history.json`.

## License

[MIT](LICENSE) © Mauricio De Juan
