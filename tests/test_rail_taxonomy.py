"""
T2 Test: rail_taxonomy.py  -  EN 50128 / EN 50716 Domain Model

Verifies:
1. EN 50128 phases enumerate correctly
2. V-model phase pairings work
3. TraceLinkTypes cover the full V-model
4. DocumentKinds map to rail documents
5. DataQualityRecord computes correctly
6. DataQualityReport aggregates scores
7. RailFunction and SignalType enums exist
8. Downstream/upstream phase traversal
"""

import unittest

from cortex.rail_taxonomy import (
    EN50128Phase,
    TraceLinkType,
    DocumentKind,
    SignalType,
    InterlockingType,
    RailFunction,
    DataQualityRecord,
    DataQualityReport,
    get_downstream_phase,
    get_upstream_phase,
    get_verification_pair,
    V_MODEL_PHASE_PAIRS,
    V_MODEL_DOWNWARD,
)


class TestEN50128Phase(unittest.TestCase):

    def test_all_phases_defined(self):
        phases = list(EN50128Phase)
        self.assertEqual(len(phases), 14)

    def test_phase_values_unique(self):
        names = {p.value for p in EN50128Phase}
        self.assertEqual(len(names), 14)


class TestTraceLinkType(unittest.TestCase):

    def test_v_model_types_present(self):
        types_present = {t.value for t in TraceLinkType}
        for expected in ("specifies", "implements", "verifies",
                         "validates", "allocated_to", "refines"):
            self.assertIn(expected, types_present,
                          f"Missing trace type: {expected}")

    def test_all_types_unique(self):
        names = {t.value for t in TraceLinkType}
        self.assertEqual(len(names), len(list(TraceLinkType)))


class TestDocumentKind(unittest.TestCase):

    def test_rail_documents_exist(self):
        docs = {d.value for d in DocumentKind}
        for expected in ("SRS", "SAS", "SDS", "SVP", "SVR", "HAZ_LOG"):
            self.assertIn(expected, docs, f"Missing doc kind: {expected}")


class TestSignalType(unittest.TestCase):

    def test_signals_defined(self):
        signals = list(SignalType)
        self.assertGreater(len(signals), 0)


class TestInterlockingType(unittest.TestCase):

    def test_types_defined(self):
        types = list(InterlockingType)
        self.assertGreater(len(types), 0)
        self.assertIn(InterlockingType.COMPUTER_BASED, types)


class TestRailFunction(unittest.TestCase):

    def test_safety_functions_present(self):
        funcs = {f.value for f in RailFunction}
        for expected in ("automatic_train_protection", "interlocking",
                         "european_train_control_system"):
            self.assertIn(expected, funcs,
                          f"Missing rail function: {expected}")


class TestDataQualityRecord(unittest.TestCase):

    def test_record_creation(self):
        rec = DataQualityRecord(
            attribute="completeness",
            value=0.85,
            measurement_method="automated_audit",
            measured_at="2026-05-01",
        )
        self.assertEqual(rec.attribute, "completeness")
        self.assertEqual(rec.value, 0.85)
        self.assertTrue(rec.passed)  # 0.85 >= 0.80
        self.assertEqual(len(rec.hash), 64)

    def test_record_fails_below_threshold(self):
        rec = DataQualityRecord(
            attribute="accuracy",
            value=0.70,
            measurement_method="spot_check",
            measured_at="2026-05-01",
        )
        self.assertFalse(rec.passed)

    def test_to_evidence_has_keys(self):
        rec = DataQualityRecord(
            attribute="timeliness",
            value=0.90,
            measurement_method="timestamp_check",
            measured_at="2026-05-01",
        )
        ev = rec.to_evidence()
        for key in ("attribute", "value", "measurement_method",
                    "passed", "hash"):
            self.assertIn(key, ev)


class TestDataQualityReport(unittest.TestCase):

    def test_empty_report(self):
        report = DataQualityReport(
            report_id="DQ-001",
            generated_at="2026-05-01",
            dataset_hash="aaa",
            dataset_size=0,
        )
        self.assertEqual(report.overall_score, 0.0)
        self.assertFalse(report.compliant)

    def test_report_with_records(self):
        records = [
            DataQualityRecord(attribute="completeness", value=0.85,
                              measurement_method="m1", measured_at="2026-01-01"),
            DataQualityRecord(attribute="accuracy", value=0.90,
                              measurement_method="m2", measured_at="2026-01-01"),
            DataQualityRecord(attribute="consistency", value=0.88,
                              measurement_method="m3", measured_at="2026-01-01"),
        ]
        report = DataQualityReport(
            report_id="DQ-002",
            generated_at="2026-05-01",
            dataset_hash="bbb",
            dataset_size=10000,
            records=records,
        )
        avg = (0.85 + 0.90 + 0.88) / 3
        self.assertAlmostEqual(report.overall_score, avg, places=3)
        self.assertTrue(report.compliant)  # > 0.80

    def test_to_evidence_has_keys(self):
        report = DataQualityReport(
            report_id="DQ-003",
            generated_at="2026-05-01",
            dataset_hash="ccc",
            dataset_size=5000,
        )
        ev = report.to_evidence()
        self.assertIn("report_id", ev)
        self.assertIn("overall_score", ev)
        self.assertIn("compliant", ev)
        self.assertIn("hash", ev)

    def test_hash_stable(self):
        report1 = DataQualityReport(
            report_id="DQ-004",
            generated_at="2026-05-01",
            dataset_hash="ddd",
            dataset_size=100,
        )
        report2 = DataQualityReport(
            report_id="DQ-004",
            generated_at="2026-05-01",
            dataset_hash="ddd",
            dataset_size=100,
        )
        self.assertEqual(report1.hash, report2.hash)


class TestVModelTraversal(unittest.TestCase):

    def test_downstream_phase(self):
        ds = get_downstream_phase(EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS)
        self.assertEqual(ds, EN50128Phase.PHASE_2_HAZARD_RISK_ANALYSIS)

    def test_upstream_phase(self):
        us = get_upstream_phase(EN50128Phase.PHASE_8_SOFTWARE_MODULE_DESIGN)
        self.assertEqual(us, EN50128Phase.PHASE_7_SOFTWARE_DESIGN)

    def test_verification_pair(self):
        pair = get_verification_pair(EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS)
        self.assertEqual(pair, EN50128Phase.PHASE_14_SYSTEM_VALIDATION)

    def test_verification_pair_reverse(self):
        pair = get_verification_pair(EN50128Phase.PHASE_14_SYSTEM_VALIDATION)
        self.assertEqual(pair, EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS)

    def test_no_pair_for_hazard(self):
        pair = get_verification_pair(EN50128Phase.PHASE_2_HAZARD_RISK_ANALYSIS)
        self.assertIsNone(pair)

    def test_no_upstream_for_system_requirements(self):
        us = get_upstream_phase(EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS)
        self.assertIsNone(us)

    def test_no_downstream_for_module_design(self):
        ds = get_downstream_phase(EN50128Phase.PHASE_8_SOFTWARE_MODULE_DESIGN)
        self.assertIsNone(ds)


if __name__ == "__main__":
    unittest.main()
