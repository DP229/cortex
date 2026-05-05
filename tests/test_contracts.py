"""
T2 Test: contracts.py  -  Behavioral Contract Enforcement

All tests use stdlib unittest — no external dependencies.
"""

import unittest
from typing import List, Dict, Optional, Tuple, Union, Any

from cortex.contracts import (
    behavioral_contract,
    ContractViolationError,
    validate_against_type_hint,
)


class TestValidateAgainstTypeHint(unittest.TestCase):
    def test_validate_str(self):
        self.assertTrue(validate_against_type_hint("hello", str, "test"))
        self.assertFalse(validate_against_type_hint(42, str, "test"))

    def test_validate_int(self):
        self.assertTrue(validate_against_type_hint(42, int, "test"))
        self.assertFalse(validate_against_type_hint("42", int, "test"))

    def test_validate_float(self):
        self.assertTrue(validate_against_type_hint(3.14, float, "test"))
        self.assertFalse(validate_against_type_hint(42, float, "test"))

    def test_validate_bool(self):
        self.assertTrue(validate_against_type_hint(True, bool, "test"))
        self.assertFalse(validate_against_type_hint(1, bool, "test"))

    def test_validate_optional(self):
        self.assertTrue(validate_against_type_hint(None, Optional[str], "test"))
        self.assertTrue(validate_against_type_hint("hello", Optional[str], "test"))
        self.assertFalse(validate_against_type_hint(42, Optional[str], "test"))

    def test_validate_union(self):
        self.assertTrue(validate_against_type_hint("hello", Union[str, int], "test"))
        self.assertTrue(validate_against_type_hint(42, Union[str, int], "test"))
        self.assertFalse(validate_against_type_hint(3.14, Union[str, int], "test"))

    def test_validate_list_of_str(self):
        self.assertTrue(validate_against_type_hint(["a", "b"], List[str], "test"))
        self.assertFalse(validate_against_type_hint([1, 2], List[str], "test"))

    def test_validate_list_no_args(self):
        self.assertTrue(validate_against_type_hint([1, "a", True], list, "test"))

    def test_validate_dict(self):
        self.assertTrue(validate_against_type_hint({"a": 1}, dict, "test"))
        self.assertFalse(validate_against_type_hint("not_dict", dict, "test"))

    def test_validate_none(self):
        self.assertTrue(validate_against_type_hint(None, type(None), "test"))
        self.assertFalse(validate_against_type_hint("not_none", type(None), "test"))

    def test_validate_tuple(self):
        self.assertTrue(validate_against_type_hint((1, 2), tuple, "test"))
        self.assertFalse(validate_against_type_hint([1, 2], tuple, "test"))


