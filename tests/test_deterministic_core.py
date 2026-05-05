"""
T2 Test: deterministic_core.py  -  Hash-Commit Protocol

All tests use stdlib unittest — no external dependencies.
"""

import unittest

from cortex.deterministic_core import (
    compute_hash,
    ComplianceResult,
    ModuleVersion,
    commit,
    verify as verify_hash,
    assert_deterministic,
    HashMismatchError,
    hmac_safe_compare,
)


class TestComputeHash(unittest.TestCase):
    def test_same_input_produces_same_hash(self):
        h1 = compute_hash("hello world")
        h2 = compute_hash("hello world")
        self.assertEqual(h1, h2)

    def test_different_input_produces_different_hash(self):
        h1 = compute_hash("hello world")
        h2 = compute_hash("hello WORLD")
        self.assertNotEqual(h1, h2)

    def test_empty_string_hash_is_stable(self):
        h = compute_hash("")
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_hash_of_int(self):
        h1 = compute_hash(42)
        h2 = compute_hash(42)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_hash_of_float(self):
        h1 = compute_hash(3.14159)
        h2 = compute_hash(3.14159)
        self.assertEqual(h1, h2)

    def test_hash_of_bool(self):
        h1 = compute_hash(True)
        h2 = compute_hash(True)
        self.assertEqual(h1, h2)
        self.assertNotEqual(compute_hash(True), compute_hash(False))

    def test_hash_of_dict_is_deterministic(self):
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}
        self.assertEqual(compute_hash(d1), compute_hash(d2))

    def test_hash_of_list(self):
        l1 = [1, 2, 3]
        l2 = [1, 2, 3]
        self.assertEqual(compute_hash(l1), compute_hash(l2))

    def test_hash_stability_across_100_runs(self):
        inputs = [
            "test string",
            {"key": "value", "num": 42},
            [1, 2, 3, 4, 5],
            "a" * 1000,
            3.141592653589793,
        ]
        for inp in inputs:
            baseline = compute_hash(inp)
            for _ in range(100):
                self.assertEqual(
                    compute_hash(inp), baseline,
                    f"Hash instability for {inp!r}"
                )


class TestComplianceResult(unittest.TestCase):
    def test_to_evidence_and_from_evidence_roundtrip(self):
        result = ComplianceResult(
            output="test_output",
            output_hash="abc123",
            module="test.module",
            version=ModuleVersion(1, 2, 3),
            input_hash="def456",
            metadata={"key": "val"},
        )
        evidence = result.to_evidence()
        restored = ComplianceResult.from_evidence(evidence, output="test_output")
        self.assertEqual(restored.output, result.output)
        self.assertEqual(restored.output_hash, result.output_hash)
        self.assertEqual(restored.module, result.module)
        self.assertEqual(restored.version.major, 1)
        self.assertEqual(restored.version.minor, 2)
        self.assertEqual(restored.version.patch, 3)
        self.assertEqual(restored.input_hash, result.input_hash)
        self.assertEqual(restored.metadata, result.metadata)

    def test_to_evidence_has_all_keys(self):
        result = ComplianceResult(output="x", output_hash="a", module="m")
        evidence = result.to_evidence()
        for key in ("module", "version", "output_hash", "input_hash", "timestamp", "metadata"):
            self.assertIn(key, evidence)


class TestCommitVerification(unittest.TestCase):
    def test_commit_produces_verifiable_result(self):
        output = {"key": "value"}
        result = commit(output, module="test.module")
        self.assertTrue(verify_hash(result))

    def test_commit_with_input_hash(self):
        result = commit("output", module="m", input_value="input")
        self.assertNotEqual(result.input_hash, "")
        self.assertEqual(len(result.input_hash), 64)

    def test_verify_detects_tampering(self):
        output = {"key": "value"}
        result = commit(output, module="test.module")
        tampered = ComplianceResult(
            output="DIFFERENT",
            output_hash=result.output_hash,
            module=result.module,
        )
        self.assertFalse(verify_hash(tampered))

    def test_assert_deterministic_passes_on_good_result(self):
        result = commit("hello", module="m")
        assert_deterministic(result)

    def test_assert_deterministic_raises_on_bad_result(self):
        result = ComplianceResult(output="hello", output_hash="DEADBEEF", module="m")
        with self.assertRaises(HashMismatchError) as ctx:
            assert_deterministic(result)
        self.assertEqual(ctx.exception.expected, "DEADBEEF")
        self.assertEqual(ctx.exception.module, "m")
        self.assertIn("Determinism violation", str(ctx.exception))

    def test_hashmismatch_to_dict(self):
        err = HashMismatchError("msg", "exp", "act", "mod")
        d = err.to_dict()
        self.assertEqual(d["error"], "hash_mismatch")
        self.assertEqual(d["module"], "mod")
        self.assertEqual(d["expected"], "exp")
        self.assertEqual(d["actual"], "act")


class TestHmacSafeCompare(unittest.TestCase):
    def test_equal_strings_compare_true(self):
        self.assertTrue(hmac_safe_compare("abc", "abc"))

    def test_different_strings_compare_false(self):
        self.assertFalse(hmac_safe_compare("abc", "abd"))

    def test_different_lengths_compare_false(self):
        self.assertFalse(hmac_safe_compare("abc", "abcd"))

    def test_empty_strings_equal(self):
        self.assertTrue(hmac_safe_compare("", ""))


class TestModuleVersion(unittest.TestCase):
    def test_str_format(self):
        self.assertEqual(str(ModuleVersion(1, 2, 3)), "1.2.3")
        self.assertEqual(str(ModuleVersion()), "1.0.0")

    def test_default_version(self):
        v = ModuleVersion()
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)


if __name__ == "__main__":
    unittest.main()
