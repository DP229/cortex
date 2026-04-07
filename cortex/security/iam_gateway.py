"""
Cortex IAM Gateway - Ollama Endpoint Protection

Phase 3 Enhancement: Protects local Ollama endpoints behind an
Identity and Access Management gateway with RBAC enforcement.

IEC 62443 Alignment:
- SEC-1: Audit logging of all access attempts
- SEC-2: Role-based access control for AI model access
- SEC-3: Secure communication channels
- SEC-4: Session management

Features:
- Protects /api/tags, /api/generate endpoints
- RBAC permission checking before model access
- Request/response audit logging
- Rate limiting per user
- Session management
"""

import time
import hashlib
import hmac
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import logging
import json

import structlog

logger = structlog.get_logger(__name__)


class IAMAction(str, Enum):
    """Actions that can be performed on protected resources"""
    MODEL_LIST = "model:list"
    MODEL_PULL = "model:pull"
    MODEL_DELETE = "model:delete"
    INFERENCE_RUN = "inference:run"
    INFERENCE_STREAM = "inference:stream"
    EMBEDDING_CREATE = "embedding:create"
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"


@dataclass
class IAMRequest:
    """Processed IAM request"""
    user_id: Optional[str]
    session_id: str
    action: IAMAction
    resource: str
    model: Optional[str]
    request_hash: str
    timestamp: float
    ip_address: Optional[str]
    user_agent: Optional[str]
    allowed: bool
    reason: str


@dataclass
class IAMPolicy:
    """IAM policy definition"""
    name: str
    description: str
    allowed_actions: List[IAMAction]
    denied_actions: List[IAMAction]
    rate_limit: int = 100  # requests per minute
    max_tokens_per_request: int = 4096


