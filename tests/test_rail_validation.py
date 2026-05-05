"""
T2 Test: rail_validation.py  -  EN 50128 Domain Validators

Verifies:
1. SignalTiming validation catches all boundary violations
2. ATP profile validates braking curves
3. SIL compatibility checks caller/callee rules
4. RailValidator static methods return correctly shaped dicts
5. Contract enforcement on sil_compatibility validate
6. Requirement/test ID validation patterns
7. SIL string validation
"""

import unittest

from cortex.rail_validation import (
    SignalTiming,
    ATPProfile,
    SILCompatibilityCheck,
    RailValidator,
    RailValidationError,
    InterlockingRule,
    # DataQualityReport is defined in rail_taxonomy; rail_validation imports nothing from it
)


class TestSignalTiming(unittest.TestCase):

    def test_valid_signal(self):
        sig = SignalTiming(
            signal_id="SIG-001",
            aspect_display_time_s=2.0,
            warning_time_s=3.0,
            overlap_distance_m=100.0,
            sighting_distance_m=200.0,
        )
        errors = sig.validate()
        self.assertEqual(len(errors), 0)

    def test_too_fast_aspect_change(self):
        sig = SignalTiming(
            signal_id="SIG-002",
            aspect_display_time_s=0.3,
            warning_time_s=3.0,
            overlap_distance_m=100.0,
            sighting_distance_m=200.0,
        )
        errors = sig.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any(e.error_code == "SIGNAL_ASPECT_TOO_FAST" for e in errors))

    def test_negative_overlap(self):
        sig = SignalTiming(
            signal_id="SIG-003",
            aspect_display_time_s=2.0,
            warning_time_s=3.0,
            overlap_distance_m=-5.0,
            sighting_distance_m=200.0,
        )
        errors = sig.validate()
        self.assertTrue(any(e.error_code == "SIGNAL_NEGATIVE_OVERLAP" for e in errors))

    def test_short_sighting(self):
        sig = SignalTiming(
            signal_id="SIG-004",
            aspect_display_time_s=2.0,
            warning_time_s=3.0,
            overlap_distance_m=100.0,
            sighting_distance_m=20.0,
        )
        errors = sig.validate()
        self.assertTrue(any(e.error_code == "SIGNAL_SIGHTING_TOO_SHORT" for e in errors))

    def test_multiple_violations(self):
        sig = SignalTiming(
            signal_id="SIG-005",
            aspect_display_time_s=0.2,  # too fast
            warning_time_s=0.5,         # too short
            overlap_distance_m=-10,     # negative
            sighting_distance_m=30,     # too short
        )
        errors = sig.validate()
        self.assertGreater(len(errors), 2)


class TestATPProfile(unittest.TestCase):

    def test_valid_profile(self):
        profile = ATPProfile(
            profile_id="ATP-001",
            max_speed_kmh=160,
            braking_curve=[(0, 160), (500, 100), (800, 40), (1000, 0)],
            target_distance_m=1000,
            emergency_brake_distance_m=1200,
        )
        errors = profile.validate_braking()
        self.assertEqual(len(errors), 0)

    def test_speed_increase_in_braking(self):
        profile = ATPProfile(
            profile_id="ATP-002",
            max_speed_kmh=160,
            braking_curve=[(0, 100), (500, 120)],  # speed increase
            target_distance_m=500,
            emergency_brake_distance_m=600,
        )
        errors = profile.validate_braking()
        self.assertTrue(any(e.error_code == "ATP_SPEED_INCREASE_IN_BRAKING" for e in errors))

    def test_non_monotonic_distance(self):
        profile = ATPProfile(
            profile_id="ATP-003",
            max_speed_kmh=160,
            braking_curve=[(100, 100), (50, 80)],  # distance decreases
            target_distance_m=500,
            emergency_brake_distance_m=600,
        )
        errors = profile.validate_braking()
        self.assertTrue(any(e.error_code == "ATP_NON_MONOTONIC_DISTANCE" for e in errors))

    def test_invalid_max_speed(self):
        profile = ATPProfile(
            profile_id="ATP-004",
            max_speed_kmh=-50,
            braking_curve=[(0, 0)],
            target_distance_m=100,
            emergency_brake_distance_m=150,
        )
        errors = profile.validate_braking()
        self.assertTrue(any(e.error_code == "ATP_INVALID_MAX_SPEED" for e in errors))


