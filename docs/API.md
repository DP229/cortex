# Cortex API Reference

Complete REST API documentation for Cortex — EN 50128 Railway Safety Compliance Platform.

Base URL: `http://localhost:8080`

All endpoints require JWT authentication unless noted. Use `POST /auth/login` to obtain a token.

---

## Authentication

### POST /auth/register

Register a new user.

```json
{
  "email": "engineer@example.com",
  "password": "SecurePass123!",
  "full_name": "Safety Engineer",
  "role": "safety_engineer"
}
```

**Roles:** `safety_engineer`, `reviewer`, `auditor`, `admin`

---

### POST /auth/login

```json
{
  "email": "engineer@example.com",
  "password": "SecurePass123!"
}
```

**Response:** Sets httpOnly cookie + returns JWT.

---

### POST /auth/refresh

Refresh JWT token. Reads refresh token from httpOnly cookie.

---

### POST /auth/logout

Clear auth cookie and invalidate session.

---

## Requirements

EN 50128 software requirements management.

### GET /requirements/

List all requirements with optional filters.

**Query params:** `safety_class`, `SIL`, `category`, `status`, `limit`, `offset`

### POST /requirements/

Create a new requirement.

```json
{
  "title": "TCMS shall enforce safe state within 100ms",
  "content": "When a critical fault is detected, the system shall enter a defined safe state within 100ms.",
  "safety_class": "A",
  "SIL": 2,
  "category": "safety",
  "priority": "high"
}
```

### GET /requirements/{uuid}

Get requirement with bidirectional traceability citations.

### PUT /requirements/{uuid}

Update requirement. Locked if requirement is approved.

### DELETE /requirements/{uuid}

Soft-delete requirement (EN 50128: 10-year retention).

### POST /requirements/{uuid}/approve

Approve requirement. Requires `safety_engineer` or `reviewer` role.

### POST /requirements/{uuid}/citations

Add traceability citation to another requirement.

```json
{
  "target_uuid": "<requirement-uuid>",
  "link_type": "verifies",
  "notes": "Implements hazard mitigation H-001"
}
```

**Link types:** `specifies`, `allocated_to`, `implements`, `verifies`, `validates`, `derived_from`, `refines`, `traces_to`, `conflicts_with`, `satisfies`

### POST /requirements/{uuid}/citations/{citation_uuid}/verify

Mark a citation as verified.

### GET /test-records/requirement/{uuid}/verification-status

Get verification status summary for a requirement based on all linked test records:
- **verified** — all linked tests passed
- **failed** — any linked test has failures
- **pending** — no tests or some blocked

---

## SOUPs

EN 50128 §4.2 Software of Unknown Pedigree register.

### GET /soups/

List all SOUPs with optional status filter (`candidate`, `approved`, `rejected`).

### POST /soups/

Register a new candidate SOUP.

```json
{
  "name": "FreeRTOS Kernel",
  "vendor": "Amazon Web Services",
  "version": "11.0.0",
  "checksum": "sha256:abc123...",
  "safety_relevance": "high",
  "documentation_url": "https://freertos.org",
  "notes": "Used in TCMS task scheduler"
}
```

### GET /soups/{uuid}

Get SOUP details and lifecycle history.

### PUT /soups/{uuid}

Update candidate SOUP. Locked after approval.

### DELETE /soups/{uuid}

Soft-delete candidate SOUP. Locked after approval.

### POST /soups/{uuid}/approve

Approve SOUP for use in SIL 2+ development. Locked after approval.

```json
{
  "justification": "Supplier provided IEC 62304 evidence; FreeRTOS is widely deployed in railway applications"
}
```

### POST /soups/{uuid}/reject

Reject candidate SOUP.

```json
{
  "justification": "Insufficient failure mode evidence for SIL 3 use"
}
```

---

## Assets

Railway infrastructure asset register.

### GET /assets/

List assets with optional parent filter for hierarchy.

### POST /assets/

Create an asset.

```json
{
  "name": "ATP Controller Unit A",
  "asset_type": "onboard",
  "safety_class": "A",
  "SIL": 3,
  "parent_uuid": "<parent-asset-uuid>",
  "notes": "Primary ATP controller on train set A"
}
```

### GET /assets/{uuid}

Get asset with hierarchical children.

### PUT /assets/{uuid}

Update asset.

### DELETE /assets/{uuid}

Soft-delete asset (EN 50128: 10-year retention enforced).

