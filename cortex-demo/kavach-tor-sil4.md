# Tool Operational Requirements (TOR)
# Cortex v1.0.0
# Tool Class: T2

**Document generated:** 2026-06-10
**Applicable Standards:** IEC 62304:2006+AMD1:2015, EN 50128:2011, ISO 14971:2019, IEC 62443

---

## Operational Requirements

### 🔴 TOR-OP-001: Purpose Definition

**Priority:** M (MANDATORY)
**Category:** operational

**Description:**
Cortex shall provide a knowledge management system for organizing and retrieving compliance documentation.

**Verification Method:** inspection

**Acceptance Criteria:**
Documentation exists describing purpose and scope

**Status:** not_verified

---

### 🔴 TOR-OP-002: Deterministic Output

**Priority:** M (MANDATORY)
**Category:** operational

**Description:**
Cortex shall generate deterministic, reproducible outputs for the same inputs.

**Verification Method:** test

**Acceptance Criteria:**
Same query with same knowledge base returns identical results >95% of cases

**Status:** not_verified

---

### 🔴 TOR-OP-003: Audit Trail

**Priority:** M (MANDATORY)
**Category:** operational

**Description:**
Cortex shall maintain a complete audit trail of all operations for regulatory review.

**Verification Method:** inspection

**Acceptance Criteria:**
Audit log captures user, action, timestamp, and outcome

**Status:** not_verified

---

### 🔴 TOR-OP-004: Data Integrity

**Priority:** M (MANDATORY)
**Category:** operational

**Description:**
Cortex shall preserve the integrity of ingested documents without unauthorized modification.

**Verification Method:** analysis

**Acceptance Criteria:**
Document hash verification confirms no unauthorized changes

**Status:** not_verified

---

## Functional Requirements

### 🔴 TOR-FN-001: Document Ingestion

**Priority:** M (MANDATORY)
**Category:** functional

**Description:**
Cortex shall ingest Markdown documents and maintain their structure.

**Verification Method:** test

**Acceptance Criteria:**
Markdown with headings, lists, and code blocks is preserved

**Status:** not_verified

---

### 🔴 TOR-FN-002: Semantic Search

**Priority:** M (MANDATORY)
**Category:** functional

**Description:**
Cortex shall provide semantic search across indexed documents.

**Verification Method:** test

**Acceptance Criteria:**
Vector similarity search returns relevant documents

**Status:** not_verified

---

### 🔴 TOR-FN-003: Citation Verification

**Priority:** M (MANDATORY)
**Category:** functional

**Description:**
Cortex shall verify that generated citations match source documents.

**Verification Method:** test

**Acceptance Criteria:**
Deterministic quoting returns match/nomatch with source evidence

**Status:** not_verified

---

### 🔴 TOR-FN-004: Traceability Matrix Generation

**Priority:** M (MANDATORY)
**Category:** functional

**Description:**
Cortex shall generate bidirectional traceability matrices from tagged requirements.

**Verification Method:** test

**Acceptance Criteria:**
RTM links requirements to tests bidirectionally

**Status:** not_verified

---

### 🟡 TOR-FN-005: ReqIF Export

**Priority:** I (IMPORTANT)
**Category:** functional

**Description:**
Cortex shall export requirements in ReqIF format for enterprise tools.

**Verification Method:** test

**Acceptance Criteria:**
Generated ReqIF file passes schema validation

**Status:** not_verified

---

### 🟡 TOR-FN-006: Hybrid Search

**Priority:** I (IMPORTANT)
**Category:** functional

**Description:**
Cortex shall combine vector and BM25 search with configurable weighting.

**Verification Method:** test

**Acceptance Criteria:**
Hybrid search provides improved recall over single-method search

**Status:** not_verified

---

### 🟡 TOR-FN-007: Chunking with Parent Context

**Priority:** I (IMPORTANT)
**Category:** functional

**Description:**
Cortex shall index small chunks for retrieval while preserving parent document context.

**Verification Method:** analysis

**Acceptance Criteria:**
Retrieved chunks include parent document for full context

**Status:** not_verified

---

### 🔴 TOR-FN-008: Compliance Tag Parsing

**Priority:** M (MANDATORY)
**Category:** functional

**Description:**
Cortex shall parse structured compliance tags in Markdown documents.

**Verification Method:** test

**Acceptance Criteria:**
<requirement>, <test>, <trace> tags are correctly parsed

**Status:** not_verified

---

