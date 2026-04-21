# Cortex 🧠

**Compliance-Ready AI Knowledge Base for Safety-Critical Industries**

Build, verify, and document AI-powered knowledge systems — with deterministic outputs and full regulatory traceability. From research wikis to IEC 62304-compliant medical device documentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![IEC 62304](https://img.shields.io/badge/IEC%2062304-Tool%20Class%202-green)](https://www.iec.ch)
[![EN 50128](https://img.shields.io/badge/EN%2050128-SIL%200--4-blue)](https://www.cenelec.eu)
[![ISO 14971](https://img.shields.io/badge/ISO%2014971-2019-blue)](https://www.iso.org)
[![FDA 21 CFR Part 11](https://img.shields.io/badge/FDA-21CFR%20Part%2011-purple)](https://www.fda.gov)

## What is Cortex?

Cortex is a **compliance-ready AI knowledge management system** that transforms how safety-critical industries handle documentation. It combines intelligent RAG-powered search with deterministic citation verification, cryptographic audit trails, and automated traceability matrices.

**Two Modes:**
- **Research Mode** — General-purpose AI knowledge base for any domain
- **Compliance Mode** — IEC 62304/EN 50128 compliant with full audit trails

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Cortex                                   │
│                                                                     │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────────┐  │
│  │    Agent    │◄──►│  Knowledge Base     │◄──►│     Brain       │  │
│  │             │    │      (Wiki)        │    │    (LLMs)       │  │
│  └──────┬──────┘    └─────────┬──────────┘    └─────────────────┘  │
│         │                      │                                    │
│         │         ┌───────────┴───────────┐                       │
│         │         │   Compliance Engine   │                       │
│         │         ├────────────────────────┤                       │
│         │         │ • Citation Verification│                       │
│         │         │ • Hybrid Search (BM25) │                       │
│         │         │ • RTM Generation       │                       │
│         │         │ • ReqIF Export (XSD)    │                       │
│         │         └────────────────────────┤                       │
│         │                                   │                       │
│   ┌─────┴──────┐                   ┌───────┴────────┐             │
│   │  Ingest    │                   │  TQK Generator  │             │
│   │ Pipeline  │                   │  TOR/TVP/TVR    │             │
│   └───────────┘                   └─────────────────┘             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   Security Layer (IEC 62443)                │  │
│  │  IAM Gateway (RBAC) • Immutable Audit (Merkle)                │  │
│  │  PII Masking (AES-256) • DRP (FDA 21 CFR Part 11)            │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Component | Notes |
|-------|-----------|-------|
| **Frontend** | React 18 + Vite + TypeScript | SPA with dark enterprise theme |
| **Backend** | Python FastAPI | REST API on port 8080 |
| **LLM** | Ollama (local) | Zero data leaves your machine |
| **Database** | SQLite | Audit trail, patients, consent |
| **Auth** | JWT + RBAC | 15-min tokens, 7-day refresh |
| **Encryption** | AES-256 (cryptography) | PHI at rest + in transit |
| **Rate Limiting** | Redis token bucket | Worker-safe |

## Getting Started

### 1. Backend

```bash
git clone https://github.com/dp229/cortex.git
cd cortex

# Python virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .

# Install Ollama (for local AI inference)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3

# Start the API server
uvicorn cortex.api:app --reload --port 8080
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api/* → localhost:8080)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) — login with a registered account.

### 3. Register a user (first time only)

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Test@12345678!","full_name":"Admin User","role":"admin"}'
```

Password requirements: 12+ chars, uppercase, lowercase, number, special character.

## Project Structure

```
cortex/
├── cortex/
│   ├── api.py              # Main FastAPI app (REST endpoints)
│   ├── api_healthcare.py   # Healthcare API (patients, consent, audit)
│   ├── auth_routes.py      # /auth/* JWT login/register/refresh
│   ├── audit_routes.py     # /audit/* immutable audit logs
│   ├── consent_routes.py   # /consent/* HIPAA consent records
│   ├── models.py           # SQLAlchemy models (User, Patient, Consent, AuditLog…)
│   ├── brain.py            # LLM orchestration
│   ├── knowledgebase.py    # RAG + hybrid BM25/vector search
│   ├── securityauth.py     # JWT auth manager
│   ├── audit.py           # Merkle tree audit signatures
│   └── tqk/              # Tool Qualification Kit generators
├── frontend/
│   ├── src/
│   │   ├── App.tsx        # Router + layout + auth guard
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx   # JWT auth state + provider
│   │   ├── utils/
│   │   │   └── api.ts            # Auth-aware fetch wrapper
│   │   └── pages/
│   │       ├── Dashboard.tsx     # Stats + quick search
│   │       ├── AgentChat.tsx     # LLM chat with model selector
│   │       ├── KnowledgeBase.tsx # RAG search + citations
│   │       ├── MemoryPage.tsx    # Long-term memory store
│   │       ├── Patients.tsx      # PHI patient records
│   │       ├── Consent.tsx       # HIPAA consent management
│   │       ├── AuditLog.tsx      # Immutable audit trail viewer
│   │       └── Metrics.tsx       # Latency + query volume charts
│   └── vite.config.ts     # Vite + /api proxy to :8080
└── docs/
    ├── USER_GUIDE.md      # Full user guide
    ├── API.md             # API reference
    ├── QUICKSTART.md      # 5-minute quick start
    └── DEPLOYMENT.md       # Production deployment guide
```

## Features

### 🧠 Intelligent Knowledge Management
- RAG-powered semantic search (BM25 + vector hybrid)
- Living wiki with automatic backlinks and indexing
- Multi-agent orchestration for complex research tasks
- Local-first — zero data leaves your machine (Ollama default)

### 🔐 Enterprise Security (HIPAA / SOC 2)
- **JWT auth** — admin, clinician, researcher, auditor roles
- **AES-256 PHI encryption** — at rest and in transit
- **Immutable audit logs** — Merkle tree + HMAC-SHA256 signatures
- **RBAC** — role-based access on all endpoints
- **5-layer PII masking** — defense-in-depth

### 📋 Compliance Automation
- Structured compliance tags in Markdown (`{{< requirement >}}`)
- Automated Requirements Traceability Matrix (RTM) generation
- ReqIF export with XSD validation (DOORS-compatible)
- Annex E AIDL docs — IEC 62304 Edition 2 AI Development Lifecycle
- Decision Reproducibility Package (DRP) — FDA 21 CFR Part 11

### 📊 Frontend UI
| Page | Description |
|------|-------------|
| Dashboard | Stats (queries, KB entries, latency, uptime) + quick search |
| Agent Chat | Chat with model selector (llama3/mistral) + memory toggle |
| Knowledge Base | Searchable compliance entries with citations + tag filters |
| Memory | Long-term memory store with importance scoring |
| Patients | PHI patient records (name encrypted, MRN indexed) |
| Consent | HIPAA consent records with grant/revoke lifecycle |
| Audit Log | Sortable audit trail with CSV export |
| Metrics | Latency trend charts + queries/day + model registry |

## Quick Start

```bash
# API health check
curl http://localhost:8080/health

# Login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Test@12345678!"}'

# Search knowledge base
curl -X POST http://localhost:8080/memory/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"query":"IEC 62304 requirements","limit":5}'
```

## Compliance Standards

| Standard | Scope |
|----------|-------|
| **IEC 62304** | Medical device software lifecycle |
| **EN 50128** | Railway software safety (SIL 0–4) |
| **ISO 14971** | Medical device risk management |
| **FDA 21 CFR Part 11** | Electronic records + signatures |
| **HIPAA** | PHI protection + consent tracking |
| **IEC 62443** | Industrial cybersecurity |
| **FDA AI/ML Action Plan** | AI-enabled device documentation |

## Documentation

- [Quick Start](docs/QUICKSTART.md) — Get started in 5 minutes
- [User Guide](docs/USER_GUIDE.md) — Complete user documentation
- [API Reference](docs/API.md) — All REST endpoints
- [Deployment Guide](docs/DEPLOYMENT.md) — Production setup with Cloudflare Tunnel

## License

MIT — see [LICENSE](LICENSE)