---

## Test Records

EN 50128 Table A.3 verification records.

### GET /test-records/

List test records with optional filters (`requirement_uuid`, `test_type`, `status`).

### POST /test-records/

Create a test record linked to a requirement.

```json
{
  "title": "Module Test: Safe State Enforcement",
  "requirement_uuid": "<requirement-uuid>",
  "test_type": "module",
  "test_method": "black_box",
  "passed": 15,
  "failed": 0,
  "blocked": 0,
  "execution_date": "2026-04-28",
  "executor": "safety_engineer@example.com",
  "notes": "All test cases passed; see test protocol C-2026-0428"
}
```

**Test types:** `module`, `integration`, `overall_software`, `system_integration`, `system_validation`

### GET /test-records/{uuid}

Get test record details.

### PUT /test-records/{uuid}

Update test record (e.g., add execution results).

### DELETE /test-records/{uuid}

Delete test record.

### POST /test-records/{uuid}/execute

Record test execution results and update parent requirement's verification status.

```json
{
  "passed": 20,
  "failed": 1,
  "blocked": 0,
  "execution_date": "2026-04-28",
  "executor": "safety_engineer@example.com"
}
```

---

## RTM

Requirements Traceability Matrix.

### GET /rtm/full

Generate full bidirectional RTM covering the complete V-model:
System Requirements → Hazard/Risk Analysis → Safety Requirements → System Architecture → Software Requirements → Software Architecture → Software Design → Module Design → Module Testing → Software Integration → Integration Testing → Overall Software Testing → System Integration → System Validation

### GET /rtm/requirement/{uuid}

Get traceability view for a single requirement (all upstream and downstream links).

### GET /rtm/export/reqif

Export RTM in ReqIF format (DOORS-compatible XSD validation).

---

## T2 Qualification

Automated tool qualification for EN 50128 SIL 2+.

### GET /qualification/evidence/{sil_target}

Retrieve signed T2 evidence artifact for a SIL target (`SIL0`, `SIL1`, `SIL2`, `SIL3`, `SIL4`).

### POST /qualification/run

Trigger T2 qualification run (returns job ID for async tracking).

### GET /qualification/status

Get qualification run status.

---

## Audit

Immutable audit log.

### GET /audit/

List audit events with filters (`action`, `user`, `start_date`, `end_date`, `limit`).

**Note:** Audit logs are append-only and cryptographically signed (Merkle + HMAC-SHA256). They cannot be modified or deleted.

---

## Health

### GET /health

API health check. No authentication required.

### GET /

Root endpoint. Returns basic info.

---

## Models

### Requirement
| Field | Type | Description |
|-------|------|-------------|
| uuid | string | Unique identifier |
| title | string | Requirement title |
| content | string | Full requirement text |
| safety_class | string | A, B, C, or D |
| SIL | integer | 0–4 |
| category | string | functional, safety, performance, interface |
| priority | string | critical, high, medium, low |
| status | string | draft, approved, rejected |
| verification_status | string | verified, failed, pending |
| created_by | string | User email |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |

### SOUP
| Field | Type | Description |
|-------|------|-------------|
| uuid | string | Unique identifier |
| name | string | Software component name |
| vendor | string | Supplier name |
| version | string | Version identifier |
| checksum | string | SHA-256 checksum |
| safety_relevance | string | critical, high, medium, low, none |
| status | string | candidate, approved, rejected |
| justification | string | Approval/rejection reason |
| created_by | string | User email |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |

### Asset
| Field | Type | Description |
|-------|------|-------------|
| uuid | string | Unique identifier |
| name | string | Asset name |
| asset_type | string | onboard, wayside, infrastructure |
| safety_class | string | A, B, C, or D |
| SIL | integer | 0–4 |
| parent_uuid | string | Parent asset UUID for hierarchy |
| created_by | string | User email |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |

### TestRecord
| Field | Type | Description |
|-------|------|-------------|
| uuid | string | Unique identifier |
| title | string | Test record title |
| requirement_uuid | string | Linked requirement UUID |
| test_type | string | module, integration, overall_software, etc. |
| test_method | string | black_box, white_box, grey_box |
| passed | integer | Passed test cases |
| failed | integer | Failed test cases |
| blocked | integer | Blocked test cases |
| verification_status | string | verified, failed, pending |
| execution_date | date | Test execution date |
| executor | string | User email |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |
