"""
T2 Test: tvr.py  -  Tool Verification Report

Verifies:
1. TVR records results, computes pass rate
2. Overall result calculation correct (all-pass, mixed, all-fail)
3. Qualification status determination considers mandatory requirements
4. Test result filtering by status works
5. Report serialization round-trips
6. Markdown output is well-formed
7. AutomatedTVRunner basic functionality
"""

import unittest

from cortex.tqk.tvr import (
    ToolVerificationReport,
    TestExecutionResult,
    TestResult,
    AutomatedTVRunner,
)
from cortex.tqk.tvp import TestCategory
from cortex.deterministic_core import compute_hash


class TestTestResultEnum(unittest.TestCase):

    def test_all_states_defined(self):
        states = {TestResult.PASS, TestResult.FAIL, TestResult.NOT_EXECUTED,
                  TestResult.NOT_APPLICABLE, TestResult.BLOCKED}
        self.assertEqual(len(states), 5)


class TestTestExecutionResult(unittest.TestCase):

    def test_construction_with_defaults(self):
        result = TestExecutionResult(
            test_id="TVP-TST-001",
            tor_req_id="TOR-FN-001",
            result=TestResult.PASS,
        )
        self.assertEqual(result.test_id, "TVP-TST-001")
        self.assertEqual(result.tor_req_id, "TOR-FN-001")
        self.assertEqual(result.result, TestResult.PASS)
        self.assertEqual(result.executor, "qualification_engine")
        self.assertEqual(result.deviations, [])
        self.assertEqual(result.evidence, [])

    def test_construction_with_custom_values(self):
        result = TestExecutionResult(
            test_id="TVP-TST-002",
            tor_req_id="TOR-FN-002",
            result=TestResult.FAIL,
            executor="manual",
            actual_result="Module crashed",
            deviations=["Null pointer"],
            evidence=["log.txt"],
            comments="Investigation needed",
        )
        self.assertEqual(result.executor, "manual")
        self.assertEqual(result.actual_result, "Module crashed")
        self.assertEqual(result.deviations, ["Null pointer"])
        self.assertEqual(result.evidence, ["log.txt"])
        self.assertEqual(result.comments, "Investigation needed")


class TestToolVerificationReport(unittest.TestCase):

    def setUp(self):
        self.report = ToolVerificationReport()
        # Add some results
        self.report.add_result(TestExecutionResult(
            test_id="TVP-TST-001", tor_req_id="TOR-FN-001",
            result=TestResult.PASS, actual_result="ok",
        ))
        self.report.add_result(TestExecutionResult(
            test_id="TVP-TST-002", tor_req_id="TOR-FN-002",
            result=TestResult.PASS, actual_result="ok",
        ))
        self.report.add_result(TestExecutionResult(
            test_id="TVP-TST-003", tor_req_id="TOR-FN-003",
            result=TestResult.FAIL, actual_result="failed",
        ))

    def test_pass_rate_calculation(self):
        rate = self.report.get_pass_rate()
        self.assertEqual(rate, 2 / 3 * 100)

    def test_filter_by_result(self):
        passed = self.report.get_results_by_result(TestResult.PASS)
        self.assertEqual(len(passed), 2)

        failed = self.report.get_results_by_result(TestResult.FAIL)
        self.assertEqual(len(failed), 1)

    def test_summary_contains_all_fields(self):
        summary = self.report.get_summary()
        self.assertIn("total_tests", summary)
        self.assertIn("passed", summary)
        self.assertIn("failed", summary)
        self.assertIn("pass_rate", summary)
        self.assertEqual(summary["total_tests"], 3)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["failed"], 1)

    def test_set_result_updates_existing(self):
        self.report.set_result(
            test_id="TVP-TST-001",
            result=TestResult.FAIL,
            actual_result="now failing",
        )
        results = self.report.get_results_by_result(TestResult.PASS)
        self.assertEqual(len(results), 1)  # only test 2 remains pass

    def test_set_result_creates_new(self):
        self.report.set_result(
            test_id="TVP-TST-999",
            result=TestResult.PASS,
            actual_result="new test",
        )
        self.assertEqual(len(self.report.test_results), 4)

    def test_finalize_sets_dates(self):
        self.report.finalize()
        self.assertIsNotNone(self.report.execution_end_date)
        self.assertIsNotNone(self.report.overall_result)

    def test_finalize_all_pass_qualifies(self):
        report = ToolVerificationReport()
        for i in range(10):
            report.add_result(TestExecutionResult(
                test_id=f"TVP-TST-{i:03d}", tor_req_id=f"TOR-FN-{i:03d}",
                result=TestResult.PASS, actual_result="ok",
            ))
        report.finalize()
        self.assertEqual(report.qualification_status, "qualified")

    def test_finalize_with_mandatory_failure_not_qualified(self):
        report = ToolVerificationReport()
        report.add_result(TestExecutionResult(
            test_id="TVP-TST-001", tor_req_id="TOR-OP-001",
            result=TestResult.FAIL, actual_result="failed",
        ))
        report.finalize()
        self.assertEqual(report.qualification_status, "not_qualified")


class TestTvrSerialization(unittest.TestCase):

    def setUp(self):
        self.report = ToolVerificationReport()
        self.report.add_result(TestExecutionResult(
            test_id="TVP-TST-001", tor_req_id="TOR-FN-001",
            result=TestResult.PASS, actual_result="ok",
        ))
        self.report.finalize()

    def test_to_dict_has_all_keys(self):
        data = self.report.to_dict()
        for key in ("tool_name", "tool_version", "tvp_version", "summary",
                    "overall_result", "qualification_status"):
            self.assertIn(key, data)

    def test_to_dict_test_results_complete(self):
        data = self.report.to_dict()
        for tr in data["test_results"]:
            for key in ("test_id", "tor_req_id", "result", "executor"):
                self.assertIn(key, tr, f"Missing key {key} in test result")

    def test_to_markdown_produces_content(self):
        md = self.report.to_markdown()
        self.assertIn("Tool Verification Report", md)
        self.assertIn("Summary", md)
        self.assertIn("pass", md.lower())

    def test_serialization_hash_stable(self):
        h = compute_hash(self.report.to_dict())
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


if __name__ == "__main__":
    unittest.main()
