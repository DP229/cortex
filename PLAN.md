# Cortex Implementation Plan

**Version:** 2.0  
**Last Updated:** 2026-04-04  
**Project:** Cortex - Local-First AI Knowledge Base Agent

---

## Overview

Cortex is a privacy-first AI agent that ingests technical content, maintains a living wiki, and answers complex engineering questions — all without a single byte leaving your machine.

### Timeline Summary

| Phase | Weeks | Focus | Deliverables |
|-------|-------|-------|--------------|
| **Phase 1: Foundation** | 1-2 | Cleanup, async fixes, config, security | Working local-first SDK |
| **Phase 2: Knowledge Base** | 3-4 | Wiki core, ingest pipeline, tools | Ingest + query workflow |
| **Phase 3: Query & Output** | 5-6 | Query agent, rendering, CLI | Ask questions, get answers |
| **Phase 4: Maintenance** | 7-8 | Health checks, fine-tuning, tests | Production-ready tool |

---

## Phase 1: Foundation (Weeks 1-2)

### Goal: Clean, working codebase with no dead code

### Week 1: Cleanup & Core Fixes

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 1.1 | Remove OpenPool | Delete openloop.py, dashboard, distributed examples | `openloop.py`, `dashboard/` | 2 |
| 1.2 | Fix async/sync | Replace `get_event_loop()` with proper patterns | `agent.py`, `orchestrator.py` | 3 |
| 1.3 | Fix Brain async | Implement real async HTTP for all providers | `brain.py` | 3 |
| 1.4 | Create config.py | Persistent YAML configuration | `config.py` (new) | 2 |
| 1.5 | Security hardening | Permission enforcement, path validation | `tools.py` | 3 |

**Deliverables:**
- No dead code (OpenPool removed)
- Async/sync boundary fixed
- Configuration system with file persistence
- Security: permissions enforced, paths validated, bash sandboxed

### Week 2: Rename & Polish

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 2.1 | Package rename | neuronmesh → cortex everywhere | All files | 2 |
| 2.2 | Update docs | README, API docs, quickstart | `docs/`, `README.md` | 2 |
| 2.3 | Update examples | Remove distributed, add KB examples | `examples/` | 2 |
| 2.4 | Docker cleanup | Simplified compose, updated Dockerfile | `Dockerfile`, `docker-compose.yml` | 1 |
| 2.5 | Dependencies | Update requirements, add pyyaml, nest-asyncio | `requirements.txt`, `setup.py` | 1 |

**Deliverables:**
- Clean cortex package
- Updated documentation
- Working CLI with no broken commands

---

## Phase 2: Knowledge Base Core (Weeks 3-4)

### Goal: Wiki-based knowledge base with ingest pipeline

### Week 3: Knowledge Base Abstraction

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 3.1 | KnowledgeBase class | Wiki CRUD, search, backlinks, index | `knowledgebase.py` (new) | 6 |
| 3.2 | Wiki tools | Read, write, search, index, backlink tools | `wiki_tools.py` (new) | 4 |
| 3.3 | KB agent mode | Agent with wiki tools and system prompt | `agent.py` | 3 |
| 3.4 | Config integration | Wiki paths in CortexConfig | `config.py` | 2 |

**Deliverables:**
- `KnowledgeBase` class with full wiki management
- 6 wiki tools for agent use
- Knowledge base agent mode

### Week 4: Ingest Pipeline

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 4.1 | IngestPipeline | Multi-format ingestion (PDF, web, code, data) | `ingest.py` (new) | 6 |
| 4.2 | Wiki compiler | LLM-powered wiki compilation | `compile_wiki.py` (new) | 4 |
| 4.3 | CLI ingest command | `cortex ingest <path>` | `cli.py` | 2 |
| 4.4 | Tests | Ingest pipeline tests | `tests/` | 3 |

**Deliverables:**
- Ingest PDFs, web articles, code repos, data files
- Auto-generate wiki summaries from raw documents
- CLI ingest command

---

## Phase 3: Query & Output (Weeks 5-6)

### Goal: Ask questions, get comprehensive answers

### Week 5: Query Agent

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 5.1 | QueryAgent | Research wiki, synthesize answers | `query_agent.py` (new) | 4 |
| 5.2 | Output renderer | Marp slides, matplotlib, PDF | `render.py` (new) | 4 |
| 5.3 | CLI ask command | `cortex ask "..."` | `cli.py` | 2 |
| 5.4 | Integration tests | End-to-end query tests | `tests/` | 3 |

**Deliverables:**
- Ask questions against the wiki
- Answers written as markdown files
- Render to slides, charts, PDFs

### Week 6: CLI & UX Polish

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 6.1 | Full CLI | All commands: init, ingest, ask, maintain, render | `cli.py` | 4 |
| 6.2 | Interactive mode | Chat with knowledge base | `cli.py` | 2 |
| 6.3 | Error handling | User-friendly error messages | All files | 2 |
| 6.4 | Logging | Structured logging with config | All files | 2 |

**Deliverables:**
- Complete CLI workflow
- Interactive chat mode
- Good error messages and logging

