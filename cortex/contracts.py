"""
Behavioral Contracts  -  T2 Compliance Pre/Post-condition Enforcement

Every public compliance function gets a @behavioral_contract decorator.
The decorator validates:
  - pre:  Input type, range, non-null constraints (stdlib isinstance + custom)
  - post: Output type, range, non-null constraints
  - invariants: Properties that must hold after the call

Contracts are compiled once at import time (zero overhead after startup).
No external dependencies — stdlib only for deterministic reproducibility.
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union, Tuple, Type, get_type_hints, get_origin, get_args
import builtins
import logging

logger = logging.getLogger("cortex.t2.contracts")


class ContractViolationError(Exception):
    def __init__(self, message: str, contract: str, location: str, details: Any = None):
        super().__init__(message)
        self.contract = contract
        self.location = location
        self.details = details

    def to_evidence(self) -> dict:
        return {
            "error": "contract_violation",
            "contract": self.contract,
            "location": self.location,
            "message": str(self),
            "details": str(self.details) if self.details else None,
        }


_TYPE_NAME_MAP = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
    tuple: "tuple",
    type(None): "NoneType",
}


def _type_name(tp: Any) -> str:
    origin = get_origin(tp) or tp
    if origin in _TYPE_NAME_MAP:
        return _TYPE_NAME_MAP[origin]
    return getattr(origin, "__name__", str(origin))


def validate_against_type_hint(value: Any, hint: Any, label: str) -> bool:
    """Validate a value against a type hint using stdlib only. Returns True if valid, False otherwise."""
    if hint is inspect.Parameter.empty:
        return True

    origin = get_origin(hint)
    args = get_args(hint)

    if origin is type(None):
        if value is not None:
            logger.error("type_violation", extra={"label": label, "expected": "None", "actual": type(value).__name__})
            return False
        return True

    if origin is Optional:
        if value is None:
            return True
        inner = args[0]
        return validate_against_type_hint(value, inner, label)

    if origin is Union:
        for sub in args:
            if validate_against_type_hint(value, sub, label):
                return True
        logger.error("type_violation", extra={"label": label, "expected": str(hint), "actual": type(value).__name__})
        return False

    if origin in (list, List):
        if not isinstance(value, list):
            logger.error("type_violation", extra={"label": label, "expected": "list", "actual": type(value).__name__})
            return False
        if args:
            for idx, item in enumerate(value):
                if not validate_against_type_hint(item, args[0], f"{label}[{idx}]"):
                    return False
        return True

    if origin in (dict, Dict):
        if not isinstance(value, dict):
            logger.error("type_violation", extra={"label": label, "expected": "dict", "actual": type(value).__name__})
            return False
        if args and len(args) >= 2:
            for k, v in value.items():
                if not validate_against_type_hint(k, args[0], f"{label}.key"):
                    return False
                if not validate_against_type_hint(v, args[1], f"{label}[{k}]"):
                    return False
        return True

    if origin in (tuple, Tuple):
        if not isinstance(value, tuple):
            logger.error("type_violation", extra={"label": label, "expected": "tuple", "actual": type(value).__name__})
            return False
        return True

    try:
        if isinstance(hint, type):
            ok = isinstance(value, hint)
            if not ok:
                logger.error("type_violation", extra={"label": label, "expected": hint.__name__, "actual": type(value).__name__})
            return ok
    except TypeError:
        pass

    return True


def behavioral_contract(
    *,
    pre: Optional[Callable[..., bool]] = None,
    post: Optional[Callable[..., bool]] = None,
    invariants: Optional[List[Callable[[Any], bool]]] = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        hints = get_type_hints(func)
        param_names = list(sig.parameters.keys())
        return_hint = hints.get("return")

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = f"{func.__module__}.{func.__qualname__}"

            bound = dict(zip(param_names, args))
            bound.update(kwargs)

            for name, hint in hints.items():
                if name == "return":
                    continue
                if name in bound:
                    if not validate_against_type_hint(bound[name], hint, f"{func_name}:param:{name}"):
                        raise ContractViolationError(
                            f"Type violation at param '{name}' in {func_name}",
                            contract="type_validation",
                            location=f"{func_name}:param:{name}",
                            details={"param": name, "expected": _type_name(hint), "actual": _type_name(type(bound[name]))},
                        )

            if pre is not None:
                try:
                    if not pre(**bound):
                        raise ContractViolationError(
                            f"Pre-condition failed for {func_name}",
                            contract="pre",
                            location=func_name,
                            details=bound,
                        )
                except Exception as exc:
                    raise ContractViolationError(
                        f"Pre-condition evaluation error for {func_name}: {exc}",
                        contract="pre",
                        location=func_name,
                        details=str(exc),
                    )

            result = func(*args, **kwargs)

            if return_hint is not None:
                if not validate_against_type_hint(result, return_hint, f"{func_name}:return"):
                    raise ContractViolationError(
                        f"Return type violation in {func_name}",
                        contract="type_validation",
                        location=f"{func_name}:return",
                        details={"expected": _type_name(return_hint), "actual": _type_name(type(result))},
                    )

            if invariants:
                for idx, invariant in enumerate(invariants):
                    try:
                        if not invariant(result):
                            raise ContractViolationError(
                                f"Invariant #{idx} failed for {func_name}",
                                contract="invariant",
                                location=func_name,
                                details={"invariant_index": idx},
                            )
                    except Exception as exc:
                        raise ContractViolationError(
                            f"Invariant #{idx} evaluation error for {func_name}: {exc}",
                            contract="invariant",
                            location=func_name,
                            details={"invariant_index": idx, "error": str(exc)},
                        )

            if post is not None:
                try:
                    eval_context = {**bound, "_return": result}
                    if not post(**eval_context):
                        raise ContractViolationError(
                            f"Post-condition failed for {func_name}",
                            contract="post",
                            location=func_name,
                            details=eval_context,
                        )
                except Exception as exc:
                    raise ContractViolationError(
                        f"Post-condition evaluation error for {func_name}: {exc}",
                        contract="post",
                        location=func_name,
                        details=str(exc),
                    )

            return result

        return wrapper

    return decorator
