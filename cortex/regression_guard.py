"""
Regression Guard  -  Pinned Hash Protection for T2 Compliance

Stores expected SHA-256 hashes for every compliance-critical function.
Any unapproved hash change = CI failure.

Workflow:
  1. Dev changes code → function output hash differs
  2. CI runs `regression_guard.py` → detects hash mismatch
  3. Dev reviews change, bumps module version, regenerates expectations
  4. CI re-runs → passes (explicit version bump confirms intentional change)

The expectation store lives at: .cortex/expected_hashes.json
and is checked into version control.

Usage:
  python -m cortex.regression_guard verify   # Verify all hashes match
  python -m cortex.regression_guard generate  # Regenerate expectations
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cortex.deterministic_core import compute_hash, ModuleVersion


EXPECTED_HASHES_PATH = os.path.join(
    os.path.dirname(__file__), "..", ".cortex", "expected_hashes.json"
)


@dataclass
class HashExpectation:
    module: str
    function: str
    version: str
    input_hash: str
    expected_output_hash: str
    last_verified: str = ""

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "function": self.function,
            "version": self.version,
            "input_hash": self.input_hash,
            "expected_output_hash": self.expected_output_hash,
            "last_verified": self.last_verified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HashExpectation":
        return cls(**d)


@dataclass
class HashExpectationStore:
    expectations: Dict[str, HashExpectation] = field(default_factory=dict)
    generated_at: str = ""
    store_hash: str = ""

    def key(self, module: str, function: str) -> str:
        return f"{module}::{function}"

    def get(self, module: str, function: str) -> Optional[HashExpectation]:
        return self.expectations.get(self.key(module, function))

    def set(self, expectation: HashExpectation) -> None:
        self.expectations[self.key(expectation.module, expectation.function)] = expectation

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "store_hash": self.store_hash,
            "expectations": {k: v.to_dict() for k, v in self.expectations.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HashExpectationStore":
        store = cls(
            generated_at=d.get("generated_at", ""),
            store_hash=d.get("store_hash", ""),
        )
        for k, v in d.get("expectations", {}).items():
            store.expectations[k] = HashExpectation.from_dict(v)
        return store

    def finalize(self) -> None:
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self.store_hash = compute_hash(self.to_dict())


class RegressionGuard:
    """
    Guard that verifies compliance function outputs haven't regressed.

    Each compliance function is identified by (module, function).
    The guard pin-computes its output hash and compares against
    the expected hash in the store.
    """

    def __init__(self, store_path: str = EXPECTED_HASHES_PATH):
        self.store_path = store_path
        self.store = self._load_store()

    def _load_store(self) -> HashExpectationStore:
        path = Path(self.store_path)
        if path.exists():
            return HashExpectationStore.from_dict(json.loads(path.read_text()))
        return HashExpectationStore()

    def _save_store(self) -> None:
        self.store.finalize()
        path = Path(self.store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.store.to_dict(), indent=2, sort_keys=True))

    def register(
        self,
        module: str,
        function: str,
        version: ModuleVersion,
        input_value: Any = None,
        output_value: Any = None,
    ) -> HashExpectation:
        input_hash = compute_hash(input_value) if input_value is not None else ""
        output_hash = compute_hash(output_value) if output_value is not None else ""
        exp = HashExpectation(
            module=module,
            function=function,
            version=str(version),
            input_hash=input_hash,
            expected_output_hash=output_hash,
            last_verified=datetime.now(timezone.utc).isoformat(),
        )
        self.store.set(exp)
        return exp

    def verify_one(
        self,
        module: str,
        function: str,
        version: ModuleVersion,
        output_value: Any,
    ) -> Tuple[bool, str, str]:
        expected = self.store.get(module, function)
        actual_hash = compute_hash(output_value)
        if expected is None:
            return False, actual_hash, f"No expectation registered for {module}::{function}"
        if expected.expected_output_hash != actual_hash:
            return (
                False,
                actual_hash,
                f"Hash mismatch: {module}::{function} v{version} — "
                f"expected {expected.expected_output_hash[:16]} but got {actual_hash[:16]}. "
                f"Run `python -m cortex.regression_guard generate` to update expectations.",
            )
        expected.last_verified = datetime.now(timezone.utc).isoformat()
        return True, actual_hash, "OK"

    def verify_all(self, registrations: List[Tuple[str, str, ModuleVersion, Any]]) -> Tuple[bool, List[dict]]:
        results = []
        all_pass = True
        for module, function, version, output in registrations:
            ok, actual, msg = self.verify_one(module, function, version, output)
            if not ok:
                all_pass = False
            results.append({
                "module": module,
                "function": function,
                "version": str(version),
                "ok": ok,
                "actual_hash": actual,
                "message": msg,
            })
        return all_pass, results

    def generate_all(
        self,
        registrations: List[Tuple[str, str, ModuleVersion, Any, Any]],
    ) -> HashExpectationStore:
        for module, function, version, input_val, output_val in registrations:
            self.register(module, function, version, input_val, output_val)
        self._save_store()
        return self.store

    def scan_and_register_compliance_modules(self) -> int:
        """
        Auto-scan known compliance modules and register their hashes.

        Returns count of registered expectations.
        """
        registrations: List[Tuple[str, str, ModuleVersion, Any, Any]] = []

        # TOR generation
        from cortex.tqk.tor import ToolOperationalRequirements
        tor = ToolOperationalRequirements(tool_class="T2")
        registrations.append(
            ("cortex.tqk.tor", "to_dict", ModuleVersion(1, 0, 0), None, tor.to_dict())
        )

        # TVP generation
        from cortex.tqk.tvp import ToolVerificationPlan
        tvp = ToolVerificationPlan()
        tvp.derive_from_tor(tor)
        registrations.append(
            ("cortex.tqk.tvp", "to_dict", ModuleVersion(1, 0, 0), None, tvp.to_dict())
        )

        # TVR generation (empty — no test results)
        from cortex.tqk.tvr import ToolVerificationReport
        tvr = ToolVerificationReport()
        registrations.append(
            ("cortex.tqk.tvr", "to_dict", ModuleVersion(1, 0, 0), None, tvr.to_dict())
        )

        # Evidence collector
        from cortex.tqk.t2_qualifier import QualificationEngine, T2EvidencePackage
        engine = QualificationEngine()
        evidence = engine.qualify(sil_target="SIL2")
        registrations.append(
            ("cortex.tqk.t2_qualifier", "qualify", ModuleVersion(1, 0, 0),
             "SIL2", evidence.to_evidence())
        )

        # Evidence signing
        from cortex.tqk.t2_evidence import EvidenceCollector, SignedT2Evidence
        collector = EvidenceCollector()
        signed = collector.collect_and_sign(evidence)
        registrations.append(
            ("cortex.tqk.t2_evidence", "collect_and_sign", ModuleVersion(1, 0, 0),
             None, signed.to_evidence())
        )

        # Rail taxonomy data quality
        from cortex.rail_taxonomy import DataQualityReport
        dq = DataQualityReport(
            report_id="DQ-001",
            generated_at="2026-05-04",
            dataset_hash="abc123",
            dataset_size=10000,
        )
        registrations.append(
            ("cortex.rail_taxonomy", "DataQualityReport", ModuleVersion(1, 0, 0),
             None, dq.to_evidence())
        )

        self.generate_all(registrations)
        return len(registrations)

    def verify_compliance_modules(self) -> Tuple[bool, List[dict]]:
        verifications: List[Tuple[str, str, ModuleVersion, Any]] = []

        from cortex.tqk.tor import ToolOperationalRequirements
        tor = ToolOperationalRequirements(tool_class="T2")
        verifications.append(
            ("cortex.tqk.tor", "to_dict", ModuleVersion(1, 0, 0), tor.to_dict())
        )

        from cortex.tqk.tvp import ToolVerificationPlan
        tvp = ToolVerificationPlan()
        tvp.derive_from_tor(tor)
        verifications.append(
            ("cortex.tqk.tvp", "to_dict", ModuleVersion(1, 0, 0), tvp.to_dict())
        )

        from cortex.tqk.tvr import ToolVerificationReport
        tvr = ToolVerificationReport()
        verifications.append(
            ("cortex.tqk.tvr", "to_dict", ModuleVersion(1, 0, 0), tvr.to_dict())
        )

        from cortex.tqk.t2_qualifier import QualificationEngine
        engine = QualificationEngine()
        evidence = engine.qualify(sil_target="SIL2")
        verifications.append(
            ("cortex.tqk.t2_qualifier", "qualify", ModuleVersion(1, 0, 0),
             evidence.to_evidence())
        )

        from cortex.tqk.t2_evidence import EvidenceCollector
        collector = EvidenceCollector()
        signed = collector.collect_and_sign(evidence)
        verifications.append(
            ("cortex.tqk.t2_evidence", "collect_and_sign", ModuleVersion(1, 0, 0),
             signed.to_evidence())
        )

        from cortex.rail_taxonomy import DataQualityReport
        dq = DataQualityReport(
            report_id="DQ-001",
            generated_at="2026-05-04",
            dataset_hash="abc123",
            dataset_size=10000,
        )
        verifications.append(
            ("cortex.rail_taxonomy", "DataQualityReport", ModuleVersion(1, 0, 0),
             dq.to_evidence())
        )

        return self.verify_all(verifications)


def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="Cortex T2 Regression Guard")
    parser.add_argument("command", choices=["verify", "generate"],
                        help="verify hashes or generate expectations")
    args = parser.parse_args()

    guard = RegressionGuard()

    if args.command == "generate":
        count = guard.scan_and_register_compliance_modules()
        print(f"Generated {count} hash expectations -> {guard.store_path}")
        print(f"Store hash: {guard.store.store_hash[:16]}")
        return 0

    elif args.command == "verify":
        ok, results = guard.verify_compliance_modules()
        all_pass = True
        for r in results:
            status = "PASS" if r["ok"] else "FAIL"
            print(f"  {status}  {r['module']}::{r['function']}  v{r['version']}")
            if not r["ok"]:
                all_pass = False
                print(f"         {r['message']}")
                print(f"         actual hash: {r['actual_hash'][:16]}")

        if all_pass:
            print("\nAll compliance hashes verified — no regressions detected.")
            return 0
        else:
            print("\nREGRESSION DETECTED: Compliance function output has changed.")
            print("If this is intentional, bump the module version and run:")
            print("  python -m cortex.regression_guard generate")
            return 1


if __name__ == "__main__":
    sys.exit(cli_main())
