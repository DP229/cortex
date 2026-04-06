"""
Cortex Performance Testing Suite

This module provides tools for testing and benchmarking:
- Database connection pool performance
- Audit log query performance
- PHI detection performance
- Rate limiting performance
- API endpoint load testing
"""

import time
import asyncio
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import structlog

logger = structlog.get_logger()


@dataclass
class PerformanceResult:
    """Performance test result"""
    test_name: str
    total_time_ms: float
    operations_count: int
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    median_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    operations_per_second: float
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "test_name": self.test_name,
            "total_time_ms": round(self.total_time_ms, 2),
            "operations_count": self.operations_count,
            "avg_time_ms": round(self.avg_time_ms, 2),
            "min_time_ms": round(self.min_time_ms, 2),
            "max_time_ms": round(self.max_time_ms, 2),
            "median_time_ms": round(self.median_time_ms, 2),
            "p95_time_ms": round(self.p95_time_ms, 2),
            "p99_time_ms": round(self.p99_time_ms, 2),
            "operations_per_second": round(self.operations_per_second, 2),
            "errors": self.errors
        }


class PerformanceBenchmark:
    """Performance benchmarking suite"""
    
    def __init__(self, warmup_iterations: int = 10):
        """
        Initialize benchmark
        
        Args:
            warmup_iterations: Number of warmup iterations
        """
        self.warmup_iterations = warmup_iterations
        self.results: List[PerformanceResult] = []
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def _warmup(self, func: Callable, *args, **kwargs):
        """Run warmup iterations"""
        for _ in range(self.warmup_iterations):
            try:
                func(*args, **kwargs)
            except:
                pass  # Ignore errors during warmup
    
    async def _warmup_async(self, func: Callable, *args, **kwargs):
        """Run async warmup iterations"""
        for _ in range(self.warmup_iterations):
            try:
                await func(*args, **kwargs)
            except:
                pass
    
    def benchmark(
        self,
        test_name: str,
        func: Callable,
        iterations: int = 100,
        *args,
        **kwargs
    ) -> PerformanceResult:
        """
        Benchmark a synchronous function
        
        Args:
            test_name: Name of the test
            func: Function to benchmark
            iterations: Number of iterations
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            PerformanceResult
        """
        # Warmup
        self._warmup(func, *args, **kwargs)
        
        # Benchmark
        times = []
        errors = []
        
        for i in range(iterations):
            start = time.perf_counter()
            try:
                func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception as e:
                errors.append(str(e))
        
        # Calculate statistics
        if times:
            total_time = sum(times)
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            median_time = statistics.median(times)
            p95_time = self._calculate_percentile(times, 95)
            p99_time = self._calculate_percentile(times, 99)
            ops_per_sec = len(times) / (total_time / 1000)
        else:
            total_time = 0
            avg_time = min_time = max_time = median_time = p95_time = p99_time = 0
            ops_per_sec = 0
        
        result = PerformanceResult(
            test_name=test_name,
            total_time_ms=total_time,
            operations_count=len(times),
            avg_time_ms=avg_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            median_time_ms=median_time,
            p95_time_ms=p95_time,
            p99_time_ms=p99_time,
            operations_per_second=ops_per_sec,
            errors=errors
        )
        
        self.results.append(result)
        return result
    
    async def benchmark_async(
        self,
        test_name: str,
        func: Callable,
        iterations: int = 100,
        *args,
        **kwargs
    ) -> PerformanceResult:
        """
        Benchmark an async function
        
        Args:
            test_name: Name of the test
            func: Async function to benchmark
            iterations: Number of iterations
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            PerformanceResult
        """
        # Warmup
        await self._warmup_async(func, *args, **kwargs)
        
        # Benchmark
        times = []
        errors = []
        
        for i in range(iterations):
            start = time.perf_counter()
            try:
                await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception as e:
                errors.append(str(e))
        
        # Calculate statistics
        if times:
            total_time = sum(times)
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            median_time = statistics.median(times)
            p95_time = self._calculate_percentile(times, 95)
            p99_time = self._calculate_percentile(times, 99)
            ops_per_sec = len(times) / (total_time / 1000)
        else:
            total_time = 0
            avg_time = min_time = max_time = median_time = p95_time = p99_time = 0
            ops_per_sec = 0
        
        result = PerformanceResult(
            test_name=test_name,
            total_time_ms=total_time,
            operations_count=len(times),
            avg_time_ms=avg_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            median_time_ms=median_time,
            p95_time_ms=p95_time,
            p99_time_ms=p99_time,
            operations_per_second=ops_per_sec,
            errors=errors
        )
        
        self.results.append(result)
        return result
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all benchmark results"""
        return [r.to_dict() for r in self.results]
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)
        
        for result in self.results:
            print(f"\n{result.test_name}:")
            print(f"  Total Time: {result.total_time_ms:.2f}ms")
            print(f"  Operations: {result.operations_count}")
            print(f"  Avg Time: {result.avg_time_ms:.2f}ms")
            print(f"  Min Time: {result.min_time_ms:.2f}ms")
            print(f"  Max Time: {result.max_time_ms:.2f}ms")
            print(f"  Median: {result.median_time_ms:.2f}ms")
            print(f"  P95: {result.p95_time_ms:.2f}ms")
            print(f"  P99: {result.p99_time_ms:.2f}ms")
            print(f"  Ops/sec: {result.operations_per_second:.2f}")
            
            if result.errors:
                print(f"  Errors: {len(result.errors)}")


class LoadTest:
    """Load testing for concurrent requests"""
    
    def __init__(self, concurrency: int = 10):
        """
        Initialize load test
        
        Args:
            concurrency: Number of concurrent workers
        """
        self.concurrency = concurrency
    
    def run_concurrent(
        self,
        func: Callable,
        total_requests: int,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run load test with concurrent requests
        
        Args:
            func: Function to test
            total_requests: Total number of requests
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Load test results
        """
        results = {
            "total_requests": total_requests,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "times": []
        }
        
        def worker(requests: int):
            """Worker function"""
            for _ in range(requests):
                start = time.perf_counter()
                try:
                    func(*args, **kwargs)
                    elapsed = (time.perf_counter() - start) * 1000
                    results["times"].append(elapsed)
                    results["successful"] += 1
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(str(e))
        
        # Distribute requests across workers
        requests_per_worker = total_requests // self.concurrency
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = [
                executor.submit(worker, requests_per_worker)
                for _ in range(self.concurrency)
            ]
            
            # Wait for all futures
            for future in futures:
                future.result()
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Calculate statistics
        if results["times"]:
            results["avg_time_ms"] = statistics.mean(results["times"])
            results["min_time_ms"] = min(results["times"])
            results["max_time_ms"] = max(results["times"])
            results["median_time_ms"] = statistics.median(results["times"])
            results["requests_per_second"] = results["successful"] / (total_time / 1000)
        else:
            results["avg_time_ms"] = 0
            results["min_time_ms"] = 0
            results["max_time_ms"] = 0
            results["median_time_ms"] = 0
            results["requests_per_second"] = 0
        
        results["total_time_ms"] = total_time
        
        return results


