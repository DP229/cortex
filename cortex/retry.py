"""
NeuronMesh Retry - Fault Tolerance & Retry Logic

Provides:
- Automatic retries with exponential backoff
- Circuit breaker pattern
- Health checks
- Graceful degradation
"""

import time
import asyncio
from typing import Any, Callable, Optional, TypeVar
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategies"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 10000
    backoff_multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retriable_exceptions: tuple = (Exception,)


@dataclass
class RetryState:
    """State of a circuit breaker"""
    failures: int = 0
    last_failure: float = 0
    state: str = "closed"  # closed, open, half_open
    opened_at: float = 0


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: Testing if service recovered
    
    Example:
        breaker = CircuitBreaker(failure_threshold=5)
        
        try:
            result = breaker.call(risky_function)
        except CircuitOpen:
            # Handle failure gracefully
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = "closed"
        self.failures = 0
        self.last_failure = 0
        self.opened_at = 0
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker"""
        if self.state == "open":
            # Check if we should try half-open
            if time.time() - self.opened_at >= self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker: OPEN -> HALF_OPEN")
            else:
                raise CircuitOpenError("Circuit is open")
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset or close
            if self.state == "half_open":
                self._close()
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            raise
    
    def _record_failure(self):
        """Record a failure"""
        self.failures += 1
        self.last_failure = time.time()
        
        if self.failures >= self.failure_threshold:
            self._open()
    
    def _open(self):
        """Open the circuit"""
        self.state = "open"
        self.opened_at = time.time()
        logger.warning(f"Circuit breaker: OPEN (threshold: {self.failure_threshold})")
    
    def _close(self):
        """Close the circuit"""
        self.state = "closed"
        self.failures = 0
        logger.info("Circuit breaker: CLOSED")
    
    def get_state(self) -> str:
        """Get current state"""
        return self.state


class CircuitOpenError(Exception):
    """Raised when circuit is open"""
    pass


def with_retry(
    func: Callable[..., T] = None,
    config: RetryConfig = None,
) -> Callable[..., T]:
    """
    Decorator for automatic retry with backoff.
    
    Example:
        @with_retry(config=RetryConfig(max_attempts=3))
        def risky_operation():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args, **kwargs) -> T:
            return await _retry_async(fn, config, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs) -> T:
            return _retry_sync(fn, config, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper
    
    if func is None:
        return decorator
    return decorator(func)


def _retry_sync(func: Callable[..., T], config: RetryConfig, *args, **kwargs) -> T:
    """Synchronous retry implementation"""
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
            
        except config.retriable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = _calculate_delay(config, attempt)
                logger.warning(f"Retry {attempt + 1}/{config.max_attempts} after {delay}ms: {e}")
                time.sleep(delay / 1000)
    
    raise last_exception


async def _retry_async(func: Callable[..., T], config: RetryConfig, *args, **kwargs) -> T:
    """Async retry implementation"""
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
            
        except config.retriable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = _calculate_delay(config, attempt)
                logger.warning(f"Retry {attempt + 1}/{config.max_attempts} after {delay}ms: {e}")
                await asyncio.sleep(delay / 1000)
    
    raise last_exception


def _calculate_delay(config: RetryConfig, attempt: int) -> int:
    """Calculate delay for this attempt"""
    if config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.initial_delay_ms * (config.backoff_multiplier ** attempt)
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.initial_delay_ms * (attempt + 1)
    else:  # CONSTANT
        delay = config.initial_delay_ms
    
    return min(delay, config.max_delay_ms)


class HealthCheck:
    """
    Health check for monitoring service health.
    
    Example:
        checker = HealthCheck()
        
        checker.register("database", check_db_connection)
        checker.register("api", check_api_health)
        
        result = checker.check_all()
        if result.is_healthy:
            print("All systems operational")
    """
    
    def __init__(self):
        self._checks = {}
    
    def register(self, name: str, check_func: Callable[[], bool]):
        """Register a health check"""
        self._checks[name] = check_func
    
    def check(self, name: str) -> bool:
        """Run a specific check"""
        if name not in self._checks:
            return False
        
        try:
            return self._checks[name]()
        except Exception:
            return False
    
    def check_all(self) -> "HealthResult":
        """Run all checks"""
        results = {}
        healthy = True
        
        for name in self._checks:
            results[name] = self.check(name)
            if not results[name]:
                healthy = False
        
        return HealthResult(
            is_healthy=healthy,
            checks=results,
            timestamp=time.time(),
        )


@dataclass
class HealthResult:
    """Result of health check"""
    is_healthy: bool
    checks: dict
    timestamp: float
    
    def to_dict(self) -> dict:
        return {
            "healthy": self.is_healthy,
            "checks": self.checks,
            "timestamp": self.timestamp,
        }
