# Cortex 🧠

**EN 50128-Compliant AI Knowledge Base for Railway Safety-Critical Systems**

Build, verify, and document AI-assisted railway software workflows — with deterministic outputs, full regulatory traceability, and T2 Tool Qualification evidence built in.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![EN 50128](https://img.shields.io/badge/EN%2050128-SIL%200--4-blue)](https://www.cenelec.eu)
[![ISO 14971](https://img.shields.io/badge/ISO%2014971-2019-blue)](https://www.iso.org)

---

## What is Cortex?

Cortex is a **compliance-ready AI knowledge management platform** purpose-built for railway software teams. It combines AI-assisted requirements management, bidirectional traceability, SOUP (Software of Unknown Pedigree) tracking, and automated test record keeping — all with the deterministic, auditable evidence artifacts required for EN 50128 SIL 0–4 certification.

**Primary users:**
- **Lead System Engineers** — define and manage software requirements for onboard and wayside products
- **Safety Engineers** — maintain compliance evidence, approve SOUPs, manage traceability
- **Software Developers** — execute within a regulated V-model workflow with automated RTM generation
- **Quality / Certification Teams** — consume T2 qualification evidence for notified body submissions

---

## Why Cortex for Railway?

Railway software development under EN 50128 is documentation-heavy, traceability-intensive, and requires auditable evidence at every V-model phase. Cortex addresses the hardest parts:

| Challenge | Cortex Solution |
|-----------|-----------------|
| Scattered requirements across documents | Centralized requirements database with EN 50128 metadata (safety class, SIL, priority, category) |
| Bidirectional traceability manually maintained | Auto-generated Requirements Traceability Matrix (RTM) from citation graph |
| SOUP approval workflow not tracked | Dedicated SOUP register with approve/reject lifecycle, locked after approval |
| Test records disconnected from requirements | Test records linked to requirements; auto-computes verification status (verified/failed/pending) |
| AI tool outputs not reproducible | Deterministic DRP (Decision Reproducibility Package) with SHA-256 citation hashes |
| Code changes break compliance without warning | Regression Guard: CI fails on unapproved hash changes to compliance functions |
| T2 Tool Qualification evidence is manual | Automated T2 evidence collection and qualification engine for SIL 2+ |

---

## Business Use Cases

### Onboard Products (Train Control, TCMS, ATP/ATO)

**As a Lead System Engineer**, you define software requirements for a Train Management System (TMS) running on SIL 2 hardware. Cortex lets you:

- Create requirements with EN 50128 attributes (safety_class, SIL, category: functional/safety/performance/interface)
- Trace requirements to software architecture, module design, and unit test records
- Register the RTOS and cryptography library as candidate SOUPs — approve only after supplier evidence review
- Link test execution records (Module Test, Integration Test) to requirements; verification status auto-updates
- Export a complete RTM (Requirements Traceability Matrix) for certification submission

### Wayside Products (Interlocking, RBC, Axle Counters)

Wayside systems often integrate third-party components with limited pedigree evidence. Cortex helps you:

- Maintain an asset register for wayside infrastructure with hierarchical parent/child relationships
- Register all third-party software as SOUPs; classify by safety relevance before use in SIL 2+ systems
- Manage conflicts between requirements (e.g., spare capacity vs. determinism constraints)
- Generate T2 qualification evidence packages automatically — including TOR (Tool Impact Report), TVP (Tool Qualification Plan), and TVR (Tool Validation Report)
- Run deterministic fault injection to verify your fault handling meets EN 50128 §7.4

### Cross-Project Compliance Audits

When a Notified Body audits your software lifecycle data, Cortex provides:

- Immutable audit log (Merkle tree + HMAC-SHA256) for all requirement approvals, SOUP decisions, and test executions
- Behavioral contracts (`@behavioral_contract` decorator) that verify pre/post conditions on every compliance function — with evidence JSON per call
- Deterministic AI citation verification — AI-generated conclusions are reproducible and cite exact paragraph/line references
- CI/CD integration (`ci_qualify.py`) that runs regression guard + T2 qualification on every push and fails the pipeline before compliance regressions reach main

---

## Features

### 📋 Requirements Management
- Full CRUD for EN 50128 software requirements with safety_class (A/B/C/D), SIL (0–4), priority, and category
- Approval workflow with role-gated transitions (`require: requirement:approve`)
- Bidirectional traceability citations: `verifies`, `satisfies`, `conflicts_with`, `refines`, `derived_from`
- Verification tracking: requirement status auto-updates based on linked test records (verified/failed/pending)
- ReqIF export (DOORS-compatible XSD validation) for external requirement management tools

### 🧩 SOUP Management (EN 50128 §4.2)
- Register candidate SOUPs with vendor, version, checksum, and safety relevance classification
- Approve/reject workflow with mandatory justification — approved SOUPs are locked from modification
- Audit trail for every SOUP state transition

### 🏗️ Asset Register
- Railway infrastructure asset CRUD with hierarchical parent/child relationships
- Safety class and SIL level per asset
- Soft-delete with 10-year EN 50128 retention enforcement

### 📝 Test Records (EN 50128 Table A.3)
- Create test records linked to source requirements
- Record execution results (passed/failed/blocked counts)
- Auto-computed verification_status on parent requirement
- GET verification status summary per requirement

### 🔗 Requirements Traceability Matrix (RTM)
- Auto-generated RTM from the citation graph (requirement → design → code → test → verification → validation)
- Full V-model coverage: System Requirements through System Validation
- Exportable for certification submissions

### 🤖 AI with Deterministic DRP
- AI-assisted requirements analysis, test generation hints, and document drafting
- Every AI conclusion includes exact citation to source document + paragraph
- Decision Reproducibility Package (DRP): SHA-256 hash of input + normalized output for reproducibility
- Deterministic text normalization (preserves decimals like 3.14, strips only true noise)

### 🛡️ T2 Tool Qualification Framework
- **Regression Guard**: SHA-256 pinned hashes for all compliance-critical functions; CI fails on mismatch
- **Behavioral Contracts**: `@behavioral_contract` decorator enforces pre/post/invariant conditions with evidence JSON
- **Fault Injector**: Deterministic fault injection for SIL 2+ robustness testing
- **T2 Qualifier**: `QualificationEngine` runs T2 test suites; produces signed evidence artifacts
- **Evidence API**: `GET /qualification/evidence/{sil_target}` returns signed T2 evidence for auditors

### 🔐 Security & Audit
- JWT + RBAC auth with httpOnly cookies; dual-mode (cookie or Bearer token)
- AES-256 encryption for sensitive data at rest
- Immutable Merkle tree audit logs with HMAC-SHA256 signatures
- RBAC on all endpoints; role definitions updated for railway (safety_engineer, reviewer, auditor)

### 🌐 Frontend UI
| Page | Purpose |
|------|---------|
| Dashboard | Overview stats, quick search, system health |
| Requirements | Create, filter, approve, and trace EN 50128 requirements |
| SOUPs | Register and approve/reject candidate software components |
| Assets | Railway infrastructure asset hierarchy |
| RTM | Visual traceability matrix across the V-model |
| Test Records | Link test executions to requirements; view verification status |
| Audit Log | Immutable, sortable audit trail with export |
| Agent Chat | AI assistant for requirements analysis and document drafting |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          Cortex                                   │
│                                                                   │
│  ┌──────────────┐    ┌────────────────────┐    ┌──────────────┐  │
│  │   Frontend   │◄──►│   FastAPI Backend  │◄──►│    Brain      │  │
│  │  (React+TS)  │    │   (REST, port 8080)│    │   (Ollama)   │  │
│  └──────────────┘    └──────────┬─────────┘    └──────────────┘  │
│                                │                                  │
│  ┌─────────────────────────────┴──────────────────────────────┐  │
│  │              EN 50128 Compliance Engine                    │  │
│  │  Requirements  │  SOUP Register  │  RTM  │  Test Records    │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │           T2 Qualification Framework                         │  │
│  │  Regression Guard  │  Contracts  │  Fault Injector           │  │
│  │  T2 Evidence  │  TQK Generator (TOR/TVP/TVR)                │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │              Deterministic DRP                               │  │
│  │  Citation Verification  │  SHA-256 Hash  │  Normalization   │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │              Security Layer (RBAC, AES-256, Audit, Cookies)  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Component | Notes |
|-------|-----------|-------|
| **Frontend** | React 18 + Vite + TypeScript | SPA, dark enterprise theme |
| **Backend** | Python FastAPI | REST API on port 8080 |
| **Database** | SQLite | Audit trail, requirements, assets, SOUPs, test records |
| **Auth** | JWT + httpOnly cookies | 15-min tokens, 7-day refresh, RBAC |
| **Encryption** | AES-256 (cryptography lib) | Data at rest |
| **AI** | Ollama (local LLM) | Zero data leaves your machine |
| **Rate Limiting** | Redis token bucket | Worker-safe (optional) |
| **CI** | GitHub Actions | Regression guard + T2 qualification on every push |

---

## Getting Started

### 1 — Backend

```bash
git clone https://github.com/DP229/cortex.git
cd cortex

# Python virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .

# Install Ollama (local AI — no data leaves your machine)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3

# Start the API server
uvicorn cortex.api:app --reload --port 8080
```

### 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) — login with a registered account.

### 3 — Register a user

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"safety@example.com","password":"SecurePass123!","full_name":"Safety Engineer","role":"safety_engineer"}'
```

**Password requirements:** 12+ chars, uppercase, lowercase, number, special character.

Roles: `safety_engineer`, `reviewer`, `auditor`, `admin`

---

## Project Structure

```
cortex/
├── api.py                          # FastAPI app — all route registration
├── auth_routes.py                  # /auth/* — login, register, refresh
├── audit_routes.py                 # /audit/* — immutable audit logs
├── requirements_routes.py          # /requirements/* — EN 50128 requirements CRUD
├── soup_routes.py                  # /soups/* — SOUP register + approve/reject
├── asset_routes.py                 # /assets/* — infrastructure asset CRUD
├── test_routes.py                  # /test-records/* — EN 50128 Table A.3 records
├── qualification_routes.py         # /qualification/* — T2 evidence endpoints
├── models.py                       # SQLAlchemy models (User, Requirement, SOUP…)
├── audit.py                        # Merkle tree audit signatures
├── rtm.py                          # Requirements Traceability Matrix generator
├── compliance_tags.py              # EN 50128 data quality tag parsing
├── decision_reproducibility.py     # DRP — deterministic AI citation verification
├── deterministic.py                # Text normalization for EN 50128 compliance
├── deterministic_core.py          # SHA-256 compute_hash, ComplianceResult
├── contracts.py                    # @behavioral_contract decorator + evidence
├── fault_injector.py              # Deterministic fault injection for SIL 2+
├── regression_guard.py             # Pinned hash protection for compliance functions
├── rail_taxonomy.py               # EN 50128 / EN 50716 domain model (phases, trace types)
├── rail_validation.py             # EN 50128 compliance validation logic
├── ci_qualify.py                  # CI entry point: qualify + evidence commands
├── tqk/                           # Tool Qualification Kit generators
│   ├── t2_qualifier.py            # QualificationEngine — SIL target T2 tests
│   ├── t2_evidence.py             # T2 evidence collection + signing
│   ├── tor.py                    # Tool Impact Report generator
│   ├── tvp.py                    # Tool Qualification Plan generator
│   └── tvr.py                    # Tool Validation Report generator
frontend/
├── src/
│   ├── App.tsx                    # Router + layout + auth guard
│   ├── contexts/AuthContext.tsx   # JWT auth state
│   ├── utils/api.ts              # Auth-aware fetch wrapper
│   └── pages/
│       ├── Dashboard.tsx
│       ├── RequirementsPage.tsx   # EN 50128 requirements management
│       ├── SoupPage.tsx          # SOUP register + approval workflow
│       ├── AssetsPage.tsx        # Railway infrastructure assets
│       ├── RTMPage.tsx           # Traceability matrix viewer
│       ├── TestRecordsPage.tsx   # EN 50128 Table A.3 test records
│       └── AuditLog.tsx
```

---

## REST API Overview

```
Auth
  POST   /auth/register
  POST   /auth/login
  POST   /auth/refresh
  POST   /auth/logout

Requirements  (EN 50128 software requirements)
  GET    /requirements/
  POST   /requirements/
  GET    /requirements/{uuid}
  PUT    /requirements/{uuid}
  DELETE /requirements/{uuid}
  POST   /requirements/{uuid}/approve
  POST   /requirements/{uuid}/citations
  POST   /requirements/{uuid}/citations/{citation_uuid}/verify
  GET    /test-records/requirement/{uuid}/verification-status

SOUPs  (EN 50128 §4.2)
  GET    /soups/
  POST   /soups/
  GET    /soups/{uuid}
  PUT    /soups/{uuid}
  DELETE /soups/{uuid}
  POST   /soups/{uuid}/approve
  POST   /soups/{uuid}/reject

Assets  (Railway infrastructure)
  GET    /assets/
  POST   /assets/
  GET    /assets/{uuid}
  PUT    /assets/{uuid}
  DELETE /assets/{uuid}

Test Records  (EN 50128 Table A.3)
  GET    /test-records/
  POST   /test-records/
  GET    /test-records/{uuid}
  PUT    /test-records/{uuid}
  DELETE /test-records/{uuid}
  POST   /test-records/{uuid}/execute

RTM  (Requirements Traceability Matrix)
  GET    /rtm/full
  GET    /rtm/requirement/{uuid}
  GET    /rtm/export/reqif

T2 Qualification  (CI/CD entry points)
  GET    /qualification/evidence/{sil_target}
  POST   /qualification/run
  GET    /qualification/status

Audit
  GET    /audit/
```

---

## Compliance Standards

| Standard | Scope | How Cortex Helps |
|----------|-------|-----------------|
| **EN 50128** | Railway software safety SIL 0–4 | Requirements CRUD, SOUP register, test records, RTM, T2 evidence |
| **EN 50716** | Railway software documentation | Traceability matrix, ReqIF export |
| **ISO 14971** | Risk management | Hazard tracking via requirements citations |
| **FDA 21 CFR Part 11** | Electronic records & signatures | Deterministic DRP, immutable audit log |
| **IEC 62443** | Industrial cybersecurity | RBAC, AES-256, audit trail |

---

## CLI Commands

```bash
# T2 qualification (run in CI)
python -m cortex.ci_qualify qualify --sil-target SIL2    # Returns exit code 0/1
python -m cortex.ci_qualify evidence --sil-target SIL2    # Generate signed evidence artifact

# Regression guard
python -m cortex.regression_guard verify   # Verify pinned hashes match
python -m cortex.regression_guard generate  # Regenerate expectations (after intentional change)

# API health check
curl http://localhost:8080/health

# Login and use
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"safety@example.com","password":"SecurePass123!"}'
```

---

## Documentation

- [Quick Start](docs/QUICKSTART.md) — Get running in 5 minutes
- [User Guide](docs/USER_GUIDE.md) — Complete feature documentation
- [API Reference](docs/API.md) — All REST endpoints
- [Deployment Guide](docs/DEPLOYMENT.md) — Production setup

---

## License

MIT — see [LICENSE](LICENSE)
