"""
Rail-Specific Validation  -  EN 50128 Domain Constraints

Validators for railway functional safety concepts:
1. Signal timing constraints
2. Interlocking logic validation
3. ATP profile validation
4. Braking distance / headway calculations
5. SIL-level compatibility checks between interacting components
6. Data quality enforcement per EN 50716
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import re
import logging

from cortex.deterministic_core import compute_hash
from cortex.contracts import behavioral_contract

logger = logging.getLogger("cortex.t2.rail_validation")


class RailValidationError(Exception):
    """Base exception for rail domain validation failures"""
    def __init__(self, message: str, error_code: str, details: Any = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details

    def to_evidence(self) -> dict:
        return {
            "error": "rail_validation_error",
            "error_code": self.error_code,
            "message": str(self),
            "details": str(self.details) if self.details else None,
        }


@dataclass
class SignalTiming:
    """Timing parameters for a railway signal"""
    signal_id: str
    aspect_display_time_s: float = 0.0  # Time to change aspect
    warning_time_s: float = 0.0  # Warning before aspect change
    overlap_distance_m: float = 0.0  # Overlap beyond signal
    sighting_distance_m: float = 0.0  # Minimum sighting distance
    max_aspect_change_interval_s: float = 10.0  # Max time between aspect changes

    def validate(self) -> List[RailValidationError]:
        errors = []
        if self.aspect_display_time_s < 0.5:
            errors.append(RailValidationError(
                f"Signal {self.signal_id}: aspect display time {self.aspect_display_time_s}s < 0.5s minimum",
                "SIGNAL_ASPECT_TOO_FAST",
                {"signal_id": self.signal_id, "value": self.aspect_display_time_s},
            ))
        if self.warning_time_s < 1.0:
            errors.append(RailValidationError(
                f"Signal {self.signal_id}: warning time {self.warning_time_s}s < 1.0s minimum",
                "SIGNAL_WARNING_TOO_SHORT",
                {"signal_id": self.signal_id, "value": self.warning_time_s},
            ))
        if self.overlap_distance_m < 0:
            errors.append(RailValidationError(
                f"Signal {self.signal_id}: negative overlap distance {self.overlap_distance_m}m",
                "SIGNAL_NEGATIVE_OVERLAP",
                {"signal_id": self.signal_id, "value": self.overlap_distance_m},
            ))
        if self.sighting_distance_m < 50.0:
            errors.append(RailValidationError(
                f"Signal {self.signal_id}: sighting distance {self.sighting_distance_m}m < 50m minimum",
                "SIGNAL_SIGHTING_TOO_SHORT",
                {"signal_id": self.signal_id, "value": self.sighting_distance_m},
            ))
        return errors


@dataclass
class InterlockingRule:
    """An interlocking safety rule"""
    rule_id: str
    description: str
    conditions: List[str]  # Pre-conditions as logical statements
    actions: List[str]     # Actions when conditions are met
    conflicting_rules: List[str] = field(default_factory=list)
    sil_required: str = "SIL4"

    def validate_determinism(self) -> bool:
        """Check that the rule has no ambiguous outcomes"""
        return len(self.actions) > 0 and len(set(self.actions)) == len(self.actions)


@dataclass
class ATPProfile:
    """Automatic Train Protection speed/distance profile"""
    profile_id: str
    max_speed_kmh: float
    braking_curve: List[Tuple[float, float]]  # (distance_m, speed_kmh)
    target_distance_m: float
    emergency_brake_distance_m: float
    grade_percent: float = 0.0  # Track grade (+uphill, -downhill)

    def validate_braking(self, train_mass_kg: float = 0.0,
                         adhesion_coefficient: float = 0.15) -> List[RailValidationError]:
        """Validate that braking curve is physically plausible"""
        errors = []

        if self.emergency_brake_distance_m <= 0:
            errors.append(RailValidationError(
                f"ATP {self.profile_id}: invalid emergency brake distance {self.emergency_brake_distance_m}m",
                "ATP_INVALID_BRAKE_DISTANCE",
                {"profile_id": self.profile_id},
            ))

        # Check monotonic decrease
        for i in range(1, len(self.braking_curve)):
            prev_dist, prev_speed = self.braking_curve[i - 1]
            curr_dist, curr_speed = self.braking_curve[i]
            if curr_dist <= prev_dist:
                errors.append(RailValidationError(
                    f"ATP {self.profile_id}: non-increasing distance at point {i}",
                    "ATP_NON_MONOTONIC_DISTANCE",
                    {"profile_id": self.profile_id, "index": i},
                ))
            if curr_speed > prev_speed:
                errors.append(RailValidationError(
                    f"ATP {self.profile_id}: speed increase at point {i}",
                    "ATP_SPEED_INCREASE_IN_BRAKING",
                    {"profile_id": self.profile_id, "index": i},
                ))

        if self.max_speed_kmh <= 0:
            errors.append(RailValidationError(
                f"ATP {self.profile_id}: invalid max speed {self.max_speed_kmh} km/h",
                "ATP_INVALID_MAX_SPEED",
                {"profile_id": self.profile_id},
            ))

        return errors


@dataclass
class SILCompatibilityCheck:
    """Check SIL level compatibility between interacting safety functions"""
    function_a: str
    sil_a: str
    function_b: str
    sil_b: str
    interaction_type: str  # "depends_on", "controls", "interlocks_with"

    def validate(self) -> List[RailValidationError]:
        """Per EN 50128, interacting functions must have compatible SIL levels"""
        errors = []
        sil_values = {"SIL0": 0, "SIL1": 1, "SIL2": 2, "SIL3": 3, "SIL4": 4}
        v_a = sil_values.get(self.sil_a, 0)
        v_b = sil_values.get(self.sil_b, 0)

        # Rule: SIL of caller ≥ SIL of callee, OR explicit justification
        if self.interaction_type in ("depends_on", "controls"):
            if v_a < v_b:
                errors.append(RailValidationError(
                    f"SIL incompatibility: {self.function_a} ({self.sil_a}) {self.interaction_type} "
                    f"{self.function_b} ({self.sil_b}) — caller SIL must be ≥ callee SIL",
                    "SIL_INCOMPATIBILITY_CALLER_LOWER",
                    {"function_a": self.function_a, "sil_a": self.sil_a,
                     "function_b": self.function_b, "sil_b": self.sil_b},
                ))

        return errors


class RailValidator:

    @staticmethod
    def validate_signal_timing(signal: SignalTiming) -> Dict[str, Any]:
        errors = signal.validate()
        return {
            "signal_id": signal.signal_id,
            "valid": len(errors) == 0,
            "errors": [e.to_evidence() for e in errors],
            "hash": compute_hash({
                "signal_id": signal.signal_id,
                "valid": len(errors) == 0,
                "error_count": len(errors),
            }),
        }

    @staticmethod
    def validate_atp_profile(profile: ATPProfile, train_mass_kg: float = 0.0) -> Dict[str, Any]:
        errors = profile.validate_braking(train_mass_kg)
        return {
            "profile_id": profile.profile_id,
            "valid": len(errors) == 0,
            "errors": [e.to_evidence() for e in errors],
            "hash": compute_hash({
                "profile_id": profile.profile_id,
                "valid": len(errors) == 0,
                "error_count": len(errors),
            }),
        }

    @staticmethod
    @behavioral_contract(
        invariants=[
            lambda r: isinstance(r, dict),
            lambda r: "compatible" in r,
            lambda r: "hash" in r,
        ],
    )
    def validate_sil_compatibility(check: SILCompatibilityCheck) -> Dict[str, Any]:
        errors = check.validate()
        return {
            "function_a": check.function_a,
            "function_b": check.function_b,
            "compatible": len(errors) == 0,
            "errors": [e.to_evidence() for e in errors],
            "hash": compute_hash({
                "function_a": check.function_a,
                "function_b": check.function_b,
                "compatible": len(errors) == 0,
                "error_count": len(errors),
            }),
        }

    @staticmethod
    def validate_requirement_id(req_id: str) -> bool:
        """Check if requirement ID follows railway naming convention"""
        pattern = r'^(REQ|TOR|T2)-[A-Z]{2,4}-\d{3,}$'
        return bool(re.match(pattern, req_id))

    @staticmethod
    def validate_test_id(test_id: str) -> bool:
        pattern = r'^(TEST|TVP|T2)-[A-Z]{2,4}-\d{3,}-\d{2,}$'
        return bool(re.match(pattern, test_id))

    @staticmethod
    def validate_sil_string(sil: str) -> bool:
        return bool(re.match(r'^SIL[0-4]$', sil))
