"""
Cortex Security Middleware

FastAPI middleware for security:
- Rate limiting
- Security headers
- Input validation
- Request logging
- CORS configuration
"""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import structlog

from cortex.security.rate_limiter import get_rate_limiter, get_client_identifier
from cortex.security.validation import SecurityValidator, SecurityHeaders

logger = structlog.get_logger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for HTTP requests
    
    Adds:
    - Security headers
    - Rate limiting headers
    - Request logging
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware"""
        start_time = time.time()
        
        # Get client identifier
        client_ip = get_client_identifier(request)
        
        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", "unknown")
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                client_ip=client_ip,
                error=str(e)
            )
            raise
        
        # Add security headers
        security_headers = SecurityHeaders.get_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add rate limit headers if available
        if hasattr(request.state, 'rate_limit_remaining'):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        
        if hasattr(request.state, 'rate_limit_limit'):
            response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
        
        # Add timing header
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        
        # Log response
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip
        )
        
        # Audit log for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            logger.info(
                "sensitive_endpoint_accessed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                client_ip=client_ip
            )
        
        return response
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint is sensitive (requires audit)"""
        sensitive_prefixes = [
            "/auth/",
            "/audit/",
            "/patient/",
            "/phi/",
            "/medical/",
            "/admin/"
        ]
        
        return any(path.startswith(prefix) for prefix in sensitive_prefixes)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for authentication endpoints
    
    This middleware applies stricter rate limits to authentication
    and PHI access endpoints to prevent brute force attacks.
    """
    
    # Rate limits by path pattern
    PATH_LIMITS = {
        "/auth/login": ("login", 5, 300),  # endpoint_type, max_requests, window_seconds
        "/auth/register": ("register", 3, 3600),
        "/auth/password-change": ("password_change", 3, 3600),
        "/auth/refresh": ("token_refresh", 10, 60),
    }
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to requests"""
        # Only apply to specific endpoints
        path = request.url.path
        
        # Check if path requires rate limiting
        limit_config = self._get_limit_config(path)
        
        if limit_config:
            endpoint_type, max_requests, window_seconds = limit_config
            
            limiter = get_rate_limiter()
            client_ip = get_client_identifier(request)
            
            # Check rate limit
            from cortex.security.rate_limiter import RateLimitConfig as RLC
            
            config = RLC(
                max_requests=max_requests,
                window_seconds=window_seconds,
                block_duration_seconds=window_seconds
            )
            
            allowed, retry_after, error_msg = limiter.check_rate_limit(
                endpoint_type=endpoint_type,
                identifier=client_ip,
                custom_config=config
            )
            
            if not allowed:
                # Log rate limit exceeded
                logger.warning(
                    "rate_limit_exceeded",
                    endpoint=endpoint_type,
                    client_ip=client_ip,
                    retry_after=retry_after
                )
                
                # Return 429 Too Many Requests
                return Response(
                    content='{"detail": "' + (error_msg or "Rate limit exceeded") + '"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)} if retry_after else None
                )
            
            # Record request
            limiter.record_request(endpoint_type, client_ip)
            
            # Store rate limit info for response headers
            from cortex.security.rate_limiter import RateLimitConfig
            remaining = limiter.get_remaining_requests(endpoint_type, client_ip)
            request.state.rate_limit_remaining = remaining
            request.state.rate_limit_limit = max_requests
        
        # Process request
        response = await call_next(request)
        
        return response
    
    def _get_limit_config(self, path: str) -> tuple:
        """Get rate limit configuration for path"""
        for pattern, config in self.PATH_LIMITS.items():
            if path.startswith(pattern):
                return config
        return None


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Input validation middleware
    
    Validates request body for potential attacks:
    - SQL injection
    - XSS
    - Path traversal
    """
    
    async def dispatch(self, request: Request, call_next):
        """Validate request body"""
        # Only validate POST, PUT, PATCH requests
        if request.method in ["POST", "PUT", "PATCH"]:
            # Read body for validation
            body = await request.body()
            
            if body:
                try:
                    # Try to parse as JSON
                    import json
                    data = json.loads(body)
                    
                    # Validate structured data
                    if isinstance(data, dict):
                        self._validate_dict(data)
                    elif isinstance(data, list):
                        for item in data[:100]:  # Limit validation
                            if isinstance(item, dict):
                                self._validate_dict(item)
                
                except json.JSONDecodeError:
                    # Not JSON, validate as string
                    self._validate_string(body.decode('utf-8', errors='ignore'))
                except InputValidationError as e:
                    logger.warning(
                        "input_validation_failed",
                        path=request.url.path,
                        error=str(e)
                    )
                    return Response(
                        content='{"detail": "Invalid input: ' + str(e) + '"}',
                        status_code=400,
                        media_type="application/json"
                    )
        
        # Process request
        response = await call_next(request)
        return response
    
    def _validate_dict(self, data: dict, depth: int = 0):
        """Recursively validate dictionary"""
        if depth > 10:  # Max depth
            return
        
        for key, value in data.items():
            if isinstance(value, str):
                self._validate_string(value)
            elif isinstance(value, dict):
                self._validate_dict(value, depth + 1)
            elif isinstance(value, list):
                for item in value[:100]:  # Limit
                    if isinstance(item, dict):
                        self._validate_dict(item, depth + 1)
                    elif isinstance(item, str):
                        self._validate_string(item)
    
    def _validate_string(self, value: str):
        """Validate string for attacks"""
        # Check for SQL injection
        if SecurityValidator.detect_sql_injection(value):
            raise InputValidationError("Potential SQL injection detected")
        
        # Check for XSS
        if SecurityValidator.detect_xss(value):
            raise InputValidationError("Potential XSS attack detected")
        
        # Check for path traversal
        if SecurityValidator.detect_path_traversal(value):
            raise InputValidationError("Path traversal detected")


class InputValidationError(Exception):
    """Input validation error"""
    pass


def setup_cors_middleware(app, allowed_origins: list):
    """
    Setup CORS middleware with secure defaults
    
    Args:
        app: FastAPI application
        allowed_origins: List of allowed origins
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Response-Time",
        ],
        max_age=3600,  # 1 hour
    )


def apply_security_middleware(app):
    """
    Apply all security middleware to FastAPI app
    
    Args:
        app: FastAPI application
    """
    # Add rate limiting middleware (applied first)
    app.add_middleware(RateLimitMiddleware)
    
    # Add input validation middleware
    app.add_middleware(InputValidationMiddleware)
    
    # Add security headers middleware (applied last)
    app.add_middleware(SecurityMiddleware)
    
    logger.info("Security middleware applied")