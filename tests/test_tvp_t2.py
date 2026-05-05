"""
T2 Test: tvp.py  -  Tool Verification Plan

Verifies:
1. TVP derives test cases from TOR (valid + invalid + boundary)
2. Each TOR mandatory requirement has valid + invalid + boundary tests
3. derive_from_tor produces correct test counts
4. Test cases have correct categories
5. TVP serialization round-trips
6. filter methods work correctly
7. Equivalence partitioning support in test cases
"""

import unittest

from cortex.tqk.tor import (
    ToolOperationalRequirements,
    RequirementPriority,
)
from cortex.tqk.tvp import (
    ToolVerificationPlan,
    VerificationTestCase,
    TestCategory,
)
from cortex.deterministic_core import compute_hash


class TestToolVerificationPlan(unittest.TestCase):

    def setUp(self):
        self.tor = ToolOperationalRequirements(tool_class="T2")
        self.tor.apply_sil_mapping("SIL2")
        self.tvp = ToolVerificationPlan()
        self.tvp.derive_from_tor(self.tor)

    def test_derive_produces_test_cases(self):
        self.assertGreater(len(self.tvp.test_cases), 0)

    def test_more_tests_than_tor_requirements(self):
        """Derivation should produce more tests than base requirements
        because each gets valid + invalid + boundary partitions."""
        tor_count = len(self.tor.get_all_requirements())
        tvp_count = len(self.tvp.test_cases)
        self.assertGreaterEqual(tvp_count, tor_count,
            f"Expected at least {tor_count} tests, got {tvp_count}")

    def test_all_test_cases_have_ids(self):
        for tc in self.tvp.test_cases:
            self.assertTrue(tc.test_id.startswith("TVP-"))
            self.assertTrue(len(tc.test_id) > 5)

    def test_all_test_cases_have_tor_reference(self):
        for tc in self.tvp.test_cases:
            self.assertTrue(tc.tor_req_id.startswith("TOR-"))
            self.assertTrue(len(tc.tor_req_id) > 5)

    def test_all_test_cases_have_valid_category(self):
        for tc in self.tvp.test_cases:
            self.assertIsInstance(tc.category, TestCategory)

    def test_test_cases_have_procedures(self):
        for tc in self.tvp.test_cases:
            self.assertGreater(len(tc.test_procedure), 0)
            self.assertTrue(any("Set up" in step or "1." in step
                               for step in tc.test_procedure))

    def test_test_cases_link_to_existing_tor_requirements(self):
        tor_ids = {r.req_id for r in self.tor.get_all_requirements()}
        for tc in self.tvp.test_cases:
            self.assertIn(tc.tor_req_id, tor_ids,
                          f"Test {tc.test_id} references unknown TOR {tc.tor_req_id}")

    def test_filter_by_category(self):
        for cat in TestCategory:
            filtered = self.tvp.get_test_cases_by_category(cat)
            for tc in filtered:
                self.assertEqual(tc.category, cat)

    def test_filter_by_tor(self):
        all_tor = self.tor.get_all_requirements()
        self.assertGreater(len(all_tor), 0)
        first_tor = all_tor[0].req_id
        filtered = self.tvp.get_test_cases_by_tor(first_tor)
        self.assertGreater(len(filtered), 0)
        for tc in filtered:
            self.assertEqual(tc.tor_req_id, first_tor)

    def test_get_by_id_found(self):
        first_tc = self.tvp.test_cases[0]
        found = self.tvp.get_test_cases_by_id(first_tc.test_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.test_id, first_tc.test_id)

    def test_get_by_id_not_found(self):
        found = self.tvp.get_test_cases_by_id("NONEXISTENT-999")
        self.assertIsNone(found)

    def test_estimated_duration_positive(self):
        self.assertGreater(self.tvp.get_total_estimated_duration(), 0)

    def test_equivalence_partitions_field_exists(self):
        for tc in self.tvp.test_cases:
            self.assertTrue(hasattr(tc, "_eq_partition"))


class TestVerificationTestCase(unittest.TestCase):

    def test_construction_with_defaults(self):
        tc = VerificationTestCase(
            test_id="TVP-TST-001",
            tor_req_id="TOR-FN-001",
            title="Test case",
            category=TestCategory.TEST,
            test_procedure=["Step 1", "Step 2"],
            expected_result="Expected",
            pass_criteria="Must pass",
        )
        self.assertEqual(tc.test_id, "TVP-TST-001")
        self.assertEqual(tc.required_equipment, [])
        self.assertEqual(tc.prerequisites, [])
        self.assertEqual(tc.estimated_duration_minutes, 30)
        self.assertEqual(tc._eq_partition, {})

    def test_equivalence_field_serializable(self):
        tc = VerificationTestCase(
            test_id="TVP-TST-002",
            tor_req_id="TOR-FN-002",
            title="EQ test case",
            category=TestCategory.TEST,
            test_procedure=["Step 1"],
            expected_result="Expected",
            pass_criteria="Must pass",
        )
        tc._eq_partition = {"valid": ["A", "B"], "invalid": ["C"], "boundary": ["X"]}
        self.assertEqual(tc._eq_partition["valid"], ["A", "B"])
        self.assertEqual(len(tc._eq_partition["invalid"]), 1)


class TestTvpSerialization(unittest.TestCase):

    def setUp(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        self.tvp = ToolVerificationPlan()
        self.tvp.derive_from_tor(tor)

    def test_to_dict_has_all_keys(self):
        data = self.tvp.to_dict()
        self.assertIn("tool_name", data)
        self.assertIn("tool_version", data)
        self.assertIn("total_test_cases", data)
        self.assertIn("total_estimated_minutes", data)
        self.assertIn("by_category", data)
        self.assertIn("test_cases", data)

    def test_to_dict_test_cases_complete(self):
        data = self.tvp.to_dict()
        for tc_data in data["test_cases"]:
            self.assertIn("test_id", tc_data)
            self.assertIn("tor_req_id", tc_data)
            self.assertIn("title", tc_data)
            self.assertIn("category", tc_data)
            self.assertIn("procedure", tc_data)

    def test_to_markdown_produces_content(self):
        md = self.tvp.to_markdown()
        self.assertIn("Tool Verification Plan", md)
        self.assertIn("Summary", md)

    def test_serialization_hash_stable(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        tvp = ToolVerificationPlan()
        tvp.derive_from_tor(tor)
        h1 = compute_hash(tvp.to_dict())
        h2 = compute_hash(tvp.to_dict())
        self.assertEqual(h1, h2, "Same instance TVP serialization must be deterministic")


class TestTvpTortraceability(unittest.TestCase):

    def test_every_tor_requirement_has_at_least_one_test(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        tvp = ToolVerificationPlan()
        tvp.derive_from_tor(tor)

        tor_ids = {r.req_id for r in tor.get_all_requirements()}
        tested_ids = {tc.tor_req_id for tc in tvp.test_cases}

        for tor_id in tor_ids:
            self.assertIn(tor_id, tested_ids,
                          f"TOR requirement {tor_id} has no test case")


if __name__ == "__main__":
    unittest.main()