class DatabaseBenchmark:
    """Benchmark database operations"""
    
    def __init__(self):
        """Initialize database benchmark"""
        from cortex.database import get_database_manager
        self.db = get_database_manager()
    
    def benchmark_connection_pool(self, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark connection pool performance
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=5)
        
        def get_connection():
            """Get connection from pool"""
            with self.db.get_session() as session:
                session.execute("SELECT 1")
        
        return benchmark.benchmark(
            "connection_pool",
            get_connection,
            iterations=iterations
        )
    
    def benchmark_audit_log_insert(self, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark audit log insert performance
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=5)
        from cortex.models import AuditLog
        from cortex.audit import AuditAction
        from uuid import uuid4
        
        def insert_audit():
            """Insert audit log"""
            with self.db.get_session() as session:
                audit = AuditLog(
                    user_id=uuid4(),
                    action=AuditAction.LOGIN.value,
                    resource_type="api",
                    ip_address="127.0.0.1"
                )
                session.add(audit)
                session.commit()
        
        return benchmark.benchmark(
            "audit_log_insert",
            insert_audit,
            iterations=iterations
        )
    
    def benchmark_audit_log_query(self, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark audit log query performance
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=5)
        from cortex.models import AuditLog
        from uuid import uuid4
        
        user_id = uuid4()
        
        def query_audit():
            """Query audit logs"""
            with self.db.get_session() as session:
                logs = session.query(AuditLog).filter(
                    AuditLog.user_id == user_id
                ).limit(50).all()
                return logs
        
        return benchmark.benchmark(
            "audit_log_query",
            query_audit,
            iterations=iterations
        )
    
    def run_all_benchmarks(self) -> List[Dict[str, Any]]:
        """Run all database benchmarks"""
        results = []
        
        results.append(self.benchmark_connection_pool(iterations=200))
        results.append(self.benchmark_audit_log_insert(iterations=100))
        results.append(self.benchmark_audit_log_query(iterations=200))
        
        return [r.to_dict() for r in results]


