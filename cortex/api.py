"""
Cortex API - FastAPI Server

Provides a REST API for Cortex:
- Agent management
- Memory operations
- Knowledge base operations
- Metrics & monitoring

Run:
    uvicorn cortex.api:app --reload --port 8080
"""

import time
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from cortex import (
    Memory, Brain,
    Orchestrator, AgentSpec,
    create_agent,
)
from cortex.optimizer import get_optimizer
from cortex.retry import HealthCheck


# === Lifespan ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    # Startup
    app.state.agent = None
    app.state.memory = Memory()
    app.state.brain = Brain()
    app.state.orchestrator = Orchestrator()
    app.state.health = HealthCheck()
    
    # Register health checks
    app.state.health.register("memory", lambda: len(app.state.memory.vector_store.vectors) >= 0)
    app.state.health.register("brain", lambda: app.state.brain is not None)
    
    yield
    
    # Shutdown
    pass


# === App ===

app = FastAPI(
    title="Cortex API",
    description="Local-First AI Knowledge Base Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Models ===

class AgentCreateRequest(BaseModel):
    name: str = "agent"
    model: str = "llama3"
    instructions: str = "You are a helpful AI assistant."
    memory_enabled: bool = True


class AgentRunRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


class MemoryAddRequest(BaseModel):
    content: str
    entry_type: str = "fact"
    importance: float = 0.5


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5


# === Agent Endpoints ===

@app.post("/agent/create")
async def create_agent_endpoint(req: AgentCreateRequest):
    """Create a new agent"""
    agent = create_agent(
        name=req.name,
        model=req.model,
        instructions=req.instructions,
        memory=app.state.memory if req.memory_enabled else None,
    )
    app.state.agent = agent
    
    return {
        "status": "created",
        "name": req.name,
        "model": req.model,
    }


@app.post("/agent/run")
async def run_agent(req: AgentRunRequest):
    """Run agent with prompt"""
    start = time.time()
    
    if not app.state.agent:
        app.state.agent = create_agent(
            model=req.model or "llama3",
            memory=app.state.memory,
        )
    
    response = app.state.agent.run(req.prompt)
    
    return {
        "content": response.content,
        "latency_ms": int((time.time() - start) * 1000),
        "cost": response.cost,
        "turns": len(response.turns),
    }


@app.get("/agent/history")
async def get_agent_history():
    """Get agent conversation history"""
    if not app.state.agent:
        return {"history": []}
    
    messages = app.state.agent.get_history()
    return {
        "history": [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
    }


@app.post("/agent/reset")
async def reset_agent():
    """Reset agent conversation"""
    if app.state.agent:
        app.state.agent.reset()
    return {"status": "reset"}


# === Memory Endpoints ===

@app.get("/memory/stats")
async def get_memory_stats():
    """Get memory statistics"""
    stats = app.state.memory.get_stats()
    return stats


@app.post("/memory/add")
async def add_memory(req: MemoryAddRequest):
    """Add a memory"""
    entry = app.state.memory.add(
        content=req.content,
        entry_type=req.entry_type,
        importance=req.importance,
    )
    
    return {
        "id": entry.id,
        "status": "added",
    }


@app.post("/memory/search")
async def search_memory(req: MemorySearchRequest):
    """Search memory"""
    results = app.state.memory.retrieve(req.query, limit=req.limit)
    
    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "entry_type": r.entry_type,
                "importance": r.importance,
            }
            for r in results
        ],
        "count": len(results),
    }


@app.post("/memory/clear")
async def clear_memory():
    """Clear all memories"""
    count = app.state.memory.get_stats()["total_memories"]
    app.state.memory.clear()
    
    return {"cleared": count}


# === Metrics Endpoints ===

@app.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    metrics = get_metrics()
    return metrics.get_stats()


@app.get("/metrics/models")
async def get_model_metrics():
    """Get per-model metrics"""
    metrics = get_metrics()
    return metrics.get_model_stats()


@app.get("/metrics/optimizer")
async def get_optimizer_stats():
    """Get optimizer statistics"""
    optimizer = get_optimizer()
    return optimizer.get_stats()


# === Health Endpoints ===

@app.get("/health")
async def health_check():
    """Health check"""
    result = app.state.health.check_all()
    return result.to_dict()


@app.get("/health/{check_name}")
async def health_check_specific(check_name: str):
    """Specific health check"""
    is_healthy = app.state.health.check(check_name)
    return {
        "name": check_name,
        "healthy": is_healthy,
    }


# === Model Endpoints ===

@app.get("/models")
async def list_models():
    """List available models"""
    models = app.state.brain.registry.list()
    
    return {
        "models": [
            {
                "name": m.name,
                "provider": m.provider.value,
                "context_length": m.context_length,
                "cost_per_1k": m.cost_per_1k,
            }
            for m in models
        ],
        "count": len(models),
    }


# === Orchestrator Endpoints ===

@app.post("/orchestrate/sequential")
async def orchestrate_sequential(task: str, agent_count: int = 2):
    """Run sequential orchestration"""
    orchestrator = app.state.orchestrator
    
    agents = [
        AgentSpec(f"agent_{i}", f"role_{i}", "You are a helpful assistant.")
        for i in range(agent_count)
    ]
    
    result = await orchestrator.sequential(agents, task)
    
    return {
        "pattern": result.pattern.value,
        "duration_ms": result.duration_ms,
        "outputs": result.outputs,
    }


# === Main ===

def run_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = False):
    """Run the API server"""
    uvicorn.run(
        "cortex.api:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server()
