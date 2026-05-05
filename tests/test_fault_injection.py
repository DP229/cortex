"""
T2 Test: fault_injector.py  -  Fault Injection Harness

All tests use stdlib unittest — no external dependencies.
"""

import os
import time
import unittest

from cortex.fault_injector import (
    FaultInjector,
    FaultScenario,
    FaultEvent,
    SCENARIO_DOCS,
)


class TestFaultScenarioEnum(unittest.TestCase):
    def test_all_scenarios_defined(self):
        scenarios = FaultInjector.all_scenarios()
        self.assertEqual(len(scenarios), 8)
        for s in scenarios:
            self.assertIsInstance(s, FaultScenario)

    def test_each_scenario_has_doc(self):
        for s in FaultScenario:
            self.assertIn(s, SCENARIO_DOCS, f"Missing doc for {s.value}")
            self.assertGreater(len(SCENARIO_DOCS[s]), 0)


class TestFaultInjectorSetup(unittest.TestCase):
    def test_initial_state_is_empty(self):
        injector = FaultInjector()
        self.assertEqual(len(injector.active), 0)

    def test_add_and_remove_scenario(self):
        injector = FaultInjector()
        injector.add(FaultScenario.TRUNCATED_FILE)
        self.assertIn(FaultScenario.TRUNCATED_FILE, injector.active)
        injector.remove(FaultScenario.TRUNCATED_FILE)
        self.assertNotIn(FaultScenario.TRUNCATED_FILE, injector.active)

    def test_clear(self):
        injector = FaultInjector()
        injector.add(FaultScenario.TRUNCATED_FILE)
        injector.add(FaultScenario.CLOCK_SKEW)
        injector.clear()
        self.assertEqual(len(injector.active), 0)

    def test_duplicate_add_no_effect(self):
        injector = FaultInjector()
        injector.add(FaultScenario.CLOCK_SKEW)
        injector.add(FaultScenario.CLOCK_SKEW)
        self.assertEqual(len(injector.active), 1)


class TestFaultInjectionApplication(unittest.TestCase):
    def test_clock_skew_applied_and_reverted(self):
        original_time = time.time
        injector = FaultInjector([FaultScenario.CLOCK_SKEW])

        with injector.inject(operation="test_clock_skew"):
            self.assertIsNot(time.time, original_time)
            self.assertIn("CORTEX_FAULT_CLOCK_SKEW", os.environ)

        self.assertIs(time.time, original_time)
        self.assertNotIn("CORTEX_FAULT_CLOCK_SKEW", os.environ)

    def test_environment_variables_set_and_cleared(self):
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        with injector.inject(operation="test_env"):
            self.assertEqual(os.environ.get("CORTEX_FAULT_TRUNCATED_FILE"), "1")
        self.assertNotIn("CORTEX_FAULT_TRUNCATED_FILE", os.environ)

    def test_all_env_vars_cleared_after_injection(self):
        injector = FaultInjector(FaultInjector.all_scenarios())
        with injector.inject(operation="test_all"):
            self.assertIsNotNone(os.environ.get("CORTEX_FAULT_CLOCK_SKEW"))
            self.assertEqual(os.environ.get("CORTEX_FAULT_EMPTY_KB"), "1")

        env_vars = [
            "CORTEX_FAULT_CLOCK_SKEW",
            "CORTEX_FAULT_TRUNCATED_FILE",
            "CORTEX_FAULT_CORRUPTED_EMBEDDING",
            "CORTEX_FAULT_MALFORMED_REQUIREMENT",
            "CORTEX_FAULT_SQL_INJECTION",
            "CORTEX_FAULT_KEY_ROTATION",
            "CORTEX_FAULT_PARTIAL_CRASH",
            "CORTEX_FAULT_EMPTY_KB",
        ]
        for var in env_vars:
            self.assertNotIn(var, os.environ, f"{var} not cleaned up")