class TestSILCompatibility(unittest.TestCase):

    def test_compatible_sil(self):
        check = SILCompatibilityCheck(
            function_a="ATP", sil_a="SIL4",
            function_b="Signal", sil_b="SIL2",
            interaction_type="controls",
        )
        errors = check.validate()
        self.assertEqual(len(errors), 0)

    def test_incompatible_caller_lower(self):
        check = SILCompatibilityCheck(
            function_a="Monitor", sil_a="SIL1",
            function_b="Brake", sil_b="SIL4",
            interaction_type="controls",
        )
        errors = check.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any(e.error_code == "SIL_INCOMPATIBILITY_CALLER_LOWER"
                           for e in errors))

    def test_equal_sil_compatible(self):
        check = SILCompatibilityCheck(
            function_a="ATP", sil_a="SIL4",
            function_b="ETCS", sil_b="SIL4",
            interaction_type="interlocks_with",
        )
        errors = check.validate()
        self.assertEqual(len(errors), 0)


class TestRailValidator(unittest.TestCase):

    def test_validate_signal_timing(self):
        sig = SignalTiming(
            signal_id="SIG-VAL-001",
            aspect_display_time_s=2.0,
            warning_time_s=3.0,
            overlap_distance_m=100.0,
            sighting_distance_m=200.0,
        )
        result = RailValidator.validate_signal_timing(sig)
        self.assertIn("valid", result)
        self.assertIn("errors", result)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["hash"]), 64)

    def test_validate_atp_profile(self):
        profile = ATPProfile(
            profile_id="ATP-VAL-001",
            max_speed_kmh=160,
            braking_curve=[(0, 160), (500, 100), (1000, 0)],
            target_distance_m=1000,
            emergency_brake_distance_m=1200,
        )
        result = RailValidator.validate_atp_profile(profile)
        self.assertIn("valid", result)
        self.assertTrue(result["valid"])

    def test_validate_sil_compatibility(self):
        check = SILCompatibilityCheck(
            function_a="ATP", sil_a="SIL4",
            function_b="Signal", sil_b="SIL2",
            interaction_type="controls",
        )
        result = RailValidator.validate_sil_compatibility(check)
        self.assertIn("compatible", result)
        self.assertTrue(result["compatible"])
        self.assertIn("hash", result)

    def test_validate_sil_compatibility_with_incompatible(self):
        check = SILCompatibilityCheck(
            function_a="Monitor", sil_a="SIL1",
            function_b="Brake", sil_b="SIL4",
            interaction_type="controls",
        )
        result = RailValidator.validate_sil_compatibility(check)
        self.assertFalse(result["compatible"])


class TestIdValidation(unittest.TestCase):

    def test_valid_req_id(self):
        self.assertTrue(RailValidator.validate_requirement_id("REQ-SIG-001"))
        self.assertTrue(RailValidator.validate_requirement_id("TOR-OP-042"))
        self.assertTrue(RailValidator.validate_requirement_id("T2-QUAL-015"))

    def test_invalid_req_id(self):
        self.assertFalse(RailValidator.validate_requirement_id("abc"))
        self.assertFalse(RailValidator.validate_requirement_id("req-sig-001"))
        self.assertFalse(RailValidator.validate_requirement_id("REQ-1-001"))  # segment too short

    def test_valid_test_id(self):
        self.assertTrue(RailValidator.validate_test_id("TEST-ATP-001-01"))
        self.assertTrue(RailValidator.validate_test_id("T2-TVR-001-99"))

    def test_invalid_test_id(self):
        self.assertFalse(RailValidator.validate_test_id("test-001"))
        self.assertFalse(RailValidator.validate_test_id("TEST-X-001"))

    def test_valid_sil(self):
        self.assertTrue(RailValidator.validate_sil_string("SIL0"))
        self.assertTrue(RailValidator.validate_sil_string("SIL4"))

    def test_invalid_sil(self):
        self.assertFalse(RailValidator.validate_sil_string("SIL5"))
        self.assertFalse(RailValidator.validate_sil_string("SIL"))
        self.assertFalse(RailValidator.validate_sil_string("sil2"))


class TestRailValidationError(unittest.TestCase):

    def test_error_has_code(self):
        err = RailValidationError("msg", "ERR_TEST", {"key": "val"})
        self.assertEqual(err.error_code, "ERR_TEST")
        self.assertEqual(err.details, {"key": "val"})

    def test_to_evidence(self):
        err = RailValidationError("test message", "ERR_CODE")
        ev = err.to_evidence()
        self.assertEqual(ev["error"], "rail_validation_error")
        self.assertEqual(ev["error_code"], "ERR_CODE")
        self.assertIn("test message", ev["message"])


if __name__ == "__main__":
    unittest.main()
