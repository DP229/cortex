"""
Deterministic Fault Injection Harness  -  T2 Behavioral Verification

Simulates hardware/data/environment faults during compliance operations
to prove graceful degradation at predictable boundaries.

Fault scenarios:
  truncated_file      - Source file shorter than expected
  corrupted_embedding  - Bit flips in embedding vectors
  malformed_requirement - Syntactically invalid requirement tag
  sql_injection_string  - Malicious SQL in input fields
  clock_skew           - System clock jumped backward
  key_rotation_mid_write - Audit signing key rotates during write
  partial_crash        - Sub-module returns None unexpectedly
  empty_knowledgebase  - Zero articles in KB (cold-start path)

Usage:
  injector = FaultInjector([FaultScenario.TRUNCATED_FILE])
  with injector.active(operation="validate", context={"path": "test.md"}):
      result = quoter.validate("output text...")
  # After the block: fault state restored, audit event logged.
"""

from __future__ import annotations

import contextlib
import enum
import logging
import threading
import time
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from collections.abc import Generator

logger = logging.getLogger("cortex.t2.fault_injector")


class FaultScenario(str, enum.Enum):
    TRUNCATED_FILE = "truncated_file"
    CORRUPTED_EMBEDDING = "corrupted_embedding"
    MALFORMED_REQUIREMENT = "malformed_requirement"
    SQL_INJECTION_STRING = "sql_injection_string"
    CLOCK_SKEW = "clock_skew"
    KEY_ROTATION_MID_WRITE = "key_rotation_mid_write"
    PARTIAL_CRASH = "partial_crash"
    EMPTY_KNOWLEDGEBASE = "empty_knowledgebase"


SCENARIO_DOCS: Dict[FaultScenario, str] = {
    FaultScenario.TRUNCATED_FILE: "Source file or article truncated to 0 or partial bytes",
    FaultScenario.CORRUPTED_EMBEDDING: "Random bit-flips applied to embedding vectors before comparison",
    FaultScenario.MALFORMED_REQUIREMENT: "Requirement tag missing closing bracket or contains invalid XML",
    FaultScenario.SQL_INJECTION_STRING: "Input field contains SQL injection payload",
    FaultScenario.CLOCK_SKEW: "os.clock_gettime / time.time() reports time N days in the past",
    FaultScenario.KEY_ROTATION_MID_WRITE: "Audit signing key rotates between commit() and finalize()",
    FaultScenario.PARTIAL_CRASH: "A dependent sub-module returns None instead of expected object",
    FaultScenario.EMPTY_KNOWLEDGEBASE: "Knowledge base has zero articles (cold-start path)",
}


@dataclass
class FaultEvent:
    scenario: FaultScenario
    operation: str
    context: dict
    timestamp: str = field(default_factory=lambda: str(time.time()))
    elapsed_ms: int = 0
    exception_type: str = ""
    exception_message: str = ""
    safe_degradation: bool = False

    def to_evidence(self) -> dict:
        return {
            "scenario": self.scenario.value,
            "operation": self.operation,
            "context": self.context,
            "timestamp": self.timestamp,
            "elapsed_ms": self.elapsed_ms,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message[:500],
            "safe_degradation": self.safe_degradation,
        }


class FaultInjectionError(Exception):
    pass


