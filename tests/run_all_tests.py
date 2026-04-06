#!/usr/bin/env python3
"""
Complete Test Runner for Healthcare Compliance Agent

Runs all test suites:
1. Unit tests (security, auth, consent, documents, coding)
2. Integration tests
3. Performance tests

Usage:
    python tests/run_all_tests.py [options]

Options:
    --unit         Run unit tests only
    --integration  Run integration tests only
    --performance  Run performance tests only
    --all          Run all tests (default)
    --coverage     Generate coverage report
    --verbose      Verbose output
"""

import sys
import subprocess
import argparse
from pathlib import Path
import structlog

logger = structlog.get_logger()


class TestRunner:
    """Test runner for healthcare compliance agent"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.results = {}
    
    def run_unit_tests(self, verbose=False):
        """Run unit tests"""
        print("\n" + "=" * 80)
        print("RUNNING UNIT TESTS")
        print("=" * 80)
        
        test_files = [
            "test_auth.py",
            "test_rbac.py",
            "test_audit.py",
            "test_security.py",
            "test_consent.py",
            "test_documents.py",
            "test_medical_coding.py"
        ]
        
        failed = []
        passed = []
        
        for test_file in test_files:
            test_path = self.test_dir / test_file
            
            if not test_path.exists():
                print(f"⚠ Test file not found: {test_file}")
                continue
            
            print(f"\nRunning {test_file}...")
            
            cmd = ["pytest", str(test_path), "-v" if verbose else "-q", "--tb=short"]
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode == 0:
                passed.append(test_file)
                print(f"✓ {test_file} PASSED")
            else:
                failed.append(test_file)
                print(f"✗ {test_file} FAILED")
                if verbose:
                    print(result.stdout.decode())
        
        self.results["unit"] = {
            "passed": len(passed),
            "failed": len(failed),
            "total": len(test_files)
        }
        
        return len(failed) == 0
    
    def run_integration_tests(self, verbose=False):
        """Run integration tests"""
        print("\n" + "=" * 80)
        print("RUNNING INTEGRATION TESTS")
        print("=" * 80)
        
        test_file = self.test_dir / "test_integration_healthcare.py"
        
        if not test_file.exists():
            print("⚠ Integration test file not found")
            self.results["integration"] = {"passed": 0, "failed": 0, "total": 0}
            return False
        
        print(f"\nRunning {test_file.name}...")
        
        cmd = ["pytest", str(test_file), "-v" if verbose else "-q", "--tb=short"]
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode == 0:
            print(f"✓ Integration tests PASSED")
            self.results["integration"] = {"passed": 1, "failed": 0, "total": 1}
            return True
        else:
            print(f"✗ Integration tests FAILED")
            if verbose:
                print(result.stdout.decode())
            self.results["integration"] = {"passed": 0, "failed": 1, "total": 1}
            return False
    
    def run_performance_tests(self):
        """Run performance tests"""
        print("\n" + "=" * 80)
        print("RUNNING PERFORMANCE TESTS")
        print("=" * 80)
        
        perf_script = self.project_root / "scripts" / "run_performance_tests.py"
        
        if not perf_script.exists():
            print("⚠ Performance test script not found")
            self.results["performance"] = {"passed": 0, "failed": 0, "total": 0}
            return True
        
        print(f"\nRunning performance tests...")
        
        cmd = ["python", str(perf_script)]
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode == 0:
            print(f"✓ Performance tests PASSED")
            self.results["performance"] = {"passed": 1, "failed": 0, "total": 1}
            return True
        else:
            print(f"✗ Performance tests FAILED")
            print(result.stdout.decode())
            self.results["performance"] = {"passed": 0, "failed": 1, "total": 1}
            return False
    
    def generate_coverage_report(self):
        """Generate coverage report"""
        print("\n" + "=" * 80)
        print("GENERATING COVERAGE REPORT")
        print("=" * 80)
        
        cmd = [
            "pytest",
            "--cov=cortex",
            "--cov-report=html",
            "--cov-report=term",
            str(self.test_dir)
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("✓ Coverage report generated in htmlcov/")
            return True
        else:
            print("✗ Coverage report generation failed")
            return False
    
    def check_database_connection(self):
        """Check database connection"""
        print("\n" + "=" * 80)
        print("CHECKING DATABASE CONNECTION")
        print("=" * 80)
        
        try:
            from cortex.database import get_database_manager
            
            db = get_database_manager()
            if db.health_check():
                print("✓ Database connection successful")
                return True
            else:
                print("✗ Database health check failed")
                return False
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def check_environment(self):
        """Check environment setup"""
        print("\n" + "=" * 80)
        print("CHECKING ENVIRONMENT")
        print("=" * 80)
        
        checks = []
        
        # Check Python version
        import sys
        python_version = sys.version_info
        if python_version >= (3, 9):
            print(f"✓ Python version: {python_version.major}.{python_version.minor}")
            checks.append(True)
        else:
            print(f"✗ Python version too old: {python_version.major}.{python_version.minor}")
            checks.append(False)
        
        # Check required packages
        required_packages = [
            "fastapi", "sqlalchemy", "pydantic", "pytest", 
            "structlog", "argon2-cffi", "pyjwt"
        ]
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"✓ Package installed: {package}")
                checks.append(True)
            except ImportError:
                print(f"✗ Package missing: {package}")
                checks.append(False)
        
        # Check environment variables
        import os
        env_vars = ["DATABASE_URL", "ENCRYPTION_KEY"]
        
        for var in env_vars:
            if os.getenv(var):
                print(f"✓ Environment variable set: {var}")
                checks.append(True)
            else:
                print(f"⚠ Environment variable not set: {var}")
                checks.append(False)
        
        return all(checks)
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        total_passed = sum(r.get("passed", 0) for r in self.results.values())
        total_failed = sum(r.get("failed", 0) for r in self.results.values())
        total_tests = sum(r.get("total", 0) for r in self.results.values())
        
        print(f"\nUnit Tests:")
        if "unit" in self.results:
            print(f"  Passed: {self.results['unit']['passed']}")
            print(f"  Failed: {self.results['unit']['failed']}")
            print(f"  Total: {self.results['unit']['total']}")
        
        print(f"\nIntegration Tests:")
        if "integration" in self.results:
            print(f"  Passed: {self.results['integration']['passed']}")
            print(f"  Failed: {self.results['integration']['failed']}")
            print(f"  Total: {self.results['integration']['total']}")
        
        print(f"\nPerformance Tests:")
        if "performance" in self.results:
            print(f"  Passed: {self.results['performance']['passed']}")
            print(f"  Failed: {self.results['performance']['failed']}")
            print(f"  Total: {self.results['performance']['total']}")
        
        print(f"\nOverall Summary:")
        print(f"  Total Passed: {total_passed}")
        print(f"  Total Failed: {total_failed}")
        print(f"  Total Tests: {total_tests}")
        
        if total_failed == 0:
            print(f"\n✓ ALL TESTS PASSED")
            return True
        else:
            print(f"\n✗ SOME TESTS FAILED")
            return False
    
    def run_all(self, verbose=False):
        """Run all tests"""
        print("\n" + "=" * 80)
        print("HEALTHCARE COMPLIANCE AGENT - COMPLETE TEST SUITE")
        print("=" * 80)
        
        # Check environment
        if not self.check_environment():
            print("\n✗ Environment check failed")
            return False
        
        # Check database
        if not self.check_database_connection():
            print("\n⚠ Database not available, skipping database tests")
        
        # Run unit tests
        self.run_unit_tests(verbose)
        
        # Run integration tests
        self.run_integration_tests(verbose)
        
        # Run performance tests
        self.run_performance_tests()
        
        # Print summary
        return self.print_summary()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run tests for Healthcare Compliance Agent")
    
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Default to all tests if no specific test type selected
    if not any([args.unit, args.integration, args.performance]):
        args.all = True
    
    success = True
    
    if args.all:
        success = runner.run_all(verbose=args.verbose)
    else:
        if args.unit:
            runner.run_unit_tests(verbose=args.verbose)
        if args.integration:
            runner.run_integration_tests(verbose=args.verbose)
        if args.performance:
            runner.run_performance_tests()
        
        success = runner.print_summary()
    
    if args.coverage:
        runner.generate_coverage_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()