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

## Use Cases

| Industry | Application | Compliance |
|----------|-------------|------------|
| **Medical Devices** | AI-enabled device documentation | IEC 62304 Annex E, FDA AI/ML Action Plan, FDA 21 CFR Part 11 |
| **Railway Systems** | Safety-critical software docs | EN 50128, SIL 0-4 |
| **Aerospace** | DO-178C compliance documentation | FAA/EASA standards |
| **General R&D** | Research wiki with verifiable citations | EU AI Act Articles 11/12, ISO 14971 |

## Key Features

### 🧠 Intelligent Knowledge Management
- **RAG-powered semantic search** with hybrid BM25 + vector retrieval
- **Automatic index rebuild** — file-hash change detection, no restart needed
- **Living wiki** with automatic backlinks and indexing
- **Multi-agent orchestration** for complex research tasks
- **Local-first** — zero data leaves your machine (Ollama default)

### ✅ Deterministic Outputs (No Hallucinations)
- **Safety-class-aware thresholds** — critical requirements demand 98%+ exact match
- **Citation verification** — every claim traced to source documents
- **Proper text normalization** — preserves decimals, versions, acronyms
- **8 citation formats** — markdown, wikilinks, superscript, author-year, etc.
- **Hallucination detection** with measurable false-positive metrics

### 📋 Compliance Automation
- **Structured compliance tags** — `<requirement>`, `<test>`, `<trace>` in Markdown
- **Tarjan SCC cycle detection** — prevents infinite verification loops
- **Automated RTM generation** — bidirectional Requirements Traceability Matrix
- **ReqIF export with XSD validation** — DOORS-compatible XML, fully qualified namespaces
- **Annex E AIDL docs** — IEC 62304 Edition 2 AI Development Lifecycle

### 🔒 Enterprise Security (IEC 62443 / SOC 2)
- **IAM gateway** — RBAC-protected Ollama endpoints
- **Redis token bucket rate limiting** — worker-safe, no bypass vulnerability
- **Immutable audit logs** — Merkle tree + key rotation (90-day), cryptographically signed
- **PII masking** — 5-layer defense-in-depth with injection detection
- **HMAC-SHA256 signatures** — key rotation supported, compromise detection

### 📦 Decision Reproducibility Package (FDA 21 CFR Part 11)
- **Timestamped audit packages** for every compliance-critical query
- **Signed directory structure** — prompt, context, model info, response
- **Integrity chain** — SHA256 hashes + HMAC signatures
- **7-year retention** — FDA Part 11 compliant

### 📦 Tool Qualification Ready
- **Tool Qualification Kit (TQK)** — IEC 62304 Tool Class 2
- **ISO 14971 aligned SOUP documentation** — exact version pinning, measurable failure criteria
- **TOR/TVP/TVR** — pre-built qualification documents with pass/fail metrics

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

# Generate RTM from tagged requirements (with cycle detection)
python -m cortex.rtm --wiki ./wiki --format html --output rtm.html

# Export to ReqIF for enterprise tools (with XSD validation)
python -m cortex.reqif --wiki ./wiki --output requirements.reqif

# Generate AIDL documentation
python -m cortex.market.aidl_generator --device "Cardiac Monitor" --version 2.0

# Generate Decision Reproducibility Package
python -m cortex.drp --query "What is the safety class?" --output /var/log/cortex/drp/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Cortex                                   │
│                                                                     │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────────┐  │
│  │    Agent     │◄──►│  Knowledge Base    │◄──►│     Brain       │  │
│  │              │    │      (Wiki)        │    │    (LLMs)       │  │
│  └──────┬───────┘    └─────────┬──────────┘    └─────────────────┘  │
│         │                      │                                    │
│         │         ┌────────────┴────────────┐                       │
│         │         │   Compliance Engine     │                       │
│         │         ├─────────────────────────┤                       │
│         │         │ • Citation Verification │                       │
│         │         │ • Hybrid Search (BM25)  │                       │
│         │         │ • tiktoken Chunks       │                       │
│         │         │ • RTM Generation        │                       │
│         │         │ • ReqIF Export (XSD)    │                       │
│         │         └─────────────────────────┤                       │
│         │                                   │                       │
│   ┌─────┴─────┐                    ┌────────┴────────┐              │
│   │  Ingest   │                    │   TQK Generator │              │
│   │ Pipeline  │                    │   TOR/TVP/TVR   │              │
│   └───────────┘                    └─────────────────┘              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Security Layer (IEC 62443)               │    │
│  │  IAM Gateway (Redis Rate Limit) • Immutable Audit (Merkle)  │    │
│  │  PII Masking (5-Layer) • DRP (FDA 21 CFR Part 11)           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Security Architecture