class TestBehavioralContractDecorator(unittest.TestCase):
    def test_valid_call_passes_through(self):
        @behavioral_contract()
        def f(x: str) -> str:
            return x + "!"

        self.assertEqual(f("hello"), "hello!")

    def test_bad_param_type_raises(self):
        @behavioral_contract()
        def f(x: int) -> int:
            return x * 2

        with self.assertRaises(ContractViolationError) as ctx:
            f("not_int")
        self.assertIn("param", str(ctx.exception))
        self.assertIn("type", ctx.exception.contract)

    def test_bad_return_type_raises(self):
        @behavioral_contract()
        def f(x: int) -> str:
            return 42

        with self.assertRaises(ContractViolationError) as ctx:
            f(1)
        loc = ctx.exception.location.lower()
        self.assertTrue("return" in loc or "return" in str(ctx.exception).lower())

    def test_pre_condition_blocks_invalid_input(self):
        @behavioral_contract(pre=lambda x: x > 0)
        def f(x: int) -> int:
            return x * 2

        self.assertEqual(f(5), 10)
        with self.assertRaises(ContractViolationError) as ctx:
            f(-1)
        self.assertIn("Pre-condition", str(ctx.exception))

    def test_pre_condition_evaluation_error_raises(self):
        @behavioral_contract(pre=lambda x: x["missing_key"])
        def f(x: dict) -> dict:
            return x

        with self.assertRaises(ContractViolationError) as ctx:
            f({})
        self.assertIn("Pre-condition", str(ctx.exception))

    def test_post_condition_blocks_bad_output(self):
        @behavioral_contract(post=lambda x, _return: _return > x)
        def f(x: int) -> int:
            return x - 1

        with self.assertRaises(ContractViolationError) as ctx:
            f(5)
        self.assertIn("Post-condition", str(ctx.exception))

    def test_post_condition_evaluation_error_raises(self):
        @behavioral_contract(post=lambda x, _return: _return["bad"])
        def f(x: int) -> int:
            return 42

        with self.assertRaises(ContractViolationError) as ctx:
            f(1)
        self.assertIn("Post-condition", str(ctx.exception))

    def test_invariant_violation_raises(self):
        @behavioral_contract(invariants=[lambda r: r > 0])
        def f(x: int) -> int:
            return x

        self.assertEqual(f(5), 5)
        with self.assertRaises(ContractViolationError) as ctx:
            f(-5)
        self.assertIn("Invariant", str(ctx.exception))

    def test_invariant_evaluation_error_raises(self):
        @behavioral_contract(invariants=[lambda r: r.invalid_attr])
        def f(x: int) -> int:
            return x

        with self.assertRaises(ContractViolationError) as ctx:
            f(1)
        self.assertIn("Invariant", str(ctx.exception))

    def test_multiple_invariants_all_checked(self):
        @behavioral_contract(invariants=[
            lambda r: r > 0,
            lambda r: r < 100,
            lambda r: r % 2 == 0,
        ])
        def f(x: int) -> int:
            return x * 2

        self.assertEqual(f(10), 20)
        with self.assertRaises(ContractViolationError) as ctx:
            f(51)
        self.assertIn("Invariant", str(ctx.exception))

    def test_kwargs_work_with_contracts(self):
        @behavioral_contract(pre=lambda name, age: len(name) > 0 and age >= 0)
        def greet(name: str, age: int) -> str:
            return f"{name} is {age}"

        self.assertEqual(greet(name="Jack", age=30), "Jack is 30")
        with self.assertRaises(ContractViolationError):
            greet(name="", age=30)
        with self.assertRaises(ContractViolationError):
            greet(name="Jack", age=-1)

    def test_optional_params_accepted(self):
        @behavioral_contract()
        def f(x: Optional[int]) -> Optional[int]:
            return x

        self.assertEqual(f(5), 5)
        self.assertIsNone(f(None))

    def test_contract_does_not_mutate_return(self):
        @behavioral_contract(invariants=[lambda r: isinstance(r, dict)])
        def f() -> dict:
            return {"a": 1}

        result = f()
        self.assertEqual(result, {"a": 1})

    def test_list_return_with_type_hint(self):
        @behavioral_contract()
        def f() -> List[int]:
            return [1, 2, 3]

        self.assertEqual(f(), [1, 2, 3])


class TestContractViolationError(unittest.TestCase):
    def test_to_evidence(self):
        err = ContractViolationError(
            "Type mismatch",
            contract="pre",
            location="test.func:param:x",
            details={"expected": "str", "actual": "int"},
        )
        evidence = err.to_evidence()
        self.assertEqual(evidence["error"], "contract_violation")
        self.assertEqual(evidence["contract"], "pre")
        self.assertEqual(evidence["location"], "test.func:param:x")
        self.assertEqual(evidence["message"], "Type mismatch")
        self.assertIn("int", evidence["details"])

    def test_default_details_none(self):
        err = ContractViolationError("msg", contract="post", location="x")
        evidence = err.to_evidence()
        self.assertIsNone(evidence["details"])


if __name__ == "__main__":
    unittest.main()
