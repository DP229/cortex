# Cortex User Guide

**Compliance-Ready AI Knowledge Base for Safety-Critical Industries**

A comprehensive guide to building, verifying, and documenting AI-powered knowledge systems with deterministic outputs and full regulatory traceability.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Knowledge Base Setup](#2-knowledge-base-setup)
3. [Ingesting Documents](#3-ingesting-documents)
4. [Querying the Knowledge Base](#4-querying-the-knowledge-base)
5. [Compliance Mode](#5-compliance-mode)
6. [Generating Compliance Artifacts](#6-generating-compliance-artifacts)
7. [Security and Access Control](#7-security-and-access-control)
8. [Audit Trails and Reproducibility](#8-audit-trails-and-reproducibility)
9. [Tool Qualification Kit](#9-tool-qualification-kit)
10. [API Reference](#10-api-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Getting Started

### 1.1 Prerequisites

```bash
# Required
- Python 3.10+
- 8GB RAM minimum (16GB recommended)
- Linux or Windows WSL2

# Optional (for AI features)
- Ollama (local LLM inference)
- Redis (for distributed rate limiting)
```

### 1.2 Installation

```bash
# Clone the repository
git clone https://github.com/dp229/cortex.git
cd cortex

# Install dependencies
pip install -e .

# Install Ollama (for local AI)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

### 1.3 Quick Start

```bash
# Initialize a new wiki
cortex init ./my-wiki

# Ingest documents
cortex ingest ./my-wiki ./docs/

# Ask a question
cortex ask "What are the safety requirements?"

# Start interactive chat
cortex agent chat
```

---

## 2. Knowledge Base Setup

### 2.1 Initializing a Wiki

```bash
# Create a new knowledge base
cortex init ./safety-docs

# This creates the following structure:
# safety-docs/
# ├── cortex.yaml       # Configuration
# ├── wiki/            # Markdown documents
# └── cache/          # Embeddings cache
```

### 2.2 Configuration (cortex.yaml)

```yaml
# Basic settings
wiki_path: ./wiki
embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
  
# LLM settings
llm:
  provider: ollama
  model: llama3
  base_url: http://localhost:11434
  
# Compliance mode
compliance:
  enabled: true
  safety_class_default: B
  iec_62304_mode: true
  
# Security
security:
  rate_limit:
    enabled: true
    redis_url: redis://localhost:6379/0
  audit:
    enabled: true
    retention_days: 2555
```

### 2.3 Directory Structure

```
my-wiki/
├── cortex.yaml           # Configuration
├── wiki/               # Source documents
│   ├── requirements/   # Requirements specs
│   ├── tests/          # Test procedures
│   └── specs/          # Technical specs
├── cache/              # Embeddings cache
└── audit/             # Audit logs (auto-created)
    ├── drp/            # Decision Reproducibility Packages
    ├── manifests/      # Signed manifests
    └── entries/        # Audit entries
```

---

## 3. Ingesting Documents

### 3.1 Basic Ingestion

```bash
# Ingest a directory of markdown files
cortex ingest ./my-wiki ./docs/

# Ingest with compliance tag parsing
cortex ingest --parse-compliance-tags ./my-wiki ./requirements/

# Ingest with specific file types
cortex ingest --extensions .md,.markdown ./my-wiki ./content/
```

### 3.2 Document Format

Cortex supports Markdown with special compliance tags:

```markdown
# Software Requirements Specification

## 1. Introduction

This document specifies requirements for the cardiac monitor software.

---

## Functional Requirements

{{< requirement id="REQ-001" type="functional" priority="shall" safety-class="B" >}}
The system SHALL validate patient data before processing.
{{</requirement>}}

The system validates all incoming patient records against the schema
defined in {{< requirement id="REQ-002" >}}data format spec{{< /requirement >}}.

---

## Testing

{{< test id="TEST-001" type="unit" method="test" verifies="REQ-001" automated="true" >}}
def test_patient_data_validation():
    """Verify malformed data is rejected."""
    with pytest.raises(ValidationError):
        process_patient({"id": None})
{{< /test >}}

---

## Traceability

Trace links connect requirements to tests:

{{< trace from="TEST-001" to="REQ-001" type="verifies" />}}
```

### 3.3 Compliance Tag Reference

| Tag | Attributes | Example |
|-----|-----------|---------|
| `requirement` | id, type, priority, safety-class | `id="REQ-001" type="functional"` |
| `test` | id, type, method, verifies, automated | `id="TEST-001" verifies="REQ-001"` |
| `trace` | from, to, type | `from="TEST-001" to="REQ-001"` |
| `compliance` | standard, clause | `standard="IEC-62304" clause="5.2"` |

### 3.4 Ingestion Output

```
$ cortex ingest ./my-wiki ./docs/

Cortex Ingestion v1.0
======================

Scanning: ./docs/
Found: 47 markdown files

Parsing compliance tags...
  ✓ 23 requirements extracted
  ✓ 18 tests extracted
  ✓ 31 trace links extracted
  
Building embeddings...
  ✓ 47 documents embedded (384-dim)
  
Building BM25 index...
  ✓ Index built with 2,341 unique terms
  ✓ File hash: a3f2b8c1d4e5...

Indexing complete.
  Total documents: 47
  Requirements: 23
  Tests: 18
  Trace links: 31
  Coverage: 87% (20/23 requirements have tests)
```

---

## 4. Querying the Knowledge Base

### 4.1 Basic Query

```bash
# Ask a question
cortex ask "What validation is performed on patient data?"
```

**Output:**
```
🤖 Answer (verified):

The system validates patient data before processing (REQ-001).

**Verification:** ✅ Citation verified in REQ-001.md with 98% similarity

**Testing:** Verified by TEST-001 (automated unit test)
**Traceability:** TEST-001 → REQ-001 (verified)

---

Sources:
1. ✅ [REQ-001.md](wiki/requirements/REQ-001.md) - Patient Data Validation
```

### 4.2 Query with Compliance Context

```bash
# Ask about safety requirements
cortex ask --safety-class critical "What are the Class C safety requirements?"

# Ask with full citation details
cortex ask --show-citations "Explain the authentication flow"
```

### 4.3 Interactive Chat

```bash
# Start interactive session
cortex agent chat

# In chat mode:
# > What is the failure rate for component X?
# > How is REQ-005 verified?
# > Show me the RTM for Class B requirements
# > Generate SOUP documentation
# > exit
```

### 4.4 Query Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--top-k` | Number of context chunks | 5 |
| `--max-tokens` | Maximum response tokens | 4096 |
| `--temperature` | LLM creativity (0-1) | 0.0 |
| `--safety-class` | Compliance threshold | "unknown" |
| `--show-citations` | Display citation details | false |

---

## 5. Compliance Mode

### 5.1 Enabling Compliance Mode

```bash
# Enable with configuration
cortex config set compliance.enabled true
cortex config set compliance.safety_class_default B

# Or via CLI
cortex ask --compliance "What safety measures are required?" \
    --safety-class critical
```

### 5.2 Safety Classes

| Class | Description | Threshold | Example |
|-------|-------------|-----------|---------|
| **critical** | Death or permanent injury | 98% exact | Surgical robot AI |
| **high** | Serious injury | 95% exact | Cardiac monitor |
| **medium** | Non-serious injury | 85% | Infusion pump UI |
| **low** | Inconvenience only | 70% | Patient portal |

### 5.3 Citation Thresholds

Higher safety classes require stricter citation matching:

```
Critical (Class A): 98% exact match required
High (Class B):     95% exact match required
Medium (Class C):   85% fuzzy match allowed
Low (Informational): 70% fuzzy match allowed
```

### 5.4 Hallucination Detection

Cortex detects and flags:
- Unverified numerical claims (specifications without citations)
- Definitive statements without hedging
- Uncited factual claims
- Modified citations (similarity < threshold)

**Example output:**
```
⚠️ Hallucination Flags:
- UNVERIFIED_SPECIFICATION: "failure rate < 0.1%" (no citation nearby)
- UNCITED_CLAIM: "The system uses AES-256 encryption"
```

---

## 6. Generating Compliance Artifacts

### 6.1 Requirements Traceability Matrix (RTM)

```bash
# Generate HTML RTM
cortex rtm --format html --output rtm.html

# Generate CSV RTM
cortex rtm --format csv --output rtm.csv

# Generate JSON RTM
cortex rtm --format json --output rtm.json

# Filter by safety class
cortex rtm --safety-class C --output rtm-class-c.html
```

**RTM Output Example:**

| Req ID | Requirement | Type | Class | Test ID | Method | Status |
|--------|-------------|------|-------|---------|--------|--------|
| REQ-001 | Patient data validation | Functional | B | TEST-001 | Test | ✅ Verified |
| REQ-002 | Heart rate limits | Safety | C | TEST-002 | Analysis | ✅ Verified |
| REQ-003 | Alarm priority | Safety | B | - | - | ❌ Not Covered |

### 6.2 ReqIF Export (DOORS)

```bash
# Export to ReqIF format
cortex reqif --output requirements.reqif

# Validate against XSD before export
cortex reqif --validate --output requirements.reqif

# DOORS import:
# File → Import → Requirements Interchange Format (ReqIF)
```

**ReqIF Validation:**
```
$ cortex reqif --validate --output requirements.reqif

Validating ReqIF XML...
✓ Namespace prefixes qualified
✓ Required elements present
✓ Identifiers validated
✓ CREATION-TIME format valid
✓ XSD schema validation passed

Export: requirements.reqif (23 requirements, 18 tests)
```

### 6.3 Cycle Detection

Cortex prevents circular traceability:

```
$ cortex rtm

ERROR: Circular dependency detected!

Cycle: REQ-001 → TEST-001 → REQ-001
Type: req_test

Remove one trace link from the cycle to proceed.
```

### 6.4 Annex E AIDL Documentation

```bash
# Generate AI Development Lifecycle documentation
cortex aidl --device "Cardiac Monitor" \
            --version "2.0" \
            --output AIDL.md

# This generates:
# - AI planning phase documentation
# - Data requirements
# - Model training records
# - Verification evidence
# - Deployment validation
```

---

## 7. Security and Access Control

### 7.1 IAM Gateway

The IAM Gateway protects Ollama endpoints with RBAC:

```bash
# Create a session with developer policy
curl -X POST http://localhost:8000/iam/session \
  -H "X-User-ID: developer@company.com" \
  -d '{"policy": "developer"}'

# Response:
{
  "session_id": "sess_abc123",
  "policy": "developer",
  "rate_limit": "100 req/min"
}
```

### 7.2 Rate Limiting

Rate limits are enforced across all workers via Redis:

| Policy | Requests/Min | Burst | Actions |
|-------|-------------|-------|---------|
| admin | 1000 | 200 | All |
| developer | 100 | 20 | List, Inference, Embed |
| analyst | 50 | 10 | List, Inference |
| readonly | 20 | 5 | List only |

```bash
# Check rate limit status
curl http://localhost:8000/iam/status \
  -H "X-User-ID: developer@company.com"

# Response:
{
  "tokens_remaining": 87,
  "refill_rate": "1.67/sec",
  "backend": "redis"
}
```

### 7.3 PII Masking

All data is masked before logging:

```python
# Input sanitizer example
from cortex.security.data_minimization import InputSanitizer

sanitizer = InputSanitizer()

# Masked before logging
result = sanitizer.mask_dict(
    {"email": "patient@hospital.com", "ssn": "123-45-6789"},
    context="audit"
)
# {"email": "[EMAIL]", "ssn": "[SSN]"}
```

### 7.4 Request Signing

```bash
# Sign a request
curl -X POST http://localhost:8000/api/generate \
  -H "X-User-ID: developer@company.com" \
  -H "X-Session-ID: sess_abc123" \
  -H "X-Request-Signature: HMAC-SHA256(...)" \
  -d '{"prompt": "What is REQ-001?"}'
```

---

## 8. Audit Trails and Reproducibility

### 8.1 Immutable Audit Logs

All access is logged to immutable, signed audit logs:

```
/var/log/cortex/audit/
├── manifests/
│   ├── MANIFEST_period_2026-04-07_001.json  (signed)
│   └── MANIFEST_period_2026-04-14_002.json  (signed)
├── entries/
│   ├── entries_period_2026-04-07_001.jsonl.gz
│   └── entries_period_2026-04-14_002.jsonl.gz
└── keys/
    ├── key_state.json
    └── key_v1.json
```

### 8.2 Decision Reproducibility Package (DRP)

Every compliance-critical query generates a DRP:

```bash
# Execute with DRP generation
cortex ask --drp "What is the safety class of component X?"

# Output:
{
  "response": "Component X is Class B...",
  "package_id": "drp_a1b2c3d4",
  "package_path": "/var/log/cortex/drp/2026/04/07/drp_a1b2c3d4/",
  "manifest_hash": "abc123..."
}
```

**DRP Package Contents:**
```
drp_a1b2c3d4/
├── manifest.json          # Package metadata + file hashes
├── prompt.json           # Exact prompt sent to model
├── context_chunks.json   # Retrieved context with scores
├── model_info.json       # Model version, config
├── response_raw.json     # Raw model response
├── citations.json        # Verified citations
├── metadata.json         # Safety class, exec time
├── signature.json        # HMAC signature
└── .sealed              # Completion marker
```

### 8.3 Verification

```bash
# Verify audit log integrity
cortex audit verify

# Output:
{
  "verification_time": "2026-04-07T12:00:00Z",
  "periods_verified": 2,
  "entries_verified": 1847,
  "manifests_valid": true,
  "entries_valid": true,
  "chain_valid": true,
  "overall_valid": true
}

# Verify a specific DRP
cortex drp verify drp_a1b2c3d4

# Output:
{
  "package_id": "drp_a1b2c3d4",
  "verified": true,
  "signature_valid": true,
  "files_intact": true
}
```

### 8.4 Retention

| Standard | Retention Period |
|----------|-----------------|
| FDA 21 CFR Part 11 | 7 years |
| IEC 62304 | System lifetime + 2 years |
| ISO 14971 | Device lifetime |

```bash
# Set retention policy
cortex config set audit.retention_days 2555

# Cleanup expired packages
cortex audit cleanup
```

---

## 9. Tool Qualification Kit

### 9.1 Generate TQK

```bash
# Generate all TQK documents
cortex tqk --generate all --output TQK/

# Generate specific documents
cortex tqk --generate tor,tvp,tvr --output TQK/

# Generate SOUP documentation
cortex tqk --generate soup --output TQK/
```

### 9.2 TQK Contents

| Document | Purpose | Standard |
|----------|---------|----------|
| `TOR.md` | Tool Operational Requirements (22 requirements) | IEC 62304 |
| `TVP.md` | Tool Verification Plan (17 test cases) | IEC 62304 |
| `TVR.md` | Tool Verification Report | IEC 62304 |
| `SOUP.md` | Third-Party Component Analysis | ISO 14971 |
| `AIDL.md` | AI Development Lifecycle | IEC 62304 Annex E |

### 9.3 Running Verification

```bash
# Run automated tests
cortex tqk --verify

# Output:
Tool Verification Report
========================

Category: Core Functionality (10 tests)
  ✅ test_embedding_generation - PASSED
  ✅ test_semantic_search - PASSED
  ✅ test_citation_verification - PASSED
  ⚠️  test_context_truncation - WARNING (95% < 99%)
  ✅ test_hybrid_search - PASSED

Category: Compliance (7 tests)
  ✅ test_compliance_tag_parsing - PASSED
  ✅ test_rtm_generation - PASSED
  ✅ test_reqif_export - PASSED
  ✅ test_cycle_detection - PASSED

Overall: 15/17 PASSED, 2 WARNINGS
```

### 9.4 SOUP Documentation

```bash
# Generate SOUP analysis
cortex soup --component Ollama --output SOUP.md

# View risk analysis
cortex soup --list --risks
```

**SOUP Risk Table:**

| Component | Version | Class | Risk | Failure Modes | Status |
|-----------|---------|-------|------|--------------|--------|
| Ollama | 0.5.4 | A | Medium | 2 | Mitigated |
| Sentence Transformers | 2.7.0 | A | Low | 1 | Mitigated |
| cryptography | 42.0.7 | B | High | 1 | Mitigated |

---

## 10. API Reference

### 10.1 Core Endpoints

```bash
# Health check
GET /health

# List models
GET /ollama/api/tags
Headers: X-User-ID, X-Session-ID

# Generate
POST /ollama/api/generate
Headers: X-User-ID, X-Session-ID
Body: {"model": "llama3", "prompt": "..."}

# Embeddings
POST /ollama/api/embeddings
Headers: X-User-ID, X-Session-ID
Body: {"model": "llama3", "prompt": "..."}
```

### 10.2 Compliance Endpoints

```bash
# Query with DRP
POST /api/query
Body: {
  "query": "What are the safety requirements?",
  "safety_class": "critical",
  "include_drp": true
}

# Generate RTM
POST /api/rtm/generate
Body: {"format": "html", "safety_class": "B"}

# Export ReqIF
POST /api/reqif/export
Body: {"validate": true}

# Verify audit integrity
GET /api/audit/verify
```

### 10.3 IAM Endpoints

```bash
# Create session
POST /iam/session
Body: {"user_id": "...", "policy": "developer"}

# Revoke session
DELETE /iam/session/{session_id}

# Get rate limit status
GET /iam/status
Headers: X-User-ID

# Get audit log
GET /iam/audit?limit=100
```

### 10.4 Python SDK

```python
from cortex import Cortex, ComplianceMode

# Initialize
cortex = Cortex(
    wiki_path="./my-wiki",
    compliance=ComplianceMode.IEC62304,
)

# Query
result = cortex.ask(
    "What validation is performed on patient data?",
    safety_class="critical"
)

print(result.response)
print(result.citations)
print(result.drp_package_id)

# In compliance mode
if not result.is_compliant:
    print(f"⚠️ Verification score: {result.verification_score:.0%}")
    for flag in result.hallucination_flags:
        print(f"  - {flag['type']}: {flag['message']}")
```

---

## 11. Troubleshooting

### 11.1 Common Issues

**Q: BM25 index not updating when documents change**

```bash
# Force rebuild
cortex search --rebuild-index

# Check index status
cortex search --status
```

**Q: Ollama connection failed**

```bash
# Check Ollama is running
ollama list

# Pull model if missing
ollama pull llama3

# Check connection
curl http://localhost:11434/api/tags
```

**Q: Rate limit errors**

```bash
# Check Redis is running
redis-cli ping

# Check rate limit status
curl http://localhost:8000/iam/status \
  -H "X-User-ID: your@email.com"
```

**Q: RTM cycle detection error**

```
ERROR: Circular traceability dependency detected:
REQ-001 → TEST-001 → REQ-001

Fix: Remove one trace link from the cycle:
{{< trace from="TEST-001" to="REQ-001" type="verifies" />}}
```

**Q: ReqIF DOORS import fails**

```bash
# Validate before export
cortex reqif --validate --output requirements.reqif

# Check common issues:
# - Namespace prefixes not qualified
# - Empty IDENTIFIER values
# - Invalid CREATION-TIME format
```

### 11.2 Debug Mode

```bash
# Enable verbose logging
cortex --verbose ask "What is REQ-001?"

# Run with debug
CORTEX_LOG_LEVEL=DEBUG cortex ask "..."
```

### 11.3 Health Checks

```bash
# Full system check
cortex doctor

# Output:
Cortex Health Check
====================

✅ Python version: 3.10.12
✅ Ollama: Connected (llama3 loaded)
✅ SQLite: OK (audit.db)
✅ Redis: Connected
✅ Disk space: 45GB available
⚠️  Embeddings cache: Cold (rebuild on first query)
✅ Audit logs: Immutable, signed
✅ Rate limiting: Redis token bucket

System Status: READY
```

### 11.4 Reset

```bash
# Clear embeddings cache
cortex reset --cache

# Clear session state
cortex reset --sessions

# Full reset (keeps wiki)
cortex reset --all

# Re-initialize
rm -rf ./cache && cortex init ./my-wiki
```

---

## Appendix A: Compliance Tag Cheat Sheet

```markdown
<!-- Requirement -->
{{< requirement id="REQ-001" type="functional" priority="shall" safety-class="B" >}}
The system SHALL validate patient data.
{{< /requirement >}}

<!-- Test -->
{{< test id="TEST-001" type="unit" method="test" verifies="REQ-001" automated="true" >}}
def test_validation():
    assert validate({"valid": "data"})
{{< /test >}}

<!-- Trace Link -->
{{< trace from="TEST-001" to="REQ-001" type="verifies" />}}

<!-- Compliance Reference -->
{{< compliance standard="IEC-62304" clause="5.2.3" />}}
```

## Appendix B: Configuration Reference

```yaml
# cortex.yaml full reference

version: "1.1"

wiki_path: ./wiki

embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
  dimension: 384
  batch_size: 32

llm:
  provider: ollama  # ollama | openai | anthropic
  model: llama3
  base_url: http://localhost:11434
  temperature: 0.0
  max_tokens: 4096

search:
  hybrid:
    vector_weight: 0.5
    bm25_weight: 0.5
    rrf_k: 60
  chunking:
    parent_max_tokens: 4000
    chunk_max_tokens: 300
    overlap_tokens: 50

compliance:
  enabled: true
  safety_class_default: B
  iec_62304_mode: true
  strict_citation_threshold: 0.98

security:
  iam:
    enabled: true
    default_policy: developer
  rate_limit:
    enabled: true
    redis_url: redis://localhost:6379/0
  audit:
    enabled: true
    retention_days: 2555
    key_rotation_days: 90
  pii_masking:
    enabled: true
    strict_mode: true

drp:
  enabled: true
  storage_path: /var/log/cortex/drp
  retention_days: 2555
```

---

*For support, open an issue at https://github.com/dp229/cortex/issues*
