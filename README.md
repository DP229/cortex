# Cortex 🧠

**Compliance-Ready AI Knowledge Base for Safety-Critical Industries**

Build, verify, and document AI-powered knowledge systems — with deterministic outputs and full regulatory traceability. From research wikis to IEC 62304-compliant medical device documentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![IEC 62304](https://img.shields.io/badge/IEC%2062304-Tool%20Class%202-green)](https://www.iec.ch)
[![EN 50128](https://img.shields.io/badge/EN%2050128-SIL%200--4-blue)](https://www.cenelec.eu)

## What is Cortex?

Cortex is a **compliance-ready AI knowledge management system** that transforms how safety-critical industries handle documentation. It combines intelligent RAG-powered search with deterministic citation verification and automated traceability matrices.

**Two Modes:**
- **Research Mode** — General-purpose AI knowledge base for any domain
- **Compliance Mode** — IEC 62304/EN 50128 compliant with full audit trails

## Use Cases

| Industry | Application | Compliance |
|----------|-------------|------------|
| **Medical Devices** | AI-enabled device documentation | IEC 62304 Annex E, FDA AI/ML Action Plan |
| **Railway Systems** | Safety-critical software docs | EN 50128, SIL 0-4 |
| **Aerospace** | DO-178C compliance documentation | FAA/EASA standards |
| **General R&D** | Research wiki with verifiable citations | EU AI Act Articles 11/12 |

## Key Features

### 🧠 Intelligent Knowledge Management
- **RAG-powered semantic search** with hybrid BM25 + vector retrieval
- **Living wiki** with automatic backlinks and indexing
- **Multi-agent orchestration** for complex research tasks
- **Local-first** — zero data leaves your machine (Ollama default)

### ✅ Deterministic Outputs (No Hallucinations)
- **Citation verification** — every claim traced to source documents
- **Hybrid search** — combines vector + lexical (BM25) with Reciprocal Rank Fusion
- **Parent-child chunking** — precise retrieval with full context preservation

### 📋 Compliance Automation
- **Structured compliance tags** — `` `` `` in Markdown
- **Automated RTM generation** — bidirectional Requirements Traceability Matrix
- **ReqIF export** — direct integration with IBM DOORS, PTC Codebeamer
- **Annex E AIDL docs** — IEC 62304 Edition 2 AI Development Lifecycle

### 🔒 Enterprise Security
- **IAM gateway** — RBAC-protected Ollama endpoints
- **Immutable audit logs** — hash-chain with cryptographic signatures
- **PII masking** — automatic redaction before logging
- **IEC 62443 aligned** — for OT security requirements

### 📦 Tool Qualification Ready
- **Tool Qualification Kit (TQK)** — IEC 62304 Tool Class 2
- **SOUP documentation** — 8 third-party components documented
- **TOR/TVP/TVR** — pre-built qualification documents

## Quick Start

### Installation

```bash
git clone https://github.com/dp229/cortex.git
cd cortex
pip install -e .

# Install Ollama (for local inference)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

### Basic Usage

```bash
# Initialize wiki
cortex init ./my-wiki

# Ingest documents
cortex ingest ./papers/
cortex ingest ./docs/

# Ask questions
cortex ask "What are the key requirements for Class B medical devices?"

# Interactive chat
cortex agent chat
```

### Compliance Mode

```bash
# Generate Tool Qualification Kit
python -m cortex.tqk.cli --generate all --output TQK/

# Generate RTM from tagged requirements
python -m cortex.rich --rtm --format html --output rt matrix.html

# Export to ReqIF for enterprise tools
python -m cortex.reqif --wiki ./wiki --output requirements.reqif

# Generate AIDL documentation
python -m cortex.market.aidl_generator --device "Cardiac Monitor" --version 2.0
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Cortex                                     │
│                                                                      │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────────┐  │
│  │    Agent     │◄──►│   Knowledge Base    │◄──►│     Brain       │  │
│  │              │    │      (Wiki)        │    │    (LLMs)       │  │
│  └──────┬───────┘    └─────────┬──────────┘    └─────────────────┘  │
│         │                      │                                      │
│         │         ┌────────────┴────────────┐                        │
│         │         │   Compliance Engine      │                        │
│         │         ├─────────────────────────┤                        │
│         │         │ • Citation Verification│                        │
│         │         │ • Hybrid Search (BM25) │                        │
│         │         │ • Parent-Child Chunks  │                        │
│         │         │ • RTM Generation       │                        │
│         │         │ • ReqIF Export        │                        │
│         │         └─────────────────────────┤                        │
│         │                                    │                        │
│  ┌─────┴─────┐                    ┌────────┴────────┐             │
│  │  Ingest   │                    │   TQK Generator  │             │
│  │ Pipeline   │                    │   TOR/TVP/TVR   │             │
│  └───────────┘                    └─────────────────┘              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Security Layer                             │    │
│  │  IAM Gateway • Immutable Audit • PII Masking • RBAC        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Compliance Documentation

### IEC 62304 Annex E (Medical Device AI)

```markdown
{{< requirement id="REQ-SAFE-001" type="safety" priority="shall" safety-class="C" >}}
The system shall validate patient data before processing.
{{< /requirement >}}

{{< test id="TEST-SAFE-001" type="system" method="test" verifies="REQ-SAFE-001" automated="true" >}}
<input>Malformed patient record</input>
<expected>System rejects input with validation error</expected>
Verify input validation for safety-critical function.
{{< /test >}}

{{< trace from="TEST-SAFE-001" to="REQ-SAFE-001" type="verifies" />}}
```

Cortex automatically generates:
- ✅ Bidirectional RTM from tags
- ✅ Test coverage analysis
- ✅ Safety class breakdown
- ✅ ReqIF XML for DOORS/Codebeamer

### Generated Documents

| Document | Purpose | Standard |
|----------|---------|----------|
| TOR.md | Tool Operational Requirements | IEC 62304 |
| TVP.md | Tool Verification Plan | IEC 62304 |
| TVR.md | Tool Verification Report | IEC 62304 |
| SOUP.md | Third-Party Components | ISO 14971 |
| AIDL.md | AI Development Lifecycle | IEC 62304 Annex E |
| RTM.html | Requirements Traceability Matrix | IEC 62304 |

## Tech Stack

| Component | Technology | Compliance Role |
|-----------|------------|----------------|
| Core | Python 3.10+ | Application |
| LLM | Ollama (local) | Inference |
| Memory | SQLite | Audit trail |
| Embeddings | Sentence-Transformers | Semantic search |
| API | FastAPI | Enterprise integration |
| Encryption | cryptography (AES-256) | Data protection |

## SOUP Components Documented

| Component | Version | Risk Level |
|-----------|---------|------------|
| Ollama | latest | Medium |
| Sentence Transformers | 2.x | Low |
| SQLite | 3.x | Low |
| FastAPI | 0.100+ | Low |
| Llama 3 | 8B/70B | High (mitigated) |

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
- [Compliance Guide](docs/COMPLIANCE.md) — IEC 62304/EN 50128 walkthrough
- [TQK Documentation](TQK/) — Tool Qualification Kit templates

## 2026 Regulatory Window

The 2026 transition period for **IEC 62304 Edition 2** creates urgent need for:

1. **Annex E AI Development Lifecycle** documentation for AI-enabled devices
2. **FDA AI/ML Action Plan** compliance for US market
3. **EU AI Act** transparency requirements (Articles 11 & 12)

**Cortex addresses all three** with automated documentation generation.

## License

MIT License — see [LICENSE](LICENSE)

## Links

- [GitHub](https://github.com/dp229/cortex)
- [Documentation](docs/)
- [Tool Qualification Kit](TQK/)

---

*Built for developers and QA engineers who need AI-powered documentation that's also audit-ready.*