### Immutable Audit Logs (Cryptographically Secure)

```
┌─────────────────────────────────────────────────────────┐
│  Rotation Period N                                       │
│                                                          │
│  Manifest (signed):                                      │
│  ├── Merkle Root: SHA256(entries)                       │
│  ├── Entry Count: 1,847                                 │
│  ├── Previous Manifest ID: manifest_N-1                  │
│  ├── Previous Signature: HMAC(manifest_N-1)             │
│  └── Signature: HMAC-SHA256(manifest_content)            │
│                                                          │
│  Entries File (append-only):                             │
│  ├── Entry 1: hash(Entry1), prev=genesis, sig=HMAC    │
│  ├── Entry 2: hash(Entry2), prev=Entry1,  sig=HMAC    │
│  └── Entry N: hash(EntryN), prev=EntryN-1, sig=HMAC    │
│                                                          │
│  Key Management:                                          │
│  └── Key rotated every 90 days (IEC 62443 minimum)       │
└─────────────────────────────────────────────────────────┘
```

### Rate Limiting (Worker-Safe)

```
Multi-Worker FastAPI (3 workers):

BEFORE (vulnerable):
  Worker 1: rate_limit["user"] = [90 requests]  ← Separate store!
  Worker 2: rate_limit["user"] = []             ← BYPASS!
  Worker 3: rate_limit["user"] = []             ← BYPASS!

AFTER (Redis Token Bucket):
  Redis: rate_limit:user → tokens=12.5, refill_rate=1.67/sec
  All workers share same state (atomic Lua script)
```

### Data Minimization (5-Layer Defense)

