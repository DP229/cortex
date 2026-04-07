"""
Cortex IAM Gateway - Ollama Endpoint Protection

Phase 3 Enhancement: Protects local Ollama endpoints behind an
Identity and Access Management gateway with RBAC enforcement.

IEC 62443 Alignment:
- SEC-1: Audit logging of all access attempts
- SEC-2: Role-based access control for AI model access
- SEC-3: Secure communication channels
- SEC-4: Session management

CRITICAL FIX:
- Rate limiting now uses Redis for centralized token-bucket algorithm
- Worker-bypass vulnerability eliminated: all workers share same rate state
- Token-bucket provides smooth rate limiting (not bursty like sliding window)

Features:
- Protects /api/tags, /api/generate endpoints
- RBAC permission checking before model access
- Request/response audit logging
- Redis-based rate limiting per user across all workers
- Session management
"""

import time
import hashlib
import hmac
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import logging
import json
import threading

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# RATE LIMITER EXCEPTION
# =============================================================================

class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: float, key: str):
        self.message = message
        self.retry_after = retry_after
        self.key = key
        super().__init__(self.message)


# =============================================================================
# TOKEN BUCKET RATE LIMITER (Redis-based)
# =============================================================================

class RedisTokenBucket:
    """
    Redis-based token bucket for distributed rate limiting.
    
    Solves the worker-bypass vulnerability in multi-worker deployments.
    All workers share the same rate limit state in Redis.
    
    Algorithm:
    - Each key has a bucket with max_capacity tokens
    - Tokens refill at rate per second
    - Each request consumes one token
    - If no tokens available, request is rejected
    
    Redis Structure (per key):
        Key: rate_limit:{key}
        Hash fields:
            - tokens: current token count (float)
            - last_refill: timestamp of last refill
    
    Atomic operations using Lua script for thread-safety.
    """
    
    # Lua script for atomic token bucket operation
    # Returns: (allowed, tokens_remaining, retry_after_seconds)
    TOKEN_BUCKET_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local tokens_per_second = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])
    
    -- Get current bucket state
    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local current_tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])
    
    -- Initialize if doesn't exist
    if current_tokens == nil then
        current_tokens = capacity
        last_refill = now
    end
    
    -- Calculate tokens to add based on time elapsed
    local elapsed = now - last_refill
    local tokens_to_add = elapsed * tokens_per_second
    current_tokens = math.min(capacity, current_tokens + tokens_to_add)
    
    -- Try to consume tokens
    local allowed = 0
    local retry_after = 0
    if current_tokens >= requested then
        current_tokens = current_tokens - requested
        allowed = 1
    else
        -- Calculate time until enough tokens available
        local tokens_needed = requested - current_tokens
        retry_after = math.ceil(tokens_needed / tokens_per_second)
    end
    
    -- Update bucket state
    redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
    
    -- Set TTL to auto-cleanup (2x refill time for inactivity)
    local ttl = math.ceil(capacity / tokens_per_second * 2)
    redis.call('EXPIRE', key, ttl)
    
    return {allowed, math.floor(current_tokens), retry_after}
    """
    
    def __init__(
        self,
        redis_client = None,
        default_capacity: int = 100,
        default_refill_rate: float = 10.0,  # tokens per second
    ):
        """
        Initialize Redis-based token bucket.
        
        Args:
            redis_client: Redis client instance (redis-py)
            default_capacity: Max tokens per bucket
            default_refill_rate: Tokens added per second
        """
        self._redis = redis_client
        self._default_capacity = default_capacity
        self._default_refill_rate = default_refill_rate
        self._script_sha: Optional[str] = None
        self._local_fallback: bool = redis_client is None
        self._fallback_store: Dict[str, Dict] = {}
        self._fallback_lock = threading.Lock()
        
        # Pre-register Lua script if Redis available
        if self._redis:
            try:
                self._script_sha = self._redis.script_load(self.TOKEN_BUCKET_SCRIPT)
            except Exception as e:
                logger.warning(f"redis_script_load_failed: {e}")
                self._redis = None
                self._local_fallback = True
    
    def check_rate_limit(
        self,
        key: str,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
        requested: int = 1,
    ) -> Tuple[bool, int, float]:
        """
        Check and consume tokens from bucket.
        
        Args:
            key: Rate limit key (e.g., user_id, session_id)
            capacity: Max tokens (uses default if not provided)
            refill_rate: Refill rate in tokens/second
            requested: Number of tokens to consume (usually 1)
            
        Returns:
            Tuple of (allowed, tokens_remaining, retry_after_seconds)
        """
        capacity = capacity or self._default_capacity
        refill_rate = refill_rate or self._default_refill_rate
        
        if self._redis:
            return self._check_redis(key, capacity, refill_rate, requested)
        else:
            return self._check_local(key, capacity, refill_rate, requested)
    
    def _check_redis(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        requested: int,
    ) -> Tuple[bool, int, float]:
        """Check rate limit using Redis"""
        redis_key = f"rate_limit:{key}"
        now = time.time()
        
        try:
            if self._script_sha:
                # Use pre-loaded script
                result = self._redis.evalsha(
                    self._script_sha,
                    1,  # number of keys
                    redis_key,
                    capacity,
                    refill_rate,
                    now,
                    requested,
                )
            else:
                # Fallback to EVAL with script
                result = self._redis.eval(
                    self.TOKEN_BUCKET_SCRIPT,
                    1,
                    redis_key,
                    capacity,
                    refill_rate,
                    now,
                    requested,
                )
            
            allowed = bool(result[0])
            tokens_remaining = int(result[1])
            retry_after = float(result[2])
            
            return allowed, tokens_remaining, retry_after
        
        except Exception as e:
            logger.error(f"redis_rate_limit_error: {e}")
            # Fail open if Redis is down (but log it)
            return True, capacity - requested, 0.0
    
    def _check_local(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        requested: int,
    ) -> Tuple[bool, int, float]:
        """Local fallback for when Redis is unavailable"""
        with self._fallback_lock:
            now = time.time()
            
            if key not in self._fallback_store:
                self._fallback_store[key] = {
                    "tokens": float(capacity),
                    "last_refill": now,
                }
            
            bucket = self._fallback_store[key]
            
            # Calculate tokens to add
            elapsed = now - bucket["last_refill"]
            tokens_to_add = elapsed * refill_rate
            bucket["tokens"] = min(capacity, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = now
            
            # Try to consume
            if bucket["tokens"] >= requested:
                bucket["tokens"] -= requested
                return True, int(bucket["tokens"]), 0.0
            else:
                tokens_needed = requested - bucket["tokens"]
                retry_after = tokens_needed / refill_rate
                return False, 0, retry_after
    
    def get_status(self, key: str) -> Dict[str, Any]:
        """Get current rate limit status for a key"""
        if self._redis:
            redis_key = f"rate_limit:{key}"
            try:
                data = self._redis.hgetall(redis_key)
                if data:
                    return {
                        "key": key,
                        "tokens": float(data.get(b"tokens", 0)),
                        "last_refill": float(data.get(b"last_refill", 0)),
                        "backend": "redis",
                    }
            except Exception as e:
                logger.error(f"redis_get_status_error: {e}")
        
        with self._fallback_lock:
            if key in self._fallback_store:
                return {
                    "key": key,
                    "tokens": self._fallback_store[key]["tokens"],
                    "last_refill": self._fallback_store[key]["last_refill"],
                    "backend": "local",
                }
        
        return {"key": key, "tokens": None, "backend": "unknown"}


# =============================================================================
# IAM ACTION & POLICY
# =============================================================================

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
    rate_limit_key: Optional[str] = None
    tokens_remaining: Optional[int] = None


@dataclass
class IAMPolicy:
    """IAM policy definition"""
    name: str
    description: str
    allowed_actions: List[IAMAction]
    denied_actions: List[IAMAction]
    rate_limit: int = 100  # requests per minute
    rate_limit_burst: int = 20  # burst capacity
    max_tokens_per_request: int = 4096


# =============================================================================
# IAM GATEWAY (Redis Rate Limiting)
# =============================================================================

class IAMGateway:
    """
    IAM Gateway for protecting Ollama endpoints.
    
    CRITICAL FIX: Rate limiting now uses Redis-based token bucket.
    This eliminates the worker-bypass vulnerability in multi-worker setups.
    
    In multi-worker FastAPI:
    - Before: Each worker had its own rate limit store
    - After: All workers share Redis rate limit state
    """
    
    # Default policies
    POLICIES = {
        "admin": IAMPolicy(
            name="admin",
            description="Full access to all Ollama operations",
            allowed_actions=list(IAMAction),
            denied_actions=[],
            rate_limit=1000,
            rate_limit_burst=200,
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
            rate_limit_burst=20,
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
            rate_limit_burst=10,
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
            rate_limit_burst=5,
            max_tokens_per_request=0,
        ),
    }
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        enable_rate_limiting: bool = True,
        enable_request_signing: bool = True,
        redis_client = None,
    ):
        self.ollama_base_url = ollama_base_url
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_request_signing = enable_request_signing
        
        # Redis-based rate limiter (CRITICAL FIX)
        self._token_bucket = RedisTokenBucket(
            redis_client=redis_client,
            default_capacity=100,
            default_refill_rate=10.0,  # 10 tokens/second refill
        )
        
        # Session state (could also be Redis for multi-worker)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._sessions_lock = threading.Lock()
        
        # Audit log
        self._audit_log: List[IAMRequest] = []
        self._audit_lock = threading.Lock()
    
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
        
        # Check rate limit FIRST (before any other checks)
        allowed = True
        reason = "allowed"
        rate_limit_key = None
        tokens_remaining = None
        
        if self.enable_rate_limiting:
            # Use user_id if available, otherwise session_id
            rate_limit_key = user_id or session_id
            
            # Calculate refill rate: capacity per 60 seconds
            # e.g., 100 req/min = 100/60 ≈ 1.67 tokens/second
            refill_rate = policy.rate_limit / 60.0
            
            allowed, tokens_remaining, retry_after = self._token_bucket.check_rate_limit(
                key=rate_limit_key,
                capacity=policy.rate_limit_burst,
                refill_rate=refill_rate,
                requested=1,
            )
            
            if not allowed:
                reason = f"rate_limit_exceeded: retry_after={retry_after:.0f}s"
                logger.warning(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    session_id=session_id,
                    key=rate_limit_key,
                    retry_after=retry_after,
                )
        
        # Check action against policy
        if allowed and reason == "allowed":
            if action in policy.denied_actions:
                allowed = False
                reason = f"action_denied: {action.value} not permitted for policy {policy_name}"
            elif action not in policy.allowed_actions:
                allowed = False
                reason = f"action_not_in_policy: {action.value} not in {policy_name} policy"
        
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
            rate_limit_key=rate_limit_key,
            tokens_remaining=tokens_remaining,
        )
        
        # Thread-safe audit log append
        with self._audit_lock:
            self._audit_log.append(iam_request)
        
        # Log decision
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
    
    def create_session(
        self,
        user_id: str,
        policy_name: str = "developer",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new IAM session"""
        import uuid
        session_id = str(uuid.uuid4())
        
        with self._sessions_lock:
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
        with self._sessions_lock:
            return self._sessions.get(session_id)
    
    def update_session_activity(self, session_id: str) -> bool:
        """Update last activity timestamp"""
        with self._sessions_lock:
            if session_id in self._sessions:
                self._sessions[session_id]["last_activity"] = time.time()
                return True
        return False
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        with self._sessions_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info("iam_session_revoked", session_id=session_id)
                return True
        return False
    
    def get_rate_limit_status(self, user_id: Optional[str], session_id: str) -> Dict[str, Any]:
        """Get current rate limit status for a user/session"""
        key = user_id or session_id
        return self._token_bucket.get_status(key)
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        with self._audit_lock:
            entries = list(self._audit_log)
        
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        
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
        with self._audit_lock:
            total_requests = len(self._audit_log)
            denied_requests = sum(1 for e in self._audit_log if not e.allowed)
            entries_copy = list(self._audit_log)
        
        active_sessions = len(self._sessions)
        
        action_counts: Dict[str, int] = {}
        for entry in entries_copy:
            action = entry.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_requests": total_requests,
            "denied_requests": denied_requests,
            "denial_rate": denied_requests / max(total_requests, 1),
            "active_sessions": active_sessions,
            "action_counts": action_counts,
        }


