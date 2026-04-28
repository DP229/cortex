"""
Cortex FastAPI Application - Railway Safety Compliance

EN 50128 Class B compliant API:
- Authentication via httpOnly cookies
- RBAC permission enforcement
- Encrypted document storage with SHA-256 verification
- Full audit trail for all operations
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from cortex.database import initialize_database
from cortex.config import CortexConfig
from cortex import __version__

# Import routers
from cortex.auth_routes import router as auth_router
from cortex.document_routes import router as document_router
from cortex.audit_routes import router as audit_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown."""
    # Startup
    logger.info("cortex_startup", version=__version__, environment="production")
    try:
        initialize_database()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise
    yield
    # Shutdown
    logger.info("cortex_shutdown")


# === FastAPI App ===

app = FastAPI(
    title="Cortex — Railway Safety Compliance Platform",
    description=(
        "EN 50128 Class B compliant AI knowledge management system "
        "for the railway safety industry."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENABLE_SWAGGER", "false").lower() == "true" else "/docs",
    redoc_url="/redoc" if os.getenv("ENABLE_SWAGGER", "false").lower() == "true" else "/redoc",
)

# === Security Headers ===
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response


# === CORS Configuration ===

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://app.viveka.my").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


# === Global Exception Handler ===

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler.
    
    EN 50128 Class B: Fail-safe — internal errors must never expose
    sensitive system details to clients.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please contact support."},
    )


# === Include Routers ===

app.include_router(auth_router)
app.include_router(document_router)
app.include_router(audit_router)


# === Root Endpoint ===

class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


@app.get("/", response_model=HealthResponse, tags=["Health"])
async def root():
    """Root endpoint — API health check."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        service="cortex-railway-safety",
    )


@app.get("/health", tags=["Health"])
async def health():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "service": "cortex-railway-safety",
        "database": "connected",
    }
