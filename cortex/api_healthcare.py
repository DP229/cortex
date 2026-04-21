"""
Cortex API - FastAPI Server for Healthcare Compliance Agent

Provides a REST API for Healthcare Compliance Agent:
- Authentication & Authorization (NEW)
- Agent management
- Memory operations
- Knowledge base operations
- Patient management (NEW)
- Compliance reporting (NEW)
- Metrics & monitoring

All endpoints are protected with JWT authentication.

Run:
    uvicorn cortex.api:app --reload --port 8080
"""

import os
import time
from typing import Optional, Dict, Any
from uuid import UUID
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog
import uvicorn

# Import existing modules
from cortex import (
    Memory, Brain,
    Orchestrator, AgentSpec,
    create_agent,
)
from cortex.optimizer import get_optimizer
from cortex.retry import HealthCheck

# Import new security modules
from cortex.database import get_database_manager, initialize_database
from cortex.models import User, AuditLog
from cortex.security.auth import get_current_user, get_current_active_user

# Import authentication routes
from cortex.auth_routes import router as auth_router

# Import audit routes
from cortex.audit_routes import router as audit_router

# Import consent routes
from cortex.consent_routes import router as consent_router

# Import document routes
from cortex.document_routes import router as document_router

# Import audit functions
from cortex.audit import log_audit, AuditAction

# Import security middleware
from cortex.security.middleware import apply_security_middleware

# Setup logging
logger = structlog.get_logger()


# === Lifespan ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    
    # Startup
    logger.info("Starting Healthcare Compliance Agent API")
    
    # Initialize database
    try:
        db = get_database_manager()
        if db.health_check():
            logger.info("Database connection successful")
            db.create_tables()  # Auto-create tables on startup
        else:
            logger.warning("Database health check failed")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    
    # Initialize agent components
    app.state.agent = None
    app.state.memory = Memory()
    app.state.brain = Brain()
    app.state.orchestrator = Orchestrator()
    app.state.health = HealthCheck()
    
    # Register health checks
    app.state.health.register("memory", lambda: len(app.state.memory.vector_store.vectors) >= 0)
    app.state.health.register("brain", lambda: app.state.brain is not None)
    app.state.health.register("database", lambda: get_database_manager().health_check())
    
    logger.info("Healthcare Compliance Agent API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Healthcare Compliance Agent API")


# === App ===

app = FastAPI(
    title="Healthcare Compliance Agent API",
    description="HIPAA-Compliant AI Knowledge Base for Healthcare",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apply security middleware
apply_security_middleware(app)

# Include authentication routes
app.include_router(auth_router)

# Include audit routes
app.include_router(audit_router)

# Include consent routes
app.include_router(consent_router)

# Include document routes
app.include_router(document_router)

# Include medical coding routes
from cortex.coding_routes import router as coding_router
app.include_router(coding_router)


# === Security Middleware ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def audit_log_request(request: Request, user: User, action: str, details: Dict[str, Any] = None, patient_id: UUID = None):
    """Audit log for API requests"""
    try:
        from uuid import UUID as UUIDClass
        from cortex.audit import log_audit, AuditAction
        
        # Convert action string to AuditAction enum
        try:
            audit_action = AuditAction(action)
        except ValueError:
            # If not a valid enum, use AGENT_QUERY as fallback
            audit_action = AuditAction.AGENT_QUERY
        
        log_audit(
            action=audit_action,
            user_id=user.id,
            resource_type="api",
            patient_id=patient_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            details=details or {}
        )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


# === Models ===

class AgentRunRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    patient_id: Optional[str] = None  # If processing PHI


class AgentRunResponse(BaseModel):
    content: str
    latency_ms: int
    cost: float
    turns: int


# === Protected Agent Endpoints ===

@app.post("/agent/run", response_model=AgentRunResponse)
async def run_agent(
    request: Request,
    req: AgentRunRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Run agent with prompt
    
    **Authentication:** Required (JWT token)
    
    **PHI Detection:** If patient_id provided, logs PHI access
    """
    from uuid import UUID
    
    start = time.time()
    
    # Create audit log
    audit_log_request(
        request,
        current_user,
        action="agent_run",
        details={
            "prompt_length": len(req.prompt),
            "model": req.model or "default",
            "patient_id": req.patient_id
        }
    )
    
    # Check if PHI involved
    patient_uuid = None
    if req.patient_id:
        try:
            patient_uuid = UUID(req.patient_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient_id format"
            )
        
        # Verify user has permission to access PHI
        from cortex.models import UserRole
        from cortex.security.rbac import Permission, require_permission
        
        user_permissions = require_permission._get_user_permissions(current_user)
        
        if Permission.PHI_ACCESS not in user_permissions:
            audit_log_request(
                request,
                current_user,
                action="phi_access_denied",
                patient_id=patient_uuid,
                details={"patient_id": req.patient_id, "reason": "permission_denied"}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PHI access requires clinician or admin role"
            )
        
        # Log PHI access
        audit_log_request(
            request,
            current_user,
            action="phi_access",
            patient_id=patient_uuid,
            details={"patient_id": req.patient_id, "action": "agent_run"}
        )
    
    # Run agent
    if not app.state.agent:
        app.state.agent = create_agent(
            model=req.model or "llama3",
            memory=app.state.memory,
        )
    
    try:
        response = app.state.agent.run(req.prompt)
        
        duration_ms = int((time.time() - start) * 1000)
        
        return AgentRunResponse(
            content=response.content,
            latency_ms=duration_ms,
            cost=response.cost,
            turns=len(response.turns)
        )
    except Exception as e:
        logger.error(f"Agent run error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@app.get("/agent/history")
async def get_agent_history(
    current_user: User = Depends(get_current_active_user)
):
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
async def reset_agent(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Reset agent conversation"""
    audit_log_request(request, current_user, action="agent_reset")
    
    if app.state.agent:
        app.state.agent.reset()
    
    return {"message": "Agent reset successfully"}


# === Memory Endpoints ===

@app.get("/memory/stats")
async def get_memory_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get memory statistics"""
    stats = app.state.memory.get_stats()
    return stats


# === Metrics Endpoints ===

@app.get("/metrics")
async def get_metrics():
    """Get system metrics (public endpoint)"""
    metrics = get_optimizer()
    return metrics.get_stats()


@app.get("/metrics/models")
async def get_model_metrics():
    """Get per-model metrics (public endpoint)"""
    metrics = get_optimizer()
    return metrics.get_model_stats()


@app.get("/metrics/optimizer")
async def get_optimizer_stats():
    """Get optimizer statistics (public endpoint)"""
    optimizer = get_optimizer()
    return optimizer.get_stats()


# === Health Endpoints ===

@app.get("/health")
async def health_check():
    """Health check endpoint (public)"""
    result = app.state.health.check_all()
    return result.to_dict()


@app.get("/health/{check_name}")
async def health_check_specific(check_name: str):
    """Specific health check (public)"""
    is_healthy = app.state.health.check(check_name)
    return {
        "name": check_name,
        "healthy": is_healthy
    }


# === Model Endpoints ===

@app.get("/models")
async def list_models():
    """List available models (public)"""
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
        "count": len(models)
    }


# === OrchestratorEndpoints ===

@app.post("/orchestrate/sequential")
async def orchestrate_sequential(
    task: str,
    agent_count: int = 2,
    current_user: User = Depends(get_current_active_user)
):
    """Run sequential orchestration"""
    # TODO: Add audit logging
    
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


# === Root Endpoint ===

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Healthcare Compliance Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# === Run Server ===

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