---

## Phase 4: Maintenance & Production (Weeks 7-8)

### Goal: Self-maintaining wiki, fine-tuning, tests

### Week 7: Wiki Maintenance

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 7.1 | Health checker | Broken links, orphans, stale, duplicates | `wiki_health.py` (new) | 4 |
| 7.2 | Auto-maintenance | CLI maintain command | `cli.py` | 2 |
| 7.3 | Fine-tuning export | Generate datasets from wiki | `finetune.py` (new) | 3 |
| 7.4 | Tests | Health check and fine-tuning tests | `tests/` | 3 |

**Deliverables:**
- Wiki health checks and linting
- Fine-tuning dataset generation
- Auto-maintenance CLI

### Week 8: Production Ready

| # | Task | Description | Files | Hours |
|---|------|-------------|-------|-------|
| 8.1 | Full test suite | 50+ unit + integration tests | `tests/` | 6 |
| 8.2 | API endpoints | Knowledge base REST API | `api.py` | 3 |
| 8.3 | Documentation | Complete docs and examples | `docs/`, `examples/` | 3 |
| 8.4 | Release prep | Version bump, PyPI, changelog | `setup.py` | 2 |

**Deliverables:**
- 50+ tests passing
- Full API coverage
- Complete documentation
- Ready for release

---

## Milestones

| Milestone | Target | Description |
|-----------|--------|-------------|
| **M1: Clean Foundation** | Week 2 | No dead code, async fixed, config system |
| **M2: Knowledge Base** | Week 4 | Wiki CRUD, ingest pipeline, wiki tools |
| **M3: Query & Answer** | Week 6 | Ask questions, get answers, render output |
| **M4: Production** | Week 8 | Tests, docs, release-ready |

---

## Success Metrics

### Week 2 (Foundation)
- [ ] No OpenPool references in codebase
- [ ] `cortex --help` works without errors
- [ ] Config persists across invocations
- [ ] Tool permissions actually enforced

### Week 4 (Knowledge Base)
- [ ] `cortex init ./wiki` creates wiki structure
- [ ] `cortex ingest ./papers/` converts PDFs to wiki
- [ ] Wiki auto-generates index and backlinks
- [ ] Agent can read and write wiki articles

### Week 6 (Query & Output)
- [ ] `cortex ask "..."` returns comprehensive answers
- [ ] Answers cite wiki sources
- [ ] `cortex render` produces slides/PDFs
- [ ] Interactive chat mode works

### Week 8 (Production)
- [ ] 50+ tests passing
- [ ] Wiki health checks find issues
- [ ] Fine-tuning dataset generation works
- [ ] Complete documentation

---

## Resource Requirements

### Development
- **Primary:** Solo developer
- **Time:** 20-30 hours/week
- **Duration:** 8 weeks

### Infrastructure
- **Development:** Local machine with Ollama
- **Storage:** Local filesystem (SQLite for memory)
- **Optional:** Qdrant for large wikis (>1000 articles)

### Tools
- Python 3.10+
- Ollama for local inference
- pytest for testing

---

## File Structure (Target)

```
cortex/
├── cortex/                    # Core SDK
│   ├── __init__.py
│   ├── agent.py                  # Agent class
│   ├── brain.py                  # LLM interface
│   ├── memory.py                 # Memory layer
│   ├── memory_redis.py           # Redis integration
│   ├── memory_qdrant.py          # Qdrant integration
│   ├── config.py                 # Configuration
│   ├── knowledgebase.py          # Wiki knowledge base
│   ├── wiki_tools.py             # Wiki-specific tools
│   ├── ingest.py                 # Data ingestion pipeline
│   ├── compile_wiki.py           # LLM wiki compilation
│   ├── query_agent.py            # Query against wiki
│   ├── render.py                 # Output rendering
│   ├── wiki_health.py            # Wiki health checks
│   ├── finetune.py               # Fine-tuning export
│   ├── orchestrator.py           # Multi-agent
│   ├── tools.py                  # Built-in tools
│   ├── embeddings.py             # Embedding generation
│   ├── metrics.py                # Metrics & monitoring
│   ├── retry.py                  # Retry logic
│   ├── optimizer.py              # Cost optimization
│   └── api.py                    # FastAPI server
├── cortex_cli/               # CLI tool
│   ├── __init__.py
│   └── main.py
├── examples/                     # Example scripts
├── tests/                        # Test suite
├── docs/                         # Documentation
├── setup.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── PLAN.md
├── docker-compose.yml
├── Dockerfile
└── LICENSE
```

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Time constraints | Medium | High | Focus on core features, defer nice-to-haves |
| LLM quality (local models) | Medium | Medium | Support cloud fallback for critical tasks |
| Wiki complexity | High | Medium | Start simple, iterate based on usage |
| Competition | High | Low | Local-first is the differentiator |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-04-04 | Pivot to local-first knowledge base agent |
| 1.0 | 2026-04-03 | Initial plan (distributed platform) |

---

*Plan updated 2026-04-04*
