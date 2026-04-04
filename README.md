# Cortex 🧠

**Local-First AI Knowledge Base Agent**

Ingest research, maintain a living wiki, and answer complex questions — all without a single byte leaving your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## What is Cortex?

Cortex is a privacy-first AI agent that builds and maintains a wiki-based knowledge base from your research documents, code, and notes. Ask it anything — it reads your wiki, synthesizes answers, and writes them up as reports or slides.

- 🧠 **Intelligent Memory** — RAG-powered semantic search across your knowledge base
- 📄 **Wiki Knowledge Base** — Auto-maintained markdown wiki with backlinks and index
- 🔍 **Document Ingest** — PDF, web articles, code repos, data files → structured markdown
- 🤖 **Multi-Agent Orchestration** — Sequential, parallel patterns for complex tasks
- 🔒 **Local-First** — Zero data ever leaves your machine (Ollama by default)
- 📊 **Output Rendering** — Marp slides, matplotlib charts, PDF reports

## Quick Start

```bash
# Install
pip install -e .

# Start Ollama (for local inference)
ollama serve
ollama pull llama3

# Initialize a knowledge base
cortex init ./my-wiki

# Ingest documents
cortex ingest ./papers/
cortex ingest ./articles/

# Ask questions
cortex ask "What are the key differences between transformers and RNNs?"

# Interactive chat
cortex agent chat
```

## Features

### 🧠 Knowledge Base Agent

```python
from cortex import Agent, Memory

# Create agent with memory
memory = Memory()
agent = Agent(model="llama3", memory=memory)

# Run - agent remembers context
response = agent.run("I'm working on a Python project")
response = agent.run("What am I working on?")  # Remembers!
```

### 📄 Wiki Management

```python
from cortex import KnowledgeBase

kb = KnowledgeBase("./wiki", "./raw")

# Write articles
kb.write_article("concepts/ml-basics.md", "# ML Basics\n\n...")

# Search semantically
results = kb.search("machine learning fundamentals")

# Auto-maintain
kb.update_backlinks()
kb.generate_index()
```

### 🔧 Tools

```python
from cortex import create_coder_agent

coder = create_coder_agent()
response = coder.run("List all Python files in this project")
```

### 🤝 Multi-Agent

```python
from cortex import Orchestrator, AgentSpec

orchestrator = Orchestrator()

agents = [
    AgentSpec("researcher", "researcher", "Research thoroughly."),
    AgentSpec("writer", "writer", "Write clearly."),
]

result = orchestrator.sync_sequential(agents, "What is AI?")
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Cortex                                 │
│                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌─────────┐           │
│  │  Agent  │◄──►│ KnowledgeBase│◄──►│  Brain  │           │
│  │         │    │   (Wiki)     │    │ (LLMs)  │           │
│  └────┬────┘    └──────────────┘    └────┬────┘           │
│       │                                   │                │
│       └──────────┬────────────────────────┘                │
│                  │                                         │
│          ┌──────┴──────┐                                 │
│          │   Ingest    │  PDF, Web, Code, Data           │
│          │  Pipeline   │                                 │
│          └─────────────┘                                 │
│                  │                                         │
│          ┌──────┴──────┐                                 │
│          │  Orchestrator│  Sequential, Parallel           │
│          └─────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

## CLI

```bash
# Agent
cortex agent run "What is Python?"
cortex agent chat

# Knowledge Base
cortex init ./my-wiki
cortex ingest ./papers/
cortex ask "What are transformers?"

# Memory
cortex memory add "Important fact" --type fact
cortex memory search "fact"

# Models
cortex model list
cortex model info llama3

# Configuration
cortex config show
cortex config set model gpt-4
```

## Supported Models

### Free (Local)

- **Ollama**: llama3, llama3.1, llama3.2, codellama, mistral, mixtral, qwen2.5, gemma2

### API (Paid)

- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo
- **Anthropic**: claude-sonnet-4, claude-3.5-sonnet, claude-3.5-haiku
- **OpenRouter**: deepseek-r1, various models
- **Groq**: llama-3.3-70b, mixtral-8x7b

## Documentation

- [Quick Start](docs/QUICKSTART.md) — Get started in 5 minutes
- [API Reference](docs/API.md) — Complete API documentation
- [Implementation Plan](PLAN.md) — Development roadmap

## Tech Stack

- **Python 3.10+** — Core language
- **SQLite** — Memory persistence
- **Sentence-Transformers** — Embeddings (optional)
- **OpenAI/Anthropic SDKs** — Cloud LLM providers
- **Ollama** — Local inference (default)
- **PyYAML** — Configuration persistence

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License — see [LICENSE](LICENSE)

## Links

- [GitHub](https://github.com/dp229/cortex)
- [Documentation](docs/)
- [Plan](PLAN.md)

---

Built with ❤️ for privacy-conscious developers and researchers
