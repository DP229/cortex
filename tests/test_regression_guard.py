"""
T2 Test: regression_guard.py  -  Hash Pinning System

Verifies:
1. HashExpectation serialization round-trips
2. HashExpectationStore loads/saves correctly
3. RegressionGuard registers and verifies expectations
4. Hash mismatch triggers failure
5. Missing expectation triggers failure
6. scan_and_register_compliance_modules works
7. verify_compliance_modules passes after generate
"""

import unittest
import json
import os
import tempfile
from pathlib import Path

from cortex.deterministic_core import compute_hash, ModuleVersion
from cortex.regression_guard import (
    HashExpectation,
    HashExpectationStore,
    RegressionGuard,
)


class TestHashExpectation(unittest.TestCase):

    def test_serialization_round_trip(self):
        exp = HashExpectation(
            module="test.module",
            function="test_fn",
            version="1.0.0",
            input_hash="abc123",
            expected_output_hash="def456",
            last_verified="2026-05-04",
        )
        d = exp.to_dict()
        restored = HashExpectation.from_dict(d)
        self.assertEqual(restored.module, exp.module)
        self.assertEqual(restored.function, exp.function)
        self.assertEqual(restored.expected_output_hash, exp.expected_output_hash)

    def test_default_last_verified(self):
        exp = HashExpectation(
            module="m", function="f", version="0.1.0",
            input_hash="aa", expected_output_hash="bb",
        )
        self.assertEqual(exp.last_verified, "")


class TestHashExpectationStore(unittest.TestCase):

    def test_empty_store(self):
        store = HashExpectationStore()
        self.assertEqual(len(store.expectations), 0)
        self.assertIsNone(store.get("m", "f"))

    def test_set_and_get(self):
        store = HashExpectationStore()
        exp = HashExpectation(
            module="m", function="f", version="1.0.0",
            input_hash="aa", expected_output_hash="bb",
        )
        store.set(exp)
        retrieved = store.get("m", "f")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.expected_output_hash, "bb")

    def test_key_generation(self):
        store = HashExpectationStore()
        self.assertEqual(store.key("a.b", "c"), "a.b::c")

    def test_serialization_round_trip(self):
        store = HashExpectationStore()
        store.set(HashExpectation(
            module="m", function="f", version="1.0.0",
            input_hash="aa", expected_output_hash="bb",
        ))
        store.finalize()
        d = store.to_dict()
        restored = HashExpectationStore.from_dict(d)
        self.assertEqual(len(restored.expectations), 1)
        self.assertIsNotNone(restored.get("m", "f"))
        self.assertEqual(restored.store_hash, store.store_hash)

    def test_finalize_sets_hash(self):
        store = HashExpectationStore()
        store.set(HashExpectation(
            module="m", function="f", version="1.0.0",
            input_hash="aa", expected_output_hash="bb",
        ))
        store.finalize()
        self.assertTrue(len(store.store_hash) > 0)
        self.assertTrue(len(store.generated_at) > 0)


class TestRegressionGuard(unittest.TestCase):

    def setUp(self):
        self.tmp_path = os.path.join(tempfile.mkdtemp(), "expected_hashes.json")
        self.guard = RegressionGuard(store_path=self.tmp_path)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

    def test_register_and_verify_passes(self):
        data = {"key": "value"}
        hash_val = compute_hash(data)
        self.guard.register(
            module="m", function="f",
            version=ModuleVersion(1, 0, 0),
            input_value="input",
            output_value=data,
        )

        ok, actual, msg = self.guard.verify_one(
            module="m", function="f",
            version=ModuleVersion(1, 0, 0),
            output_value=data,
        )
        self.assertTrue(ok)
        self.assertEqual(actual, hash_val)
        self.assertEqual(msg, "OK")

    def test_verify_missing_expectation_fails(self):
        ok, actual, msg = self.guard.verify_one(
            module="m", function="f",
            version=ModuleVersion(1, 0, 0),
            output_value="test",
        )
        self.assertFalse(ok)
        self.assertIn("No expectation", msg)

    def test_verify_hash_mismatch_fails(self):
        self.guard.register(
            module="m", function="f",
            version=ModuleVersion(1, 0, 0),
            output_value="expected_data",
        )
        ok, actual, msg = self.guard.verify_one(
            module="m", function="f",
            version=ModuleVersion(1, 0, 0),
            output_value="different_data",
        )
        self.assertFalse(ok)
        self.assertIn("Hash mismatch", msg)

    def test_verify_all(self):
        regs = [
            ("m", "f1", ModuleVersion(1, 0, 0), "output1"),
            ("m", "f2", ModuleVersion(1, 0, 0), "output2"),
        ]
        for module, fn, ver, out in regs:
            self.guard.register(module, fn, ver, output_value=out)

        ok, results = self.guard.verify_all(regs)
        self.assertTrue(ok)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r["ok"])

    def test_verify_all_with_failure(self):
        self.guard.register(
            "m", "f1", ModuleVersion(1, 0, 0),
            output_value="correct",
        )
        regs = [
            ("m", "f1", ModuleVersion(1, 0, 0), "wrong"),
            ("m", "f2", ModuleVersion(1, 0, 0), "output"),
        ]
        ok, results = self.guard.verify_all(regs)
        self.assertFalse(ok)
        self.assertFalse(results[0]["ok"])
        self.assertFalse(results[1]["ok"])  # f2 has no expectation

    def test_generate_all_persists(self):
        regs = [
            ("m", "f1", ModuleVersion(1, 0, 0), "in", "out1"),
            ("m", "f2", ModuleVersion(1, 0, 0), "in", "out2"),
        ]
        store = self.guard.generate_all(regs)
        self.assertEqual(len(store.expectations), 2)

        guard2 = RegressionGuard(store_path=self.tmp_path)
        self.assertEqual(len(guard2.store.expectations), 2)

    def test_scrape_and_register_populates_store(self):
        count = self.guard.scan_and_register_compliance_modules()
        self.assertGreater(count, 0)
        self.assertGreater(len(self.guard.store.expectations), 0)

    def test_verify_compliance_modules_after_generate(self):
        self.guard.scan_and_register_compliance_modules()
        ok, results = self.guard.verify_compliance_modules()
        # Some modules (qualify, evidence) embed timestamps — they may mismatch
        # across invocations. Verifying deterministic subset passes.
        deterministic = [r for r in results if r["module"] in (
            "cortex.tqk.tor", "cortex.tqk.tvp", "cortex.tqk.tvr",
            "cortex.rail_taxonomy",
        )]
        for r in deterministic:
            self.assertTrue(r["ok"], f"Expected ok for {r['module']}::{r['function']}: {r['message']}")


if __name__ == "__main__":
    unittest.main()
