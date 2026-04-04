"""
NeuronMesh Metrics - Performance Monitoring & Observability

Provides:
- Request metrics
- Latency tracking
- Cost accounting
- Performance profiling
"""

import os
import time
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class MetricPoint:
    """A single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class RequestMetric:
    """Metrics for a single request"""
    request_id: str
    model: str
    latency_ms: int
    tokens_used: int
    cost: float
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """
    Metrics collection and aggregation.
    
    Features:
    - Request tracking
    - Latency percentiles
    - Cost aggregation
    - Custom metrics
    
    Example:
        metrics = MetricsCollector()
        
        # Track request
        metrics.track_request("gpt-4", 500, 1000, 0.03)
        
        # Get stats
        stats = metrics.get_stats()
        print(stats["p95_latency_ms"])
    """
    
    def __init__(self, name: str = "cortex"):
        self.name = name
        self._lock = threading.RLock()
        
        # Request metrics
        self._requests: List[RequestMetric] = []
        self._max_requests = 10000
        
        # Aggregated metrics
        self._total_requests = 0
        self._total_errors = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        
        # Latency tracking (for percentiles)
        self._latencies: List[int] = []
        
        # Custom metrics
        self._custom_metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        
        # Start time
        self._start_time = time.time()
    
    def track_request(
        self,
        model: str,
        latency_ms: int,
        tokens_used: int,
        cost: float,
        success: bool = True,
        error: str = None,
        request_id: str = None,
    ):
        """Track a request"""
        with self._lock:
            metric = RequestMetric(
                request_id=request_id or f"{int(time.time()*1000)}",
                model=model,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                success=success,
                error=error,
            )
            
            self._requests.append(metric)
            
            # Trim old requests
            if len(self._requests) > self._max_requests:
                self._requests = self._requests[-self._max_requests:]
            
            # Update aggregates
            self._total_requests += 1
            self._total_tokens += tokens_used
            self._total_cost += cost
            
            if not success:
                self._total_errors += 1
            
            self._latencies.append(latency_ms)
    
    def track_custom(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Track a custom metric"""
        with self._lock:
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                labels=labels or {},
            )
            self._custom_metrics[metric_name].append(point)
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics"""
        with self._lock:
            uptime = time.time() - self._start_time
            
            # Calculate percentiles from recent latencies
            latencies = self._latencies[-1000:] if self._latencies else []
            
            return {
                "name": self.name,
                "uptime_seconds": int(uptime),
                "requests": {
                    "total": self._total_requests,
                    "errors": self._total_errors,
                    "success_rate": round(
                        (self._total_requests - self._total_errors) / max(1, self._total_requests),
                        4
                    ),
                },
                "latency_ms": {
                    "min": min(latencies) if latencies else 0,
                    "max": max(latencies) if latencies else 0,
                    "avg": sum(latencies) / len(latencies) if latencies else 0,
                    "p50": self._percentile([float(l) for l in latencies], 50),
                    "p90": self._percentile([float(l) for l in latencies], 90),
                    "p95": self._percentile([float(l) for l in latencies], 95),
                    "p99": self._percentile([float(l) for l in latencies], 99),
                },
                "tokens": {
                    "total": self._total_tokens,
                    "avg_per_request": round(
                        self._total_tokens / max(1, self._total_requests),
                        1
                    ),
                },
                "cost": {
                    "total": round(self._total_cost, 4),
                    "avg_per_request": round(
                        self._total_cost / max(1, self._total_requests),
                        6
                    ),
                },
                "requests_per_second": round(
                    self._total_requests / max(1, uptime),
                    2
                ),
            }
    
    def get_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get per-model statistics"""
        with self._lock:
            model_data = defaultdict(lambda: {
                "requests": 0,
                "errors": 0,
                "latencies": [],
                "tokens": 0,
                "cost": 0.0,
            })
            
            for req in self._requests:
                data = model_data[req.model]
                data["requests"] += 1
                data["errors"] += 0 if req.success else 1
                data["latencies"].append(req.latency_ms)
                data["tokens"] += req.tokens_used
                data["cost"] += req.cost
            
            stats = {}
            for model, data in model_data.items():
                stats[model] = {
                    "requests": data["requests"],
                    "errors": data["errors"],
                    "success_rate": round(
                        (data["requests"] - data["errors"]) / max(1, data["requests"]),
                        4
                    ),
                    "avg_latency_ms": round(
                        sum(data["latencies"]) / len(data["latencies"])
                        if data["latencies"] else 0,
                        1
                    ),
                    "total_tokens": data["tokens"],
                    "total_cost": round(data["cost"], 4),
                }
            
            return stats
    
    def get_custom_metrics(self, metric_name: str) -> List[MetricPoint]:
        """Get custom metric data"""
        with self._lock:
            return self._custom_metrics.get(metric_name, [])
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._requests.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._total_tokens = 0
            self._total_cost = 0.0
            self._latencies.clear()
            self._custom_metrics.clear()
            self._start_time = time.time()
    
    def export_json(self) -> str:
        """Export metrics as JSON"""
        return json.dumps({
            "stats": self.get_stats(),
            "model_stats": self.get_model_stats(),
        }, indent=2)


# === Global metrics ===

_global_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def track_request(model: str, latency_ms: int, tokens: int, cost: float, **kwargs):
    """Quick track request to global metrics"""
    get_metrics().track_request(model, latency_ms, tokens, cost, **kwargs)