class FaultInjector:
    def __init__(self, scenarios: Optional[List[FaultScenario]] = None):
        self._active_scenarios: Set[FaultScenario] = set(scenarios or [])
        self._lock = threading.RLock()
        self._events: List[FaultEvent] = []
        self._original_time: Optional[Callable[..., float]] = None

    @property
    def active(self) -> Set[FaultScenario]:
        with self._lock:
            return set(self._active_scenarios)

    def add(self, scenario: FaultScenario) -> None:
        with self._lock:
            self._active_scenarios.add(scenario)

    def remove(self, scenario: FaultScenario) -> None:
        with self._lock:
            self._active_scenarios.discard(scenario)

    def clear(self) -> None:
        with self._lock:
            self._active_scenarios.clear()

    @contextlib.contextmanager
    def inject(
        self,
        operation: str,
        context: Optional[dict] = None,
    ) -> Generator[None, None, None]:
        ctx = context or {}
        event = FaultEvent(scenario=FaultScenario.EMPTY_KNOWLEDGEBASE, operation=operation, context=ctx)
        start = time.time()

        try:
            self._apply_faults()
            yield
        except Exception as exc:
            event.exception_type = type(exc).__name__
            event.exception_message = str(exc)
            from cortex.deterministic_core import HashMismatchError
            from cortex.contracts import ContractViolationError
            event.safe_degradation = isinstance(exc, (HashMismatchError, ContractViolationError, ValueError, TypeError))
            raise
        finally:
            self._restore_state()
            event.elapsed_ms = int((time.time() - start) * 1000)
            with self._lock:
                self._events.append(event)
            logger.info(
                "fault_injection_complete",
                extra={
                    "operation": operation,
                    "scenario": event.scenario.value,
                    "elapsed_ms": event.elapsed_ms,
                    "exception": event.exception_type or "none",
                },
            )

    def _apply_faults(self) -> None:
        active = self.active

        if FaultScenario.CLOCK_SKEW in active:
            self._original_time = time.time
            skew = 86400 * 30
            time.time = lambda: self._original_time() - skew  # type: ignore[assignment]
            os.environ["CORTEX_FAULT_CLOCK_SKEW"] = str(skew)

        if FaultScenario.TRUNCATED_FILE in active:
            os.environ["CORTEX_FAULT_TRUNCATED_FILE"] = "1"
        if FaultScenario.CORRUPTED_EMBEDDING in active:
            os.environ["CORTEX_FAULT_CORRUPTED_EMBEDDING"] = "1"
        if FaultScenario.MALFORMED_REQUIREMENT in active:
            os.environ["CORTEX_FAULT_MALFORMED_REQUIREMENT"] = "1"
        if FaultScenario.SQL_INJECTION_STRING in active:
            os.environ["CORTEX_FAULT_SQL_INJECTION"] = "1"
        if FaultScenario.KEY_ROTATION_MID_WRITE in active:
            os.environ["CORTEX_FAULT_KEY_ROTATION"] = "1"
        if FaultScenario.PARTIAL_CRASH in active:
            os.environ["CORTEX_FAULT_PARTIAL_CRASH"] = "1"
        if FaultScenario.EMPTY_KNOWLEDGEBASE in active:
            os.environ["CORTEX_FAULT_EMPTY_KB"] = "1"

    def _restore_state(self) -> None:
        if self._original_time is not None:
            time.time = self._original_time  # type: ignore[assignment]
            self._original_time = None
        for var in (
            "CORTEX_FAULT_CLOCK_SKEW",
            "CORTEX_FAULT_TRUNCATED_FILE",
            "CORTEX_FAULT_CORRUPTED_EMBEDDING",
            "CORTEX_FAULT_MALFORMED_REQUIREMENT",
            "CORTEX_FAULT_SQL_INJECTION",
            "CORTEX_FAULT_KEY_ROTATION",
            "CORTEX_FAULT_PARTIAL_CRASH",
            "CORTEX_FAULT_EMPTY_KB",
        ):
            os.environ.pop(var, None)

    def get_events(self) -> List[FaultEvent]:
        with self._lock:
            return list(self._events)

    @classmethod
    def create_sql_injection_payload(cls) -> str:
        return "' OR 1=1; DROP TABLE users; --"

    @classmethod
    def create_malformed_requirement(cls) -> str:
        return "<req id='001' SIL='4' status='open'"

    @classmethod
    def create_corrupted_embedding(cls, vector: List[float]) -> List[float]:
        import random
        corrupted = list(vector)
        for i in range(len(corrupted)):
            if random.random() < 0.1:
                corrupted[i] = -corrupted[i]
        return corrupted

    @classmethod
    def all_scenarios(cls) -> List[FaultScenario]:
        return list(FaultScenario)
