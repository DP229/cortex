"""
T2 Test: tor.py  -  Tool Operational Requirements

Verifies:
1. TOR generation produces all requirement categories
2. SIL mapping applies correct levels per priority
3. Requirement evidence hashes are stable
4. get_requirement_by_id finds correct requirement
5. Serialization round-trips with SIL fields
6. get_unverified_requirements filters correctly
"""

import unittest

from cortex.tqk.tor import (
    ToolOperationalRequirements,
    TORRequirement,
    RequirementPriority,
    RequirementStatus,
)
from cortex.deterministic_core import compute_hash


class TestToolOperationalRequirements(unittest.TestCase):

    def setUp(self):
        self.tor = ToolOperationalRequirements(tool_class="T2")

    def test_all_categories_present(self):
        self.assertGreater(len(self.tor.operational_requirements), 0)
        self.assertGreater(len(self.tor.functional_requirements), 0)
        self.assertGreater(len(self.tor.performance_requirements), 0)
        self.assertGreater(len(self.tor.interface_requirements), 0)
        self.assertGreater(len(self.tor.environmental_requirements), 0)
        self.assertGreater(len(self.tor.quality_requirements), 0)

    def test_mandatory_requirements_exist(self):
        mandatory = self.tor.get_requirements_by_priority(RequirementPriority.MANDATORY)
        self.assertGreater(len(mandatory), 0)

    def test_all_requirements_have_ids(self):
        for req in self.tor.get_all_requirements():
            self.assertIsNotNone(req.req_id)
            self.assertTrue(len(req.req_id) > 0)

    def test_all_requirements_have_category(self):
        for req in self.tor.get_all_requirements():
            self.assertIn(req.category, (
                "operational", "functional", "performance",
                "interface", "environmental", "quality",
            ))

    def test_get_requirements_by_priority(self):
        for priority in RequirementPriority:
            reqs = self.tor.get_requirements_by_priority(priority)
            for req in reqs:
                self.assertEqual(req.priority, priority)

    def test_get_requirements_by_category(self):
        for category in ("operational", "functional", "performance",
                         "interface", "environmental", "quality"):
            reqs = self.tor.get_requirements_by_category(category)
            for req in reqs:
                self.assertEqual(req.category, category)

    def test_get_requirement_by_id_found(self):
        all_reqs = self.tor.get_all_requirements()
        self.assertGreater(len(all_reqs), 0)
        first_id = all_reqs[0].req_id
        found = self.tor.get_requirement_by_id(first_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.req_id, first_id)

    def test_get_requirement_by_id_not_found(self):
        found = self.tor.get_requirement_by_id("NONEXISTENT-ID-999")
        self.assertIsNone(found)

    def test_get_unverified_returns_all_initially(self):
        unverified = self.tor.get_unverified_requirements()
        self.assertEqual(len(unverified), len(self.tor.get_all_requirements()))

    def test_all_requirements_have_verification_method(self):
        for req in self.tor.get_all_requirements():
            self.assertIn(req.verification_method, ("inspection", "analysis", "test"))


class TestSILMapping(unittest.TestCase):

    def test_sil_mapping_sets_all_levels(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        for req in tor.get_all_requirements():
            self.assertTrue(req.sil_level.startswith("SIL"))
            self.assertIn(req.sil_level, ("SIL0", "SIL1", "SIL2", "SIL3", "SIL4"))

    def test_sil2_mandatory_gets_sil2(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        mandatory = tor.get_requirements_by_priority(RequirementPriority.MANDATORY)
        for req in mandatory:
            self.assertEqual(req.sil_level, "SIL2",
                             f"{req.req_id} priority={req.priority.name} sil={req.sil_level}")

    def test_sil4_desirable_gets_sil2(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL4")
        desirable = tor.get_requirements_by_priority(RequirementPriority.DESIRABLE)
        if desirable:
            for req in desirable:
                self.assertEqual(req.sil_level, "SIL2")

    def test_sil0_all_get_sil0(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL0")
        for req in tor.get_all_requirements():
            self.assertEqual(req.sil_level, "SIL0")


class TestTORRequirement(unittest.TestCase):

    def test_evidence_hash_present(self):
        req = TORRequirement(
            req_id="TEST-001",
            category="functional",
            title="Test Req",
            description="Test description",
            priority=RequirementPriority.MANDATORY,
            verification_method="test",
            acceptance_criteria="Must pass",
        )
        self.assertTrue(len(req.evidence_hash) > 0)
        self.assertEqual(len(req.evidence_hash), 64)

    def test_evidence_hash_stable(self):
        req1 = TORRequirement(
            req_id="TEST-001",
            category="functional",
            title="Test Req",
            description="Test description",
            priority=RequirementPriority.MANDATORY,
            verification_method="test",
            acceptance_criteria="Must pass",
        )
        req2 = TORRequirement(
            req_id="TEST-001",
            category="functional",
            title="Test Req",
            description="Test description",
            priority=RequirementPriority.MANDATORY,
            verification_method="test",
            acceptance_criteria="Must pass",
        )
        self.assertEqual(req1.evidence_hash, req2.evidence_hash)

    def test_evidence_hash_changes_with_content(self):
        req1 = TORRequirement(
            req_id="TEST-001",
            category="functional",
            title="Test Req A",
            description="Desc A",
            priority=RequirementPriority.MANDATORY,
            verification_method="test",
            acceptance_criteria="Must pass",
        )
        req2 = TORRequirement(
            req_id="TEST-001",
            category="functional",
            title="Test Req B",
            description="Desc B",
            priority=RequirementPriority.MANDATORY,
            verification_method="test",
            acceptance_criteria="Must pass",
        )
        self.assertNotEqual(req1.evidence_hash, req2.evidence_hash)


class TestSerialization(unittest.TestCase):

    def test_to_dict_includes_sil_and_evidence_hash(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        tor.apply_sil_mapping("SIL2")
        data = tor.to_dict()
        reqs = data["requirements"]
        for cat, cat_reqs in reqs.items():
            for r in cat_reqs:
                self.assertIn("sil_level", r)
                self.assertIn("evidence_hash", r)
                self.assertTrue(len(r["sil_level"]) > 0)
                self.assertTrue(len(r["evidence_hash"]) > 0)

    def test_to_dict_has_all_top_level_keys(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        data = tor.to_dict()
        for key in ("tool_name", "tool_version", "tool_class", "standards"):
            self.assertIn(key, data)

    def test_to_markdown_produces_content(self):
        tor = ToolOperationalRequirements(tool_class="T2")
        md = tor.to_markdown()
        self.assertIn("Tool Operational Requirements", md)
        self.assertIn("Operational Requirements", md)
        self.assertIn("Functional Requirements", md)

    def test_to_dict_hash_stable(self):
        tor1 = ToolOperationalRequirements(tool_class="T2")
        tor2 = ToolOperationalRequirements(tool_class="T2")
        h1 = compute_hash(tor1.to_dict())
        h2 = compute_hash(tor2.to_dict())
        self.assertEqual(h1, h2, "Identical TOR instances must produce same serialized hash")


if __name__ == "__main__":
    unittest.main()