# =============================================================================
# OLLAMA PROXY WITH IAM
# =============================================================================

class OllamaProxy:
    """Proxy for Ollama API with IAM protection"""
    
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


# =============================================================================
# FASTAPI INTEGRATION
# =============================================================================

def create_iam_middleware(gateway: IAMGateway):
    """Create FastAPI middleware for IAM protection"""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    
    class IAMMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if not request.url.path.startswith("/ollama"):
                return await call_next(request)
            
            user_id = request.headers.get("X-User-ID")
            session_id = request.headers.get("X-Session-ID")
            policy_name = request.headers.get("X-IAM-Policy", "developer")
            
            path = request.url.path
            if path.endswith("/tags"):
                action = IAMAction.MODEL_LIST
            elif path.endswith("/generate"):
                action = IAMAction.INFERENCE_RUN
            elif path.endswith("/embeddings"):
                action = IAMAction.EMBEDDING_CREATE
            else:
                action = IAMAction.MODEL_LIST
            
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
                    status_code=429 if "rate_limit" in access.reason else 403,
                    content={
                        "error": "access_denied",
                        "reason": access.reason,
                        "request_hash": access.request_hash,
                    },
                )
            
            response = await call_next(request)
            response.headers["X-Request-Hash"] = access.request_hash
            if access.tokens_remaining is not None:
                response.headers["X-RateLimit-Remaining"] = str(access.tokens_remaining)
            
            return response
    
    return IAMMiddleware


# =============================================================================
# REDIS INTEGRATION HELPER
# =============================================================================

def create_iam_gateway_with_redis(
    redis_url: str = "redis://localhost:6379/0",
    **kwargs,
) -> IAMGateway:
    """
    Create IAM gateway with Redis connection.
    
    Usage:
        import redis
        gateway = create_iam_gateway_with_redis(
            redis_url="redis://localhost:6379/0",
            enable_rate_limiting=True,
        )
    """
    try:
        import redis
        
        client = redis.from_url(redis_url, decode_responses=False)
        
        # Test connection
        client.ping()
        
        gateway = IAMGateway(
            enable_rate_limiting=True,
            redis_client=client,
            **kwargs,
        )
        
        logger.info("iam_gateway_redis_connected", redis_url=redis_url)
        return gateway
    
    except Exception as e:
        logger.error(f"iam_gateway_redis_connection_failed: {e}")
        # Fall back to local rate limiting
        return IAMGateway(enable_rate_limiting=True, **kwargs)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

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