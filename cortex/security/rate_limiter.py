"""
Cortex Rate Limiting - Brute Force Protection

EN 50128 Class B compliant rate limiting:
- Prevents brute force attacks on authentication
- Limits API abuse per IEC 62443
- Configurable limits per endpoint
- IP-based and user-based limiting
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests: int
    window_seconds: int
    block_duration_seconds: int = 300  # 5 minutes default block
    

@dataclass
class RequestRecord:
    """Record of requests"""
    timestamps: list = field(default_factory=list)
    blocked_until: Optional[float] = None
    request_count: int = 0


class RateLimiter:
    """
    In-memory rate limiter
    
    For production, consider using Redis-backed rate limiter
    for distributed systems.
    """
    
    # Default rate limits
    DEFAULT_LIMITS = {
        # Authentication endpoints (stricter limits)
        'login': RateLimitConfig(max_requests=5, window_seconds=300, block_duration_seconds=900),  # 5 per 5 min, 15 min block
        'register': RateLimitConfig(max_requests=3, window_seconds=3600, block_duration_seconds=3600),  # 3 per hour, 1 hour block
        'password_change': RateLimitConfig(max_requests=3, window_seconds=3600, block_duration_seconds=1800),  # 3 per hour, 30 min block
        'token_refresh': RateLimitConfig(max_requests=10, window_seconds=60, block_duration_seconds=300),  # 10 per minute, 5 min block
        
        # API endpoints (standard limits)
        'api_read': RateLimitConfig(max_requests=100, window_seconds=60, block_duration_seconds=60),  # 100 per minute
        'api_write': RateLimitConfig(max_requests=50, window_seconds=60, block_duration_seconds=120),  # 50 per minute
        'api_delete': RateLimitConfig(max_requests=10, window_seconds=60, block_duration_seconds=300),  # 10 per minute
        
        # Railway asset/document access (stricter)
        'document_access': RateLimitConfig(max_requests=30, window_seconds=60, block_duration_seconds=300),  # 30 per minute, 5 min block
        'audit_export': RateLimitConfig(max_requests=5, window_seconds=300, block_duration_seconds=900),  # 5 per 5 min, 15 min block
        
        # Administrative endpoints
        'admin': RateLimitConfig(max_requests=20, window_seconds=60, block_duration_seconds=300),  # 20 per minute
    }
    
    def __init__(self):
        # IP-based rate limits
        self._ip_limits: Dict[str, Dict[str, RequestRecord]] = defaultdict(lambda: defaultdict(RequestRecord))
        
        # User-based rate limits
        self._user_limits: Dict[str, Dict[str, RequestRecord]] = defaultdict(lambda: defaultdict(RequestRecord))
        
        # Global limits
        self._global_limits: Dict[str, RequestRecord] = defaultdict(RequestRecord)
    
    def _cleanup_old_requests(self, record: RequestRecord, window_seconds: int) -> None:
        """Remove requests outside the time window"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Remove old timestamps
        record.timestamps = [ts for ts in record.timestamps if ts > cutoff_time]
    
    def _check_blocked(self, record: RequestRecord) -> Tuple[bool, Optional[float]]:
        """
        Check if IP/user is blocked
        
        Returns:
            (is_blocked, remaining_seconds)
        """
        if record.blocked_until and record.blocked_until > time.time():
            remaining = record.blocked_until - time.time()
            return True, remaining
        
        return False, None
    
    def check_rate_limit(
        self,
        endpoint_type: str,
        identifier: str,
        user_id: Optional[str] = None,
        custom_config: Optional[RateLimitConfig] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Check if request is allowed
        
        Args:
            endpoint_type: Type of endpoint (login, api_read, etc.)
            identifier: IP address or unique identifier
            user_id: Optional user ID for user-based limiting
            custom_config: Custom rate limit config
            
        Returns:
            (allowed, retry_after_seconds, error_message)
        """
        config = custom_config or self.DEFAULT_LIMITS.get(endpoint_type, RateLimitConfig(max_requests=100, window_seconds=60))
        
        # Check IP-based limit
        ip_record = self._ip_limits[identifier][endpoint_type]
        
        # Check if blocked
        is_blocked, remaining = self._check_blocked(ip_record)
        if is_blocked:
            logger.warning(
                "rate_limit_blocked",
                identifier=identifier,
                endpoint_type=endpoint_type,
                remaining_seconds=remaining
            )
            return False, int(remaining), f"Rate limit exceeded. Try again in {int(remaining)} seconds."
        
        # Cleanup old requests
        self._cleanup_old_requests(ip_record, config.window_seconds)
        
        # Check IP limit
        if len(ip_record.timestamps) >= config.max_requests:
            # Block the IP
            ip_record.blocked_until = time.time() + config.block_duration_seconds
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                endpoint_type=endpoint_type,
                max_requests=config.max_requests,
                window=config.window_seconds
            )
            return False, config.block_duration_seconds, f"Rate limit exceeded. Blocked for {config.block_duration_seconds} seconds."
        
        # Check user-based limit if user_id provided
        if user_id:
            user_record = self._user_limits[user_id][endpoint_type]
            
            is_blocked, remaining = self._check_blocked(user_record)
            if is_blocked:
                logger.warning(
                    "rate_limit_blocked_user",
                    user_id=user_id,
                    endpoint_type=endpoint_type,
                    remaining_seconds=remaining
                )
                return False, int(remaining), f"Rate limit exceeded. Try again in {int(remaining)} seconds."
            
            self._cleanup_old_requests(user_record, config.window_seconds)
            
            if len(user_record.timestamps) >= config.max_requests:
                user_record.blocked_until = time.time() + config.block_duration_seconds
                logger.warning(
                    "rate_limit_exceeded_user",
                    user_id=user_id,
                    endpoint_type=endpoint_type,
                    max_requests=config.max_requests
                )
                return False, config.block_duration_seconds, f"Rate limit exceeded. Blocked for {config.block_duration_seconds} seconds."
        
        return True, None, None
    
    def record_request(
        self,
        endpoint_type: str,
        identifier: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Record a request for rate limiting
        
        Args:
            endpoint_type: Type of endpoint
            identifier: IP address or unique identifier
            user_id: Optional user ID
        """
        current_time = time.time()
        
        # Record IP-based request
        ip_record = self._ip_limits[identifier][endpoint_type]
        ip_record.timestamps.append(current_time)
        ip_record.request_count += 1
        
        # Record user-based request
        if user_id:
            user_record = self._user_limits[user_id][endpoint_type]
            user_record.timestamps.append(current_time)
            user_record.request_count += 1
    
    def get_remaining_requests(
        self,
        endpoint_type: str,
        identifier: str,
        user_id: Optional[str] = None
    ) -> int:
        """
        Get number of remaining requests allowed
        
        Args:
            endpoint_type: Type of endpoint
            identifier: IP address or identifier
            user_id: Optional user ID
            
        Returns:
            Number of remaining requests
        """
        config = self.DEFAULT_LIMITS.get(endpoint_type, RateLimitConfig(max_requests=100, window_seconds=60))
        
        # Check IP limit
        ip_record = self._ip_limits[identifier][endpoint_type]
        self._cleanup_old_requests(ip_record, config.window_seconds)
        ip_remaining = config.max_requests - len(ip_record.timestamps)
        
        # Check user limit
        if user_id:
            user_record = self._user_limits[user_id][endpoint_type]
            self._cleanup_old_requests(user_record, config.window_seconds)
            user_remaining = config.max_requests - len(user_record.timestamps)
            
            return min(ip_remaining, user_remaining)
        
        return max(0, ip_remaining)
    
    def reset_limits(self, identifier: str, user_id: Optional[str] = None) -> None:
        """
        Reset rate limits for an identifier/user (admin function)
        
        Args:
            identifier: IP address or identifier
            user_id: Optional user ID
        """
        if identifier in self._ip_limits:
            del self._ip_limits[identifier]
        
        if user_id and user_id in self._user_limits:
            del self._user_limits[user_id]
        
        logger.info("rate_limit_reset", identifier=identifier, user_id=user_id)
    
    def get_block_status(self, identifier: str) -> Dict[str, any]:
        """
        Get block status for an identifier
        
        Args:
            identifier: IP address or identifier
            
        Returns:
            Block status information
        """
        blocked_endpoints = {}
        
        if identifier in self._ip_limits:
            for endpoint_type, record in self._ip_limits[identifier].items():
                is_blocked, remaining = self._check_blocked(record)
                if is_blocked:
                    config = self.DEFAULT_LIMITS.get(endpoint_type)
                    blocked_endpoints[endpoint_type] = {
                        "blocked": True,
                        "remaining_seconds": int(remaining),
                        "block_duration": config.block_duration_seconds if config else None
                    }
        
        return {
            "identifier": identifier,
            "blocked_endpoints": blocked_endpoints,
            "is_blocked": len(blocked_endpoints) > 0
        }


# FastAPI dependency for rate limiting
from fastapi import HTTPException, status, Request
from typing import Callable

_rate_limiter_instance = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance


def rate_limit(
    endpoint_type: str,
    identifier_func: Optional[Callable[[Request], str]] = None,
    user_id_func: Optional[Callable[[], Optional[str]]] = None
) -> Callable:
    """
    FastAPI dependency for rate limiting
    
    Args:
        endpoint_type: Type of endpoint
        identifier_func: Function to extract identifier from request
        user_id_func: Function to extract user ID
        
    Returns:
        FastAPI dependency
        
    Usage:
        @router.post("/login")
        async def login(
            request: Request,
            _: None = Depends(rate_limit("login"))
        ):
            # Your login logic
            pass
    """
    async def dependency(request: Request) -> None:
        limiter = get_rate_limiter()
        
        # Get identifier (IP address)
        if identifier_func:
            identifier = identifier_func(request)
        else:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                identifier = forwarded.split(",")[0].strip()
            else:
                identifier = request.client.host if request.client else "unknown"
        
        # Get user ID if available
        user_id = None
        if user_id_func:
            try:
                user_id = user_id_func()
            except:
                pass
        
        # Check rate limit
        allowed, retry_after, error_msg = limiter.check_rate_limit(
            endpoint_type=endpoint_type,
            identifier=identifier,
            user_id=user_id
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg or "Rate limit exceeded",
                headers={"Retry-After": str(retry_after)} if retry_after else None
            )
        
        # Record the request
        limiter.record_request(
            endpoint_type=endpoint_type,
            identifier=identifier,
            user_id=user_id
        )
        
        # Add rate limit headers
        remaining = limiter.get_remaining_requests(endpoint_type, identifier, user_id)
        config = limiter.DEFAULT_LIMITS.get(endpoint_type)
        
        request.state.rate_limit_remaining = remaining
        request.state.rate_limit_limit = config.max_requests if config else None
        
        return None
    
    return dependency


def get_client_identifier(request: Request) -> str:
    """Extract client identifier from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def add_rate_limit_headers(request: Request, response) -> None:
    """Add rate limit headers to response"""
    if hasattr(request.state, 'rate_limit_remaining'):
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
    
    if hasattr(request.state, 'rate_limit_limit'):
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)