## Performance Requirements

### 🟡 TOR-PF-001: Search Latency

**Priority:** I (IMPORTANT)
**Category:** performance

**Description:**
Cortex shall respond to search queries within 5 seconds for knowledge bases up to 10,000 documents.

**Verification Method:** test

**Acceptance Criteria:**
95th percentile response time < 5 seconds

**Status:** not_verified

---

### 🟢 TOR-PF-002: Indexing Throughput

**Priority:** D (DESIRABLE)
**Category:** performance

**Description:**
Cortex shall index documents at a rate of at least 100 documents per minute.

**Verification Method:** test

**Acceptance Criteria:**
Indexing rate > 100 docs/min for typical Markdown files

**Status:** not_verified

---

### 🟡 TOR-PF-003: Memory Efficiency

**Priority:** I (IMPORTANT)
**Category:** performance

**Description:**
Cortex shall operate within 8GB RAM for knowledge bases up to 50,000 documents.

**Verification Method:** test

**Acceptance Criteria:**
Memory usage < 8GB for specified document count

**Status:** not_verified

---

## Interface Requirements

### 🔴 TOR-IF-001: Local Ollama Integration

**Priority:** M (MANDATORY)
**Category:** interface

**Description:**
Cortex shall interface with local Ollama instances for LLM inference.

**Verification Method:** test

**Acceptance Criteria:**
Cortex can call Ollama /api/generate and /api/tags endpoints

**Status:** not_verified

---

### 🔴 TOR-IF-002: File System Access

**Priority:** M (MANDATORY)
**Category:** interface

**Description:**
Cortex shall read/write documents to local file system.

**Verification Method:** inspection

**Acceptance Criteria:**
File system operations work for configured wiki paths

**Status:** not_verified

---

### 🟡 TOR-IF-003: API Export

**Priority:** I (IMPORTANT)
**Category:** interface

**Description:**
Cortex shall export RTM data via API endpoints.

**Verification Method:** test

**Acceptance Criteria:**
RTM generation endpoint returns HTML/CSV/JSON

**Status:** not_verified

---

## Environmental Requirements

### 🔴 TOR-EN-001: Python Environment

**Priority:** M (MANDATORY)
**Category:** environmental

**Description:**
Cortex shall run on Python 3.10+ with pip package management.

**Verification Method:** inspection

**Acceptance Criteria:**
Installation succeeds on clean Python 3.10+ environment

**Status:** not_verified

---

### 🔴 TOR-EN-002: Operating System Compatibility

**Priority:** M (MANDATORY)
**Category:** environmental

**Description:**
Cortex shall run on Linux and Windows WSL2 environments.

**Verification Method:** test

**Acceptance Criteria:**
Core functions work on Ubuntu 22.04 and Windows 11 WSL2

**Status:** not_verified

---

### 🟡 TOR-EN-003: Hardware Requirements

**Priority:** I (IMPORTANT)
**Category:** environmental

**Description:**
Cortex shall operate on hardware with minimum 16GB RAM and multi-core CPU.

**Verification Method:** inspection

**Acceptance Criteria:**
Documentation specifies minimum hardware requirements

**Status:** not_verified

---

## Quality Requirements

### 🟡 TOR-QA-001: Code Documentation

**Priority:** I (IMPORTANT)
**Category:** quality

**Description:**
Cortex shall have comprehensive code documentation.

**Verification Method:** inspection

**Acceptance Criteria:**
Docstrings exist for all public APIs

**Status:** not_verified

---

### 🔴 TOR-QA-002: Version Control

**Priority:** M (MANDATORY)
**Category:** quality

**Description:**
Cortex source code shall be maintained in version control.

**Verification Method:** inspection

**Acceptance Criteria:**
Git repository exists with commit history

**Status:** not_verified

---

### 🟡 TOR-QA-003: Unit Test Coverage

**Priority:** I (IMPORTANT)
**Category:** quality

**Description:**
Cortex shall have unit tests covering core functionality.

**Verification Method:** test

**Acceptance Criteria:**
Unit tests pass with >70% code coverage on core modules

**Status:** not_verified

---

### 🔴 TOR-QA-004: SOUP Documentation

**Priority:** M (MANDATORY)
**Category:** quality

**Description:**
Cortex shall document all third-party components (SOUP).

**Verification Method:** inspection

**Acceptance Criteria:**
SOUP manifest exists listing all third-party dependencies

**Status:** not_verified

---
