"""
hash-commit Protocol  -  T2 Compliance Foundation

Every compliance-critical function in Cortex returns a ComplianceResult:
  (output, output_hash, module_version, timestamp)

Key properties:
  1. Given identical inputs, output_hash is stable (deterministic)
  2. Output can be serialized/deserialized with hash verification
  3. Modules declare their semver version so hash changes are auditable
  4. Supports chaining: a downstream module embeds the hash of its upstream input

Evidence lifecycle:
  ComplianceResult  ->  JSON evidence record  ->  Merkle-verified audit entry
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("cortex.t2.deterministic_core")


@dataclass(frozen=True)
class ModuleVersion:
    major: int = 1
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class ComplianceResult:
    output: Any
    output_hash: str
    module: str
    version: ModuleVersion = field(default_factory=ModuleVersion)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_hash: str = ""
    metadata: dict = field(default_factory=dict)

    def to_evidence(self) -> dict:
        return {
            "module": self.module,
            "version": str(self.version),
            "output_hash": self.output_hash,
            "input_hash": self.input_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_evidence(cls, evidence: dict, output: Any) -> "ComplianceResult":
        version_parts = evidence["version"].split(".")
        return cls(
            output=output,
            output_hash=evidence["output_hash"],
            module=evidence["module"],
            version=ModuleVersion(
                major=int(version_parts[0]),
                minor=int(version_parts[1]) if len(version_parts) > 1 else 0,
                patch=int(version_parts[2]) if len(version_parts) > 2 else 0,
            ),
            timestamp=evidence["timestamp"],
            input_hash=evidence.get("input_hash", ""),
            metadata=evidence.get("metadata", {}),
        )


def compute_hash(value: Any) -> str:
    payload = _serialize_for_hashing(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def commit(
    output: Any,
    module: str,
    version: Optional[ModuleVersion] = None,
    input_value: Optional[Any] = None,
    metadata: Optional[dict] = None,
) -> ComplianceResult:
    output_hash = compute_hash(output)
    input_hash = compute_hash(input_value) if input_value is not None else ""
    result = ComplianceResult(
        output=output,
        output_hash=output_hash,
        module=module,
        version=version or ModuleVersion(),
        input_hash=input_hash,
        metadata=metadata or {},
    )
    logger.debug(
        "commit", extra={"module": module, "output_hash": output_hash[:16], "input_hash": input_hash[:16]}
    )
    return result


def verify(result: ComplianceResult) -> bool:
    recomputed = compute_hash(result.output)
    return hmac_safe_compare(recomputed, result.output_hash)


def assert_deterministic(result: ComplianceResult) -> None:
    actual_hash = compute_hash(result.output)
    if not hmac_safe_compare(actual_hash, result.output_hash):
        raise HashMismatchError(
            f"Determinism violation in {result.module}: hash {actual_hash[:16]} != expected {result.output_hash[:16]}",
            expected=result.output_hash,
            actual=actual_hash,
            module=result.module,
        )


class HashMismatchError(AssertionError):
    def __init__(self, message: str, expected: str, actual: str, module: str):
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.module = module

    def to_dict(self) -> dict:
        return {
            "error": "hash_mismatch",
            "module": self.module,
            "expected": self.expected,
            "actual": self.actual,
            "message": str(self),
        }


def hmac_safe_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def _serialize_for_hashing(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return json.dumps(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, default=str)
    if hasattr(value, "to_evidence"):
        return json.dumps(value.to_evidence(), sort_keys=True, default=str)
    if hasattr(value, "__dataclass_fields__"):
        import dataclasses as dc
        return json.dumps(dc.asdict(value), sort_keys=True, default=str)
    return json.dumps(str(value), sort_keys=True)