class PHIDetectionBenchmark:
    """Benchmark PHI detection performance"""
    
    def __init__(self):
        """Initialize PHI detection benchmark"""
        from cortex.security.phi_detection import PHIDetector
        self.detector = PHIDetector()
    
    def benchmark_small_text(self, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark PHI detection on small text (< 1KB)
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=10)
        
        text = """
        Patient John Smith (SSN: 123-45-6789) visited on 2024-01-15.
        DOB: 01/15/1980. MRN: MRN-12345.
        Phone: (555) 123-4567. Email: john.smith@email.com.
        """
        
        result = benchmark.benchmark(
            "phi_detection_small",
            self.detector.detect_phi,
            iterations=iterations,
            text=text
        )
        
        return result
    
    def benchmark_medium_text(self, iterations: int = 100) -> PerformanceResult:
        """
        Benchmark PHI detection on medium text (5KB)
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=5)
        
        # Generate medium-sized text with multiple PHI instances
        text_parts = []
        for i in range(50):
            text_parts.append(f"""
            Patient {i}: John Smith (SSN: {123+i:03d}-{45+i:02d}-{6789+i:04d})
            DOB: 01/15/1980. MRN: MRN-{12345+i:05d}
            Phone: (555) {123+i:03d}-{4567+i:04d}
            Email: patient{i}@email.com
            """)
        
        text = "\n".join(text_parts)
        
        result = benchmark.benchmark(
            "phi_detection_medium",
            self.detector.detect_phi,
            iterations=iterations,
            text=text
        )
        
        return result
    
    def benchmark_large_text(self, iterations: int = 50) -> PerformanceResult:
        """
        Benchmark PHI detection on large text (50KB)
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=2)
        
        # Generate large text
        text_parts = []
        for i in range(500):
            text_parts.append(f"""
            Medical Record {i}:
            Patient: John Smith
            SSN: {i:03d}-{45:02d}-{6789:04d}
            DOB: {(i % 12) + 1:02d}/{(i % 28) + 1:02d}/{1980 + (i % 40)}
            MRN: MRN-{i:06d}
            Phone: ({555 + (i % 10)}) {100 + i:03d}-{4567:04d}
            Address: {i} Main Street, City, ST {10000 + i:05d}
            """)
        
        text = "\n".join(text_parts)
        
        result = benchmark.benchmark(
            "phi_detection_large",
            self.detector.detect_phi,
            iterations=iterations,
            text=text
        )
        
        return result
    
    def run_all_benchmarks(self) -> List[Dict[str, Any]]:
        """Run all PHI detection benchmarks"""
        results = []
        
        results.append(self.benchmark_small_text(iterations=200))
        results.append(self.benchmark_medium_text(iterations=100))
        results.append(self.benchmark_large_text(iterations=50))
        
        return [r.to_dict() for r in results]