```
Layer 1: PII Regex (names, emails, SSNs, phones)
Layer 2: Secret Detection (entropy ≥4.5 bits, known prefixes)
Layer 3: Prompt Injection (instruction override, exfil patterns)
Layer 4: Context-Aware Policies (audit/log/debug/user_output)
Layer 5: URL Sanitization (query params stripped)
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
- ✅ **XSD-validated ReqIF XML** for DOORS/Codebeamer
- ✅ **Tarjan SCC cycle detection** prevents infinite loops

### ISO 14971 SOUP with Measurable Criteria

```python
# Example: Ollama failure mode with measurable criteria
ISO14971FailureMode(
    failure_mode_id="FM-OLLAMA-001",
    name="Citation False Positive Rate Excessive",
    severity=Severity.SERIOUS,
    probability=Probability.OCCASIONAL,
    measurable_criteria=[
        MeasurableCriterion(
            criterion_id="CRIT-OLLAMA-001a",
            metric="false_positive_rate",
            threshold=5.0,  # < 5%
            unit="%",
            measurement_method="Run deterministic.py on 1000 queries",
            pass_condition="value < threshold",
        ),
    ],
)
```

### Generated Documents

| Document | Purpose | Standard |
|----------|---------|----------|
| TOR.md | Tool Operational Requirements | IEC 62304 |
| TVP.md | Tool Verification Plan | IEC 62304 |
| TVR.md | Tool Verification Report | IEC 62304 |
| SOUP.md | Third-Party Components | ISO 14971 |
| AIDL.md | AI Development Lifecycle | IEC 62304 Annex E |
| RTM.html | Requirements Traceability Matrix | IEC 62304 |
| requirements.reqif | DOORS Import | ReqIF XSD |

## Decision Reproducibility Package (DRP)

Every compliance-critical query generates a signed audit package:

```
/var/log/cortex/drp/2026/04/07/drp_a1b2c3d4/
├── manifest.json          # Package metadata + file hashes
├── prompt.json           # Exact prompt sent to model
├── context_chunks.json   # Retrieved context with scores
├── model_info.json       # Model version, config
├── response_raw.json      # Raw model response
├── citations.json         # Verified citations
├── metadata.json         # Safety class, exec time
├── signature.json        # HMAC-SHA256 signature
└── .sealed              # Completion marker
```

## Tech Stack

| Component | Version | Compliance Role |
|-----------|---------|----------------|
| Core | Python 3.10+ | Application |
| LLM | Ollama 0.5.4 (exact) | Inference |
| Memory | SQLite | Audit trail |
| Embeddings | Sentence-Transformers 2.7.0 | Semantic search |
| Tokenizer | tiktoken (cl100k_base) | Context management |
| API | FastAPI | Enterprise integration |
| Encryption | cryptography 42.0.7 | Data protection (AES-256) |
| Rate Limiting | Redis + Lua | Distributed rate limit |
| Validation | xmlschema + lxml | ReqIF XSD validation |

## SOUP Components (ISO 14971 Aligned)

| Component | Exact Version | IEC 62304 Class | Risk Level |
|-----------|--------------|-----------------|------------|
| Ollama | 0.5.4 | A | Medium |
| Sentence Transformers | 2.7.0 | A | Low |
| SQLite | 3.x | A | Low |
| FastAPI | 0.100+ | A | Low |
| PyJWT | 2.x | A | Low |
| cryptography | 42.0.7 | B | High (mitigated) |
| pytest | 8.x | A | Low |
| tiktoken | 0.7+ | A | Low |

Each SOUP component includes:
- **Exact version pinning** (no "latest" or ranges)
- **ISO 14971 hazard analysis** with severity/probability
- **Measurable failure criteria** with pass/fail thresholds
- **Mitigation strategies** mapped to failure modes
- **Version history** for change tracking

## 2026 Regulatory Window

The 2026 transition period for **IEC 62304 Edition 2** creates urgent need for:

1. **Annex E AI Development Lifecycle** documentation for AI-enabled devices
2. **FDA AI/ML Action Plan** compliance for US market
3. **EU AI Act** transparency requirements (Articles 11 & 12)
4. **FDA 21 CFR Part 11** electronic records audit trails

**Cortex addresses all four** with automated documentation generation.

## Documentation

- [Quick Start](docs/QUICKSTART.md) — Get started in 5 minutes
- [API Reference](docs/API.md) — Complete API documentation
- [Compliance Guide](docs/COMPLIANCE.md) — IEC 62304/EN 50128 walkthrough
- [TQK Documentation](TQK/) — Tool Qualification Kit templates
- [Security Architecture](docs/SECURITY.md) — IEC 62443 alignment

## License

MIT License — see [LICENSE](LICENSE)

## Links

- [GitHub](https://github.com/dp229/cortex)
- [Documentation](docs/)
- [Tool Qualification Kit](TQK/)

---

*Built for developers and QA engineers who need AI-powered documentation that's also audit-ready.*

## Changelog (Recent Security Fixes)

### v1.1 Security Hardening
- **Immutable Audit Logs**: Merkle tree structure + 90-day key rotation
- **Worker-Safe Rate Limiting**: Redis token bucket, no bypass vulnerability
- **PII Masking**: 5-layer defense-in-depth with injection detection
- **ReqIF XSD Validation**: DOORS-compatible XML with fully qualified namespaces
- **ISO 14971 SOUP**: Exact version pinning + measurable failure criteria

### v1.0 Phase 1-5
- RAG with hybrid BM25 + vector search
- Deterministic citation verification
- RTM generation and ReqIF export
- IAM gateway with RBAC
- Tool Qualification Kit
