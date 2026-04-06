#!/usr/bin/env python3
"""
Run Performance Tests

This script runs the performance test suite and saves results.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.performance import run_performance_suite
import json
from datetime import datetime


def main():
    """Run performance tests"""
    print("=" * 80)
    print("CORTEX PERFORMANCE TEST SUITE")
    print("=" * 80)
    print(f"Started: {datetime.utcnow().isoformat()}")
    
    # Run tests
    results = run_performance_suite()
    
    # Add metadata
    results["test_run"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform
    }
    
    # Save results
    output_dir = Path(__file__).parent.parent / "performance_results"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"performance_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    # Generate summary report
    generate_summary_report(results, output_dir, timestamp)
    
    print("\nPerformance test suite complete!")


def generate_summary_report(results: dict, output_dir: Path, timestamp: str):
    """Generate human-readable summary report"""
    
    report_file = output_dir / f"performance_report_{timestamp}.md"
    
    with open(report_file, "w") as f:
        f.write("# Performance Test Report\n\n")
        f.write(f"**Timestamp:** {results['timestamp']}\n\n")
        
        f.write("---\n\n")
        
        # Database results
        if "database" in results and isinstance(results["database"], list):
            f.write("## Database Performance\n\n")
            f.write("| Test | Avg Time (ms) | P95 (ms) | Ops/sec | Status |\n")
            f.write("|------|---------------|----------|---------|--------|\n")
            
            for test in results["database"]:
                test_name = test.get("test_name", "unknown")
                avg_time = test.get("avg_time_ms", 0)
                p95_time = test.get("p95_time_ms", 0)
                ops_sec = test.get("operations_per_second", 0)
                status = "✓" if not test.get("errors") else "✗"
                
                f.write(f"| {test_name} | {avg_time:.2f} | {p95_time:.2f} | {ops_sec:.2f} | {status} |\n")
            
            f.write("\n")
        
        # PHI Detection results
        if "phi_detection" in results and isinstance(results["phi_detection"], list):
            f.write("## PHI Detection Performance\n\n")
            f.write("| Test | Avg Time (ms) | P95 (ms) | Ops/sec | Status |\n")
            f.write("|------|---------------|----------|---------|--------|\n")
            
            for test in results["phi_detection"]:
                test_name = test.get("test_name", "unknown")
                avg_time = test.get("avg_time_ms", 0)
                p95_time = test.get("p95_time_ms", 0)
                ops_sec = test.get("operations_per_second", 0)
                status = "✓" if not test.get("errors") else "✗"
                
                f.write(f"| {test_name} | {avg_time:.2f} | {p95_time:.2f} | {ops_sec:.2f} | {status} |\n")
            
            f.write("\n")
        
        # Rate Limiter results
        if "rate_limiter" in results and isinstance(results["rate_limiter"], list):
            f.write("## Rate Limiter Performance\n\n")
            f.write("| Test | Avg Time (ms) | P95 (ms) | Ops/sec | Status |\n")
            f.write("|------|---------------|----------|---------|--------|\n")
            
            for test in results["rate_limiter"]:
                test_name = test.get("test_name", "unknown")
                avg_time = test.get("avg_time_ms", 0)
                p95_time = test.get("p95_time_ms", 0)
                ops_sec = test.get("operations_per_second", 0)
                status = "✓" if not test.get("errors") else "✗"
                
                f.write(f"| {test_name} | {avg_time:.2f} | {p95_time:.2f} | {ops_sec:.2f} | {status} |\n")
            
            f.write("\n")
        
        # Performance thresholds
        f.write("## Performance Thresholds\n\n")
        f.write("Target performance (HIPAA compliance requirements):\n\n")
        f.write("| Component | Target | Status |\n")
        f.write("|-----------|--------|--------|\n")
        f.write("| Audit log insert | < 10ms | Check result above |\n")
        f.write("| Audit log query | < 50ms | Check result above |\n")
        f.write("| PHI detection (small) | < 5ms | Check result above |\n")
        f.write("| PHI detection (large) | < 100ms | Check result above |\n")
        f.write("| Rate limit check | < 1ms | Check result above |\n")
        f.write("| Rate limit record | < 1ms | Check result above |\n\n")
        
        f.write("---\n\n")
        f.write("*Generated automatically by performance test suite*\n")
    
    print(f"✓ Report saved to {report_file}")


if __name__ == "__main__":
    main()