class RateLimiterBenchmark:
    """Benchmark rate limiting performance"""
    
    def __init__(self):
        """Initialize rate limiter benchmark"""
        from cortex.security.rate_limiter import RateLimiter
        self.limiter = RateLimiter()
    
    def benchmark_check_rate_limit(self, iterations: int = 1000) -> PerformanceResult:
        """
        Benchmark rate limit check performance
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=50)
        
        def check_limit():
            self.limiter.check_rate_limit("login", "192.168.1.1")
        
        result = benchmark.benchmark(
            "rate_limit_check",
            check_limit,
            iterations=iterations
        )
        
        return result
    
    def benchmark_record_request(self, iterations: int = 1000) -> PerformanceResult:
        """
        Benchmark request recording performance
        
        Args:
            iterations: Number of iterations
            
        Returns:
            PerformanceResult
        """
        benchmark = PerformanceBenchmark(warmup_iterations=50)
        
        def record():
            self.limiter.record_request("login", "192.168.1.1", user_id="user123")
        
        result = benchmark.benchmark(
            "rate_limit_record",
            record,
            iterations=iterations
        )
        
        return result
    
    def benchmark_concurrent_requests(self, total_requests: int = 10000) -> Dict[str, Any]:
        """
        Benchmark concurrent rate limiting
        
        Args:
            total_requests: Total number of requests
            
        Returns:
            Load test results
        """
        load_test = LoadTest(concurrency=10)
        
        def check_and_record():
            self.limiter.check_rate_limit("login", "192.168.1.1")
            self.limiter.record_request("login", "192.168.1.1")
        
        result = load_test.run_concurrent(
            check_and_record,
            total_requests=total_requests
        )
        
        return result
    
    def run_all_benchmarks(self) -> List[Dict[str, Any]]:
        """Run all rate limiter benchmarks"""
        results = []
        
        results.append(self.benchmark_check_rate_limit(iterations=5000))
        results.append(self.benchmark_record_request(iterations=5000))
        
        return [r.to_dict() for r in results]


def run_performance_suite() -> Dict[str, Any]:
    """
    Run complete performance test suite
    
    Returns:
        All benchmark results
    """
    print("\n" + "=" * 80)
    print("RUNNING PERFORMANCE TEST SUITE")
    print("=" * 80 + "\n")
    
    all_results = {
        "timestamp": datetime.utcnow().isoformat(),
        "database": {},
        "phi_detection": {},
        "rate_limiter": {},
        "load_tests": {}
    }
    
    # Database benchmarks
    print("Running database benchmarks...")
    try:
        db_benchmark = DatabaseBenchmark()
        all_results["database"] = db_benchmark.run_all_benchmarks()
        print("✓ Database benchmarks complete")
    except Exception as e:
        print(f"✗ Database benchmarks failed: {e}")
        all_results["database"]["error"] = str(e)
    
    # PHI detection benchmarks
    print("\nRunning PHI detection benchmarks...")
    try:
        phi_benchmark = PHIDetectionBenchmark()
        all_results["phi_detection"] = phi_benchmark.run_all_benchmarks()
        print("✓ PHI detection benchmarks complete")
    except Exception as e:
        print(f"✗ PHI detection benchmarks failed: {e}")
        all_results["phi_detection"]["error"] = str(e)
    
    # Rate limiter benchmarks
    print("\nRunning rate limiter benchmarks...")
    try:
        rate_benchmark = RateLimiterBenchmark()
        all_results["rate_limiter"] = rate_benchmark.run_all_benchmarks()
        print("✓ Rate limiter benchmarks complete")
    except Exception as e:
        print(f"✗ Rate limiter benchmarks failed: {e}")
        all_results["rate_limiter"]["error"] = str(e)
    
    # Print summary
    print("\n" + "=" * 80)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 80)
    
    for category, results in all_results.items():
        if category == "timestamp":
            continue
        
        print(f"\n{category.upper()}:")
        
        if isinstance(results, dict) and "error" in results:
            print(f"  ERROR: {results['error']}")
        elif isinstance(results, list):
            for result in results:
                print(f"  {result['test_name']}:")
                print(f"    Avg: {result['avg_time_ms']:.2f}ms")
                print(f"    P95: {result['p95_time_ms']:.2f}ms")
                print(f"    Ops/sec: {result['operations_per_second']:.2f}")
    
    return all_results


if __name__ == "__main__":
    results = run_performance_suite()
    
    # Save results to file
    import json
    with open("performance_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to performance_results.json")