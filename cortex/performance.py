"""
Cortex Performance Optimization - Caching & Query Optimization

This module provides performance optimization:
- Query result caching
- Connection pool optimization
- Query optimization
- Response caching
- Lazy loading
"""

import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
import json
import structlog

from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError

logger = structlog.get_logger()


class CacheManager:
    """
    Simple in-memory cache with TTL
    
    For production, replace with Redis-backed cache
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache
        
        Args:
            default_ttl: Default time-to-live in seconds (default 5 minutes)
        """
        self.cache: Dict[str, Any] = {}
        self.expiry: Dict[str, datetime] = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key"""
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return ":".join(key_parts)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if key not in self.cache:
            return None
        
        # Check expiry
        if key in self.expiry and self.expiry[key] < datetime.utcnow():
            # Expired
            del self.cache[key]
            del self.expiry[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        self.cache[key] = value
        expiry_time = datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl)
        self.expiry[key] = expiry_time
    
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.expiry:
            del self.expiry[key]
    
    def clear(self) -> None:
        """Clear all cache"""
        self.cache.clear()
        self.expiry.clear()
    
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get value from cache or compute and cache
        
        Args:
            key: Cache key
            factory: Function to compute value if not in cache
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        
        if value is None:
            value = factory()
            self.set(key, value, ttl)
        
        return value
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = datetime.utcnow()
        valid_keys = sum(1 for k in self.cache if k not in self.expiry or self.expiry[k] > now)
        
        return {
            "total_keys": len(self.cache),
            "valid_keys": valid_keys,
            "expired_keys": len(self.cache) - valid_keys,
            "default_ttl": self.default_ttl
        }


# Global cache instance
_cache = CacheManager()


def cached(prefix: str, ttl: int = 300):
    """
    Decorator for caching function results
    
    Args:
        prefix: Cache key prefix
        ttl: Time-to-live in seconds
        
    Usage:
        @cached("user_profile", ttl=600)
        def get_user_profile(user_id):
            # Expensive database query
            return db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = _cache._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            result = _cache.get(key)
            
            if result is not None:
                logger.debug("cache_hit", key=key)
                return result
            
            # Compute result
            logger.debug("cache_miss", key=key)
            result = func(*args, **kwargs)
            
            # Cache result
            _cache.set(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


class QueryOptimizer:
    """
    SQL query optimization utilities
    """
    
    @staticmethod
    def add_eager_loading(query: Query, *relationships) -> Query:
        """
        Add eager loading to prevent N+1 queries
        
        Args:
            query: SQLAlchemy query
            relationships: Relationship names to eager load
            
        Returns:
            Query with eager loading
        """
        from sqlalchemy.orm import joinedload
        
        for rel in relationships:
            query = query.options(joinedload(rel))
        
        return query
    
    @staticmethod
    def add_selectin_loading(query: Query, *relationships) -> Query:
        """
        Add SELECT IN loading for collections
        
        Args:
            query: SQLAlchemy query
            relationships: Relationship names to load
            
        Returns:
            Query with selectin loading
        """
        from sqlalchemy.orm import selectinload
        
        for rel in relationships:
            query = query.options(selectinload(rel))
        
        return query
    
    @staticmethod
    def paginate(query: Query, page: int = 1, per_page: int = 50) -> tuple:
        """
        Paginate query results
        
        Args:
            query: SQLAlchemy query
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            (items, total, pages)
        """
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        
        return items, total, pages
    
    @staticmethod
    def optimize_count(query: Query) -> int:
        """
        Optimize count query
        
        Args:
            query: SQLAlchemy query
            
        Returns:
            Count
        """
        from sqlalchemy import func
        
        # Use count with primary key for better performance
        return query.count()


class ConnectionPoolMonitor:
    """
    Monitor database connection pool
    """
    
    def __init__(self, engine):
        """
        Initialize monitor
        
        Args:
            engine: SQLAlchemy engine
        """
        self.engine = engine
    
    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get connection pool status
        
        Returns:
            Pool status information
        """
        pool = self.engine.pool
        
        return {
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            "invalidated": pool.invalidatedcount if hasattr(pool, 'invalidatedcount') else 0
        }
    
    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Get connection pool metrics
        
        Returns:
            Pool metrics
        """
        pool = self.engine.pool
        
        metrics = {
            "pool_status": self.get_pool_status(),
            "pool_config": {
                "pool_size": getattr(pool, '_pool_size', None),
                "max_overflow": getattr(pool, '_max_overflow', None),
                "timeout": getattr(pool, '_timeout', None)
            }
        }
        
        return metrics


class PerformanceMonitor:
    """
    Performance monitoring utilities
    """
    
    def __init__(self):
        """Initialize monitor"""
        self.metrics: Dict[str, List[float]] = {}
    
    def record_latency(self, operation: str, latency_ms: float) -> None:
        """
        Record operation latency
        
        Args:
            operation: Operation name
            latency_ms: Latency in milliseconds
        """
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(latency_ms)
        
        # Keep only last 1000 measurements
        if len(self.metrics[operation]) > 1000:
            self.metrics[operation] = self.metrics[operation][-1000:]
    
    def get_percentile(self, operation: str, percentile: float = 95.0) -> Optional[float]:
        """
        Get latency percentile
        
        Args:
            operation: Operation name
            percentile: Percentile (0-100)
            
        Returns:
            Percentile value in milliseconds
        """
        if operation not in self.metrics or not self.metrics[operation]:
            return None
        
        values = sorted(self.metrics[operation])
        index = int(len(values) * percentile / 100)
        index = min(index, len(values) - 1)
        
        return values[index]
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """
        Get statistics for operation
        
        Args:
            operation: Operation name
            
        Returns:
            Statistics dict
        """
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        values = self.metrics[operation]
        
        import statistics
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": self.get_percentile(operation, 95.0),
            "p99": self.get_percentile(operation, 99.0)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics for all operations
        
        Returns:
            Dict of operation stats
        """
        return {op: self.get_stats(op) for op in self.metrics.keys()}


def measure_time(operation: str):
    """
    Decorator to measure function execution time
    
    Args:
        operation: Operation name for metrics
        
    Usage:
        @measure_time("get_user")
        def get_user(user_id):
            return db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                
                logger.debug(
                    "operation_latency",
                    operation=operation,
                    latency_ms=round(latency_ms, 2)
                )
                
                # Record in performance monitor if available
                global _perf_monitor
                if '_perf_monitor' in globals():
                    _perf_monitor.record_latency(operation, latency_ms)
        
        return wrapper
    return decorator


# Global performance monitor
_perf_monitor = PerformanceMonitor()


def get_performance_stats() -> Dict[str, Any]:
    """Get all performance statistics"""
    global _perf_monitor, _cache
    
    return {
        "cache_stats": _cache.stats(),
        "performance_metrics": _perf_monitor.get_all_stats()
    }


def clear_cache():
    """Clear all caches"""
    global _cache, _perf_monitor
    
    _cache.clear()
    _perf_monitor.metrics.clear()
    
    logger.info("cache_cleared")


# Convenience functions for caching common operations

@cached("icd10_search", ttl=600)
def cached_icd10_search(query: str, limit: int = 50):
    """
    Cached ICD-10 search
    
    Arguments are part of cache key
    """
    # This would call the actual search function
    # The result is cached for 10 minutes
    pass


@cached("cpt_search", ttl=600)
def cached_cpt_search(query: str, limit: int = 50):
    """
    Cached CPT search
    
    Arguments are part of cache key
    """
    pass


# Export utilities
__all__ = [
    'CacheManager',
    'cached',
    'QueryOptimizer',
    'ConnectionPoolMonitor',
    'PerformanceMonitor',
    'measure_time',
    'get_performance_stats',
    'clear_cache'
]