class TestFaultEventRecording(unittest.TestCase):
    def test_successful_injection_creates_event(self):
        injector = FaultInjector([FaultScenario.EMPTY_KNOWLEDGEBASE])
        with injector.inject(operation="test_op", context={"path": "/test"}):
            pass

        events = injector.get_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.operation, "test_op")
        self.assertEqual(event.context, {"path": "/test"})
        self.assertEqual(event.exception_type, "")
        self.assertFalse(event.safe_degradation)

    def test_exception_captured_in_event(self):
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        try:
            with injector.inject(operation="test_error"):
                raise ValueError("expected error")
        except ValueError:
            pass

        events = injector.get_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.exception_type, "ValueError")
        self.assertIn("expected error", event.exception_message)

    def test_multiple_injections_accumulate_events(self):
        injector = FaultInjector([FaultScenario.EMPTY_KNOWLEDGEBASE])
        with injector.inject(operation="op1"):
            pass
        with injector.inject(operation="op2"):
            pass
        with injector.inject(operation="op3"):
            pass
        self.assertEqual(len(injector.get_events()), 3)

    def test_event_to_evidence(self):
        event = FaultEvent(
            scenario=FaultScenario.TRUNCATED_FILE,
            operation="test",
            context={},
        )
        evidence = event.to_evidence()
        self.assertEqual(evidence["scenario"], "truncated_file")
        self.assertEqual(evidence["operation"], "test")
        self.assertIn("timestamp", evidence)
        self.assertIn("elapsed_ms", evidence)

    def test_safe_degradation_for_contract_violation(self):
        from cortex.contracts import ContractViolationError
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        try:
            with injector.inject(operation="test_safe"):
                raise ContractViolationError("test", contract="pre", location="x")
        except ContractViolationError:
            pass

        events = injector.get_events()
        self.assertTrue(events[0].safe_degradation)

    def test_safe_degradation_for_hash_mismatch(self):
        from cortex.deterministic_core import HashMismatchError
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        try:
            with injector.inject(operation="test_safe"):
                raise HashMismatchError("test", "a", "b", "m")
        except HashMismatchError:
            pass

        events = injector.get_events()
        self.assertTrue(events[0].safe_degradation)

    def test_safe_degradation_false_for_unknown_error(self):
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        try:
            with injector.inject(operation="test_unsafe"):
                raise RuntimeError("unexpected crash")
        except RuntimeError:
            pass

        events = injector.get_events()
        self.assertFalse(events[0].safe_degradation)


class TestUtilityMethods(unittest.TestCase):
    def test_sql_injection_payload_is_malicious(self):
        payload = FaultInjector.create_sql_injection_payload()
        self.assertIn("DROP TABLE", payload)
        self.assertIn("OR 1=1", payload)

    def test_malformed_requirement_is_incomplete(self):
        req = FaultInjector.create_malformed_requirement()
        self.assertIn("<req", req)
        self.assertIn("id='001'", req)
        self.assertFalse(req.endswith("/>") or req.endswith("</req>"))

    def test_corrupted_embedding_differs(self):
        original = [float(i) / 100 for i in range(200)]
        corrupted = FaultInjector.create_corrupted_embedding(original)
        self.assertNotEqual(corrupted, original)
        self.assertEqual(len(corrupted), len(original))
        for x in corrupted:
            self.assertIsInstance(x, float)

    def test_corrupted_embedding_has_some_differences(self):
        original = [1.0] * 100
        corrupted = FaultInjector.create_corrupted_embedding(original)
        differences = sum(1 for a, b in zip(original, corrupted) if a != b)
        self.assertGreater(differences, 0)


class TestFaultInjectionIntegration(unittest.TestCase):
    def test_multiple_scenarios_applied_simultaneously(self):
        injector = FaultInjector([
            FaultScenario.TRUNCATED_FILE,
            FaultScenario.CORRUPTED_EMBEDDING,
            FaultScenario.EMPTY_KNOWLEDGEBASE,
        ])
        with injector.inject(operation="combined"):
            self.assertEqual(os.environ.get("CORTEX_FAULT_TRUNCATED_FILE"), "1")
            self.assertEqual(os.environ.get("CORTEX_FAULT_CORRUPTED_EMBEDDING"), "1")
            self.assertEqual(os.environ.get("CORTEX_FAULT_EMPTY_KB"), "1")

        self.assertNotIn("CORTEX_FAULT_TRUNCATED_FILE", os.environ)
        self.assertNotIn("CORTEX_FAULT_CORRUPTED_EMBEDDING", os.environ)
        self.assertNotIn("CORTEX_FAULT_EMPTY_KB", os.environ)

    def test_nested_injections_restore_properly(self):
        injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
        with injector.inject(operation="outer"):
            self.assertEqual(os.environ.get("CORTEX_FAULT_TRUNCATED_FILE"), "1")
            injector.add(FaultScenario.EMPTY_KNOWLEDGEBASE)
            with injector.inject(operation="inner"):
                self.assertEqual(os.environ.get("CORTEX_FAULT_EMPTY_KB"), "1")
            self.assertNotIn("CORTEX_FAULT_EMPTY_KB", os.environ)
        self.assertNotIn("CORTEX_FAULT_TRUNCATED_FILE", os.environ)


if __name__ == "__main__":
    unittest.main()