class IAMGateway:
    """
    IAM Gateway for protecting Ollama endpoints.
    
    Acts as a middleware layer that intercepts all requests
    to Ollama APIs and enforces RBAC policies.
    """
    
    # Default policies
    POLICIES = {
        "admin": IAMPolicy(
            name="admin",
            description="Full access to all Ollama operations",
            allowed_actions=list(IAMAction),
            denied_actions=[],
            rate_limit=1000,
            max_tokens_per_request=32768,
        ),
        "developer": IAMPolicy(
            name="developer",
            description="Developer access - can run inference and list models",
            allowed_actions=[
                IAMAction.MODEL_LIST,
                IAMAction.INFERENCE_RUN,
                IAMAction.INFERENCE_STREAM,
                IAMAction.EMBEDDING_CREATE,
                IAMAction.CONFIG_READ,
            ],
            denied_actions=[
                IAMAction.MODEL_PULL,
                IAMAction.MODEL_DELETE,
                IAMAction.CONFIG_UPDATE,
            ],
            rate_limit=100,
            max_tokens_per_request=8192,
        ),
        "analyst": IAMPolicy(
            name="analyst",
            description="Read-only access for analysis tasks",
            allowed_actions=[
                IAMAction.MODEL_LIST,
                IAMAction.INFERENCE_RUN,
                IAMAction.EMBEDDING_CREATE,
            ],
            denied_actions=[
                IAMAction.MODEL_PULL,
                IAMAction.MODEL_DELETE,
                IAMAction.CONFIG_READ,
                IAMAction.CONFIG_UPDATE,
            ],
            rate_limit=50,
            max_tokens_per_request=4096,
        ),
        "readonly": IAMPolicy(
            name="readonly",
            description="Minimal access - list models only",
            allowed_actions=[
                IAMAction.MODEL_LIST,
            ],
            denied_actions=[
                IAMAction.MODEL_PULL,
                IAMAction.MODEL_DELETE,
                IAMAction.INFERENCE_RUN,
                IAMAction.INFERENCE_STREAM,
                IAMAction.EMBEDDING_CREATE,
            ],
            rate_limit=20,
            max_tokens_per_request=0,
        ),
    }
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        enable_rate_limiting: bool = True,
        enable_request_signing: bool = True,
    ):
        self.ollama_base_url = ollama_base_url
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_request_signing = enable_request_signing
        
        # Rate limiting state
        self._rate_limit_store: Dict[str, List[float]] = {}
        
        # Session state
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        # Audit log
        self._audit_log: List[IAMRequest] = []
    
    def check_access(
        self,
        user_id: Optional[str],
        session_id: str,
        action: IAMAction,
        resource: str,
        model: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        policy_name: str = "developer",
    ) -> IAMRequest:
        """
        Check if a user has access to perform an action.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            action: Action being attempted
            resource: Resource being accessed
            model: Model being used (if applicable)
            ip_address: Client IP address
            user_agent: Client user agent
            policy_name: Name of policy to apply
        
        Returns:
            IAMRequest with access decision
        """
        timestamp = time.time()
        request_data = f"{user_id}:{session_id}:{action}:{resource}:{timestamp}"
        request_hash = hashlib.sha256(request_data.encode()).hexdigest()[:16]
        
        # Get policy
        policy = self.POLICIES.get(policy_name, self.POLICIES["developer"])
        
        # Check rate limit
        allowed = True
        reason = "allowed"
        
        if self.enable_rate_limiting:
            rate_ok, rate_reason = self._check_rate_limit(
                user_id or session_id, 
                policy.rate_limit
            )
            if not rate_ok:
                allowed = False
                reason = f"rate_limit_exceeded: {rate_reason}"
        
        # Check action against policy
        if allowed:
            if action in policy.denied_actions:
                allowed = False
                reason = f"action_denied: {action.value} not permitted for policy {policy_name}"
            elif action not in policy.allowed_actions:
                allowed = False
                reason = f"action_not_in_policy: {action.value} not in {policy_name} policy"
        
        # Check token limit for inference
        if allowed and action in (IAMAction.INFERENCE_RUN, IAMAction.INFERENCE_STREAM):
            # Token checking would be done at request time
            pass
        
        # Create audit record
        iam_request = IAMRequest(
            user_id=user_id,
            session_id=session_id,
            action=action,
            resource=resource,
            model=model,
            request_hash=request_hash,
            timestamp=timestamp,
            ip_address=ip_address,
            user_agent=user_agent,
            allowed=allowed,
            reason=reason,
        )
        
        # Log the access check
        self._audit_log.append(iam_request)
        
        # Log to structlog
        log = logger.info if allowed else logger.warning
        log(
            "iam_access_check",
            user_id=user_id,
            action=action.value,
            resource=resource,
            model=model,
            allowed=allowed,
            reason=reason,
            request_hash=request_hash,
        )
        
        return iam_request
    
    def _check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, str]:
        """Check if request is within rate limit"""
        now = time.time()
        
        if key not in self._rate_limit_store:
            self._rate_limit_store[key] = []
        
        # Remove old entries
        self._rate_limit_store[key] = [
            t for t in self._rate_limit_store[key]
            if now - t < window_seconds
        ]
        
        # Check limit
        if len(self._rate_limit_store[key]) >= limit:
            return False, f"exceeded {limit} requests per {window_seconds}s"
        
        # Record this request
        self._rate_limit_store[key].append(now)
        
        return True, "ok"
    
    def create_session(
        self,
        user_id: str,
        policy_name: str = "developer",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new IAM session.
        
        Returns session ID.
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        self._sessions[session_id] = {
            "user_id": user_id,
            "policy_name": policy_name,
            "created_at": time.time(),
            "last_activity": time.time(),
            "metadata": metadata or {},
        }
        
        logger.info("iam_session_created", user_id=user_id, session_id=session_id)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        return self._sessions.get(session_id)
    
    def update_session_activity(self, session_id: str) -> bool:
        """Update last activity timestamp"""
        if session_id in self._sessions:
            self._sessions[session_id]["last_activity"] = time.time()
            return True
        return False
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("iam_session_revoked", session_id=session_id)
            return True
        return False
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        entries = self._audit_log
        
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        
        # Convert to dicts and limit
        return [
            {
                "user_id": e.user_id,
                "session_id": e.session_id,
                "action": e.action.value,
                "resource": e.resource,
                "model": e.model,
                "request_hash": e.request_hash,
                "timestamp": e.timestamp,
                "allowed": e.allowed,
                "reason": e.reason,
                "ip_address": e.ip_address,
            }
            for e in entries[-limit:]
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get IAM statistics"""
        total_requests = len(self._audit_log)
        denied_requests = sum(1 for e in self._audit_log if not e.allowed)
        active_sessions = len(self._sessions)
        
        action_counts: Dict[str, int] = {}
        for entry in self._audit_log:
            action = entry.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_requests": total_requests,
            "denied_requests": denied_requests,
            "denial_rate": denied_requests / max(total_requests, 1),
            "active_sessions": active_sessions,
            "action_counts": action_counts,
        }


# === Ollama Proxy with IAM ===

class OllamaProxy:
    """
    Proxy for Ollama API with IAM protection.
    
    Wraps Ollama endpoints and enforces IAM policies.
    """
    
    def __init__(
        self,
        gateway: IAMGateway,
        ollama_base_url: str = "http://localhost:11434",
    ):
        self.gateway = gateway
        self.ollama_base_url = ollama_base_url
    
    def list_models(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        policy_name: str = "developer",
    ) -> Dict[str, Any]:
        """List available models with IAM check"""
        session_id = session_id or "anonymous"
        
        access = self.gateway.check_access(
            user_id=user_id,
            session_id=session_id,
            action=IAMAction.MODEL_LIST,
            resource="/api/tags",
            policy_name=policy_name,
        )
        
        if not access.allowed:
            return {
                "error": "access_denied",
                "reason": access.reason,
                "request_hash": access.request_hash,
            }
        
        # Call actual Ollama API
        try:
            import urllib.request
            
            req = urllib.request.Request(
                f"{self.ollama_base_url}/api/tags",
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result
        except Exception as e:
            return {"error": str(e)}
    
    def generate(
        self,
        model: str,
        prompt: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        policy_name: str = "developer",
        **options,
    ) -> Dict[str, Any]:
        """Run inference with IAM check"""
        session_id = session_id or "anonymous"
        
        access = self.gateway.check_access(
            user_id=user_id,
            session_id=session_id,
            action=IAMAction.INFERENCE_RUN,
            resource="/api/generate",
            model=model,
            policy_name=policy_name,
        )
        
        if not access.allowed:
            return {
                "error": "access_denied",
                "reason": access.reason,
                "request_hash": access.request_hash,
            }
        
        # Call actual Ollama API
        try:
            import urllib.request
            
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            }
            
            req = urllib.request.Request(
                f"{self.ollama_base_url}/api/generate",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                
                # Log successful inference
                self.gateway.update_session_activity(session_id)
                
                return result
        except Exception as e:
            return {"error": str(e)}
    
    def create_embeddings(
        self,
        model: str,
        prompt: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        policy_name: str = "developer",
    ) -> Dict[str, Any]:
        """Create embeddings with IAM check"""
        session_id = session_id or "anonymous"
        
        access = self.gateway.check_access(
            user_id=user_id,
            session_id=session_id,
            action=IAMAction.EMBEDDING_CREATE,
            resource="/api/embeddings",
            model=model,
            policy_name=policy_name,
        )
        
        if not access.allowed:
            return {
                "error": "access_denied",
                "reason": access.reason,
                "request_hash": access.request_hash,
            }
        
        try:
            import urllib.request
            
            data = {
                "model": model,
                "prompt": prompt,
            }
            
            req = urllib.request.Request(
                f"{self.ollama_base_url}/api/embeddings",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}


# === FastAPI Integration ===

def create_iam_middleware(gateway: IAMGateway):
    """
    Create FastAPI middleware for IAM protection.
    
    Usage:
        gateway = IAMGateway()
        middleware = create_iam_middleware(gateway)
        
        app = FastAPI()
        app.add_middleware(middleware)
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    
    class IAMMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Skip non-Ollama paths
            if not request.url.path.startswith("/ollama"):
                return await call_next(request)
            
            # Extract user info from token/session
            user_id = request.headers.get("X-User-ID")
            session_id = request.headers.get("X-Session-ID")
            policy_name = request.headers.get("X-IAM-Policy", "developer")
            
            # Determine action from HTTP method and path
            path = request.url.path
            if path.endswith("/tags"):
                action = IAMAction.MODEL_LIST
            elif path.endswith("/generate"):
                action = IAMAction.INFERENCE_RUN
            elif path.endswith("/embeddings"):
                action = IAMAction.EMBEDDING_CREATE
            else:
                action = IAMAction.MODEL_LIST  # Default
            
            # Check access
            access = gateway.check_access(
                user_id=user_id,
                session_id=session_id or "anonymous",
                action=action,
                resource=path,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
                policy_name=policy_name,
            )
            
            if not access.allowed:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "access_denied",
                        "reason": access.reason,
                        "request_hash": access.request_hash,
                    },
                )
            
            # Add request ID to headers for tracing
            response = await call_next(request)
            response.headers["X-Request-Hash"] = access.request_hash
            
            return response
    
    return IAMMiddleware


# === Global instance ===

_global_gateway: Optional[IAMGateway] = None


def get_iam_gateway() -> IAMGateway:
    """Get global IAM gateway instance"""
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = IAMGateway()
    return _global_gateway


def get_ollama_proxy() -> OllamaProxy:
    """Get Ollama proxy with IAM protection"""
    return OllamaProxy(get_iam_gateway())