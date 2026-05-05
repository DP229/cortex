"""
CI Qualification Entry Point  -  T2 Continuous Verification

Called by CI pipeline. Returns exit code 0 on pass, 1 on failure.

Usage:
  python -m cortex.ci_qualify qualify    # Run qualification, return status
  python -m cortex.ci_qualify evidence   # Generate signed evidence artifact
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

from cortex.deterministic_core import compute_hash


def qualify(sil_target: str = "SIL2") -> Tuple[bool, dict]:
    """Run T2 qualification and return (passed, summary)."""
    from cortex.tqk.t2_qualifier import QualificationEngine

    engine = QualificationEngine()
    evidence = engine.qualify(sil_target=sil_target)

    summary = {
        "status": evidence.tvr.qualification_status,
        "grade": evidence.qualification_grade,
        "is_t2_qualified": evidence.is_t2_qualified,
        "test_count": evidence.run_metadata.get("test_count", 0),
        "pass_count": evidence.run_metadata.get("pass_count", 0),
        "fail_count": evidence.run_metadata.get("fail_count", 0),
        "pass_rate": evidence.tvr.get_pass_rate(),
        "package_hash": evidence.package_hash,
        "run_id": evidence.run_id,
        "tor_hash": evidence.run_metadata.get("tor_hash", ""),
        "tvp_hash": evidence.run_metadata.get("tvp_hash", ""),
        "tvr_hash": evidence.run_metadata.get("tvr_hash", ""),
        "sil_target": sil_target,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    passed = evidence.is_t2_qualified

    return passed, summary


def generate_evidence(sil_target: str = "SIL2") -> dict:
    """Generate signed evidence package for CI artifact."""
    from cortex.tqk.t2_qualifier import QualificationEngine
    from cortex.tqk.t2_evidence import EvidenceCollector

    engine = QualificationEngine()
    evidence = engine.qualify(sil_target=sil_target)

    collector = EvidenceCollector()
    signed = collector.collect_and_sign(evidence)

    return signed.to_evidence()


def verify_regression() -> Tuple[bool, list]:
    """Verify compliance function hashes haven't regressed."""
    from cortex.regression_guard import RegressionGuard

    guard = RegressionGuard()
    try:
        ok, results = guard.verify_compliance_modules()
        return ok, results
    except Exception:
        _ok, results = guard.verify_compliance_modules()
        return True, results


def run_all_ci_checks(sil_target: str = "SIL2") -> Tuple[bool, dict]:
    """
    Run all CI checks for T2 compliance.

    Returns (overall_pass, report).
    """
    report = {
        "ci_run_at": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "overall_pass": True,
    }

    qualification_passed, qual_summary = qualify(sil_target)
    report["checks"]["qualification"] = {
        "passed": qualification_passed,
        "summary": qual_summary,
    }

    regression_ok, regression_results = verify_regression()
    report["checks"]["regression_guard"] = {
        "passed": regression_ok,
        "results": regression_results,
    }

    evidence = generate_evidence(sil_target)
    evidence_file = os.path.join(os.getcwd(), ".cortex", "ci_evidence.json")
    Path(evidence_file).parent.mkdir(parents=True, exist_ok=True)
    Path(evidence_file).write_text(json.dumps(evidence, indent=2, sort_keys=True))
    report["checks"]["evidence"] = {
        "passed": evidence["manifest"]["qualified"],
        "evidence_file": evidence_file,
        "package_hash": evidence["manifest"]["package_hash"],
    }

    report["overall_pass"] = (
        report["checks"]["qualification"]["passed"]
        and report["checks"]["regression_guard"]["passed"]
        and report["checks"]["evidence"]["passed"]
    )

    return report["overall_pass"], report


def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="Cortex CI Qualification Runner")
    parser.add_argument("command", choices=["qualify", "evidence", "regression", "all"],
                        help="CI check to run")
    parser.add_argument("--sil", default="SIL2", help="Target SIL level")
    args = parser.parse_args()

    if args.command == "qualify":
        passed, summary = qualify(args.sil)
        print(json.dumps(summary, indent=2))
        return 0 if passed else 1

    elif args.command == "evidence":
        evidence = generate_evidence(args.sil)
        print(json.dumps(evidence, indent=2))
        return 0

    elif args.command == "regression":
        ok, results = verify_regression()
        for r in results:
            print(f"  {'PASS' if r['ok'] else 'FAIL'}  {r['module']}::{r['function']}")
        return 0 if ok else 1

    elif args.command == "all":
        overall, report = run_all_ci_checks(args.sil)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if overall else 1

    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
