# Cortex Quick Start Guide

Get up and running with Cortex for railway safety compliance in 5 minutes.

## Installation

```bash
# Clone the repository
git clone https://github.com/DP229/cortex.git
cd cortex

# Install
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

## Prerequisites

Cortex uses Ollama for local AI inference — no data leaves your machine.

### Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Start Ollama server
ollama serve
```

## Quick Examples

### 1. Requirements Management

```python
from cortex.models import Requirement

# Create a SIL 2 software requirement
req = Requirement(
    title="TCMS shall enforce safe state within 100ms",
    content="When a critical fault is detected, the system shall enter a defined safe state within 100ms.",
    safety_class="A",
    SIL=2,
    category="safety",
    priority="high",
)
print(f"Requirement created: {req.uuid}")
```

### 2. SOUP Registration

```python
from cortex.models import SOUP

# Register a third-party RTOS as candidate SOUP
soup = SOUP(
    name="FreeRTOS Kernel",
    vendor="Amazon Web Services",
    version="11.0.0",
    checksum="sha256:abc123...",
    safety_relevance="high",
    status="candidate",
)
print(f"SOUP registered: {soup.uuid}")
```

### 3. Test Record with Verification Linking

```python
from cortex.models import TestRecord

# Create a test record linked to a requirement
test = TestRecord(
    title="Module Test: Safe State Enforcement",
    requirement_uuid="<requirement-uuid>",
    test_type="module",
    passed=15,
    failed=0,
    blocked=0,
)
# Automatically updates requirement verification_status
print(f"Test executed, verification status updated")
```

### 4. RTM Generation

```python
from cortex.rtm import RTMGenerator

rtm = RTMGenerator()
matrix = rtm.generate_full_matrix()
# Returns bidirectional traceability: req → design → code → test → verification → validation
```

### 5. T2 Qualification (CI)

```bash
# Run T2 qualification for SIL 2 target
python -m cortex.ci_qualify qualify --sil-target SIL2

# Generate signed evidence artifact
python -m cortex.ci_qualify evidence --sil-target SIL2
```

### 6. Regression Guard

```bash
# Verify pinned hashes (fails CI on unexpected changes)
python -m cortex.regression_guard verify

# Regenerate expectations after intentional code change
python -m cortex.regression_guard generate
```

## Starting the Application

### Backend

```bash
uvicorn cortex.api:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Register a User

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"engineer@example.com","password":"SecurePass123!","full_name":"Safety Engineer","role":"safety_engineer"}'
```

Available roles: `safety_engineer`, `reviewer`, `auditor`, `admin`

## Next Steps

- Read the [User Guide](USER_GUIDE.md) for full feature documentation
- Review the [API Reference](API.md) for all REST endpoints
- See the [Deployment Guide](DEPLOYMENT.md) for production setup

## Troubleshooting

### "Ollama not available"

```bash
ollama serve
```

### "Model not found"

```bash
ollama pull llama3
```

### Import errors

```bash
pip install -e .
```
