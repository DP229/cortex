"""
T2 Test: ci_qualify.py  -  CI Qualification Runner

Verifies:
1. qualify() returns valid summary with all keys
2. generate_evidence() produces verifiable evidence
3. verify_regression() runs against compliance modules
4. run_all_ci_checks() produces complete report
5. Evidence package includes manifest + files + signature
"""

import unittest
import json
import os
import tempfile
import sys

from cortex.deterministic_core import compute_hash
from cortex.ci_qualify import qualify, generate_evidence, verify_regression, run_all_ci_checks


class TestQualify(unittest.TestCase):

    def test_qualify_returns_dict_with_keys(self):
        passed, summary = qualify("SIL2")
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(summary, dict)
        for key in ("status", "grade", "is_t2_qualified", "test_count",
                    "pass_count", "fail_count", "pass_rate", "package_hash",
                    "run_id", "tor_hash", "tvp_hash", "tvr_hash"):
            self.assertIn(key, summary, f"Missing key: {key}")

    def test_qualify_package_hash_is_valid(self):
        _, summary = qualify("SIL2")
        self.assertEqual(len(summary["package_hash"]), 64)

    def test_qualify_different_sil_different_hash(self):
        _, s1 = qualify("SIL0")
        _, s2 = qualify("SIL4")
        self.assertNotEqual(s1["package_hash"], s2["package_hash"])

    def test_qualify_test_counts_positive(self):
        _, summary = qualify("SIL2")
        self.assertGreater(summary["test_count"], 0)
        self.assertGreaterEqual(summary["pass_count"] + summary["fail_count"],
                                summary["test_count"] / 2)


class TestGenerateEvidence(unittest.TestCase):

    def test_evidence_has_all_sections(self):
        evidence = generate_evidence("SIL2")
        self.assertIn("manifest", evidence)
        self.assertIn("files", evidence)
        self.assertIn("signature", evidence)

    def test_evidence_manifest_has_keys(self):
        evidence = generate_evidence("SIL2")
        m = evidence["manifest"]
        for key in ("version", "generated_at", "sil_target", "run_id",
                    "evidence_count", "qualified", "grade", "package_hash"):
            self.assertIn(key, m, f"Missing manifest key: {key}")

    def test_evidence_has_files(self):
        evidence = generate_evidence("SIL2")
        self.assertGreater(len(evidence["files"]), 0)
        for f in evidence["files"]:
            self.assertIn("name", f)
            self.assertIn("hash", f)
            self.assertIn("size_bytes", f)

    def test_evidence_signature_present(self):
        evidence = generate_evidence("SIL2")
        sig = evidence["signature"]
        self.assertIn("signature", sig)
        self.assertTrue(len(sig["signature"]) > 0)
        self.assertEqual(sig["algorithm"], "HMAC-SHA256")

    def test_evidence_verifies(self):
        evidence = generate_evidence("SIL2")
        from cortex.tqk.t2_evidence import EvidenceCollector
        ok, msg = EvidenceCollector.verify_from_json(json.dumps(evidence))
        self.assertTrue(ok, f"Evidence not verified: {msg}")


class TestVerifyRegression(unittest.TestCase):

    def test_verify_regression_returns_results(self):
        ok, results = verify_regression()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_verify_regression_structure(self):
        ok, results = verify_regression()
        for r in results:
            self.assertIn("module", r)
            self.assertIn("function", r)
            self.assertIn("ok", r)
            self.assertIn("actual_hash", r)
            self.assertIn("message", r)


class TestRunAllCIChecks(unittest.TestCase):

    def test_run_all_returns_report(self):
        overall, report = run_all_ci_checks("SIL2")
        self.assertIsInstance(overall, bool)
        self.assertIsInstance(report, dict)
        self.assertIn("checks", report)
        self.assertIn("overall_pass", report)

    def test_run_all_has_qualification_check(self):
        _, report = run_all_ci_checks("SIL2")
        self.assertIn("qualification", report["checks"])

    def test_run_all_has_regression_check(self):
        _, report = run_all_ci_checks("SIL2")
        self.assertIn("regression_guard", report["checks"])

    def test_run_all_has_evidence_check(self):
        _, report = run_all_ci_checks("SIL2")
        self.assertIn("evidence", report["checks"])

    def test_ci_report_is_json_serializable(self):
        _, report = run_all_ci_checks("SIL2")
        try:
            json.dumps(report)
        except Exception as e:
            self.fail(f"CI report not JSON-serializable: {e}")


if __name__ == "__main__":
    unittest.main()
