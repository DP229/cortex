"""
Railway Compliance Taxonomy  -  EN 50128 / EN 50716 Domain Model

Defines the document types, lifecycle phases, traceability types,
and data quality attributes required for railway functional safety.

EN 50128 V-model phases:
  System Requirements → Hazard/Risk Analysis → Safety Requirements
    → System Architecture → Software Requirements → Software Architecture
    → Software Design → Module Design → Module Testing
    → Software Integration → Integration Testing
    → Overall Software Testing → System Integration → System Validation

Trace types extend beyond req↔test to the full V-model:
  requirement ↔ design ↔ code ↔ test ↔ verification ↔ validation
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from cortex.deterministic_core import compute_hash


class EN50128Phase(str, Enum):
    """EN 50128 Table A.1 software lifecycle phases"""
    PHASE_1_SYSTEM_REQUIREMENTS = "1_system_requirements"
    PHASE_2_HAZARD_RISK_ANALYSIS = "2_hazard_risk_analysis"
    PHASE_3_SAFETY_REQUIREMENTS = "3_safety_requirements"
    PHASE_4_SYSTEM_ARCHITECTURE = "4_system_architecture"
    PHASE_5_SOFTWARE_REQUIREMENTS = "5_software_requirements"
    PHASE_6_SOFTWARE_ARCHITECTURE = "6_software_architecture"
    PHASE_7_SOFTWARE_DESIGN = "7_software_design"
    PHASE_8_SOFTWARE_MODULE_DESIGN = "8_software_module_design"
    PHASE_9_SOFTWARE_MODULE_TESTING = "9_software_module_testing"
    PHASE_10_SOFTWARE_INTEGRATION = "10_software_integration"
    PHASE_11_SOFTWARE_INTEGRATION_TESTING = "11_software_integration_testing"
    PHASE_12_OVERALL_SOFTWARE_TESTING = "12_overall_software_testing"
    PHASE_13_SYSTEM_INTEGRATION = "13_system_integration"
    PHASE_14_SYSTEM_VALIDATION = "14_system_validation"


class TraceLinkType(str, Enum):
    """EN 50128 traceability link types (full V-model)"""
    SPECIFIES = "specifies"
    ALLOCATED_TO = "allocated_to"
    IMPLEMENTS = "implements"
    VERIFIES = "verifies"
    VALIDATES = "validates"
    DERIVED_FROM = "derived_from"
    REFINES = "refines"
    TRACES_TO = "traces_to"
    CONFLICTS_WITH = "conflicts_with"
    SATISFIES = "satisfies"


class DocumentKind(str, Enum):
    """EN 50128 Annex A document types"""
    SOFTWARE_REQUIREMENTS_SPECIFICATION = "SRS"
    SOFTWARE_ARCHITECTURE_SPECIFICATION = "SAS"
    SOFTWARE_DESIGN_SPECIFICATION = "SDS"
    SOFTWARE_MODULE_SPECIFICATION = "SMS"
    SOFTWARE_VERIFICATION_PLAN = "SVP"
    SOFTWARE_VERIFICATION_REPORT = "SVR"
    SOFTWARE_VALIDATION_PLAN = "SVAP"
    SOFTWARE_VALIDATION_REPORT = "SVAR"
    SOFTWARE_SAFETY_CASE = "SSC"
    HAZARD_LOG = "HAZ_LOG"
    RISK_ASSESSMENT = "RISK_ASMT"
    TOR = "TOR"
    TVP = "TVP"
    TVR = "TVR"
    SOUP_MANIFEST = "SOUP_MANIFEST"
    TOOL_QUALIFICATION_EVIDENCE = "T2_EVIDENCE"
    DATA_QUALITY_REPORT = "DQ_REPORT"


class SignalType(str, Enum):
    """Railway signalling types"""
    MAIN_SIGNAL = "main_signal"
    DISTANT_SIGNAL = "distant_signal"
    COMBINED_SIGNAL = "combined_signal"
    SHUNTING_SIGNAL = "shunting_signal"
    BLOCK_SIGNAL = "block_signal"
    CAB_SIGNAL = "cab_signal"
    BUFFER_STOP = "buffer_stop"
    WARNING_BOARD = "warning_board"


class InterlockingType(str, Enum):
    """Interlocking system types"""
    RELAY_BASED = "relay_based"
    ELECTRONIC = "electronic"
    COMPUTER_BASED = "computer_based"
    SOLID_STATE = "solid_state"


class RailFunction(str, Enum):
    """Safety-critical railway functions"""
    SIGNAL_CONTROL = "signal_control"
    POINT_CONTROL = "point_control"
    TRACK_CIRCUIT = "track_circuit"
    AXLE_COUNTER = "axle_counter"
    LEVEL_CROSSING = "level_crossing"
    ATP = "automatic_train_protection"
    ATO = "automatic_train_operation"
    ATS = "automatic_train_supervision"
    ETCS = "european_train_control_system"
    CBTC = "communications_based_train_control"
    INTERLOCKING = "interlocking"
    PLATFORM_DOOR = "platform_door"
    EMERGENCY_BRAKE = "emergency_brake"


@dataclass
class DataQualityRecord:
    """EN 50716 data quality metadata for AI training data"""
    attribute: str
    value: float  # 0.0-1.0 quality score
    measurement_method: str
    measured_at: str
    threshold: float = 0.80
    passed: bool = True
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = compute_hash({
                "attribute": self.attribute,
                "value": self.value,
                "measurement_method": self.measurement_method,
            })
        self.passed = self.value >= self.threshold

    def to_evidence(self) -> dict:
        return {
            "attribute": self.attribute,
            "value": self.value,
            "measurement_method": self.measurement_method,
            "measured_at": self.measured_at,
            "threshold": self.threshold,
            "passed": self.passed,
            "hash": self.hash,
        }


@dataclass
class DataQualityReport:
    """EN 50716 Data Quality Report for AI training data"""
    report_id: str
    generated_at: str
    dataset_hash: str
    dataset_size: int
    records: List[DataQualityRecord] = field(default_factory=list)
    overall_score: float = 0.0
    compliant: bool = False
    hash: str = ""

    def __post_init__(self):
        if self.records:
            self.overall_score = sum(r.value for r in self.records) / len(self.records)
        self.compliant = self.overall_score >= 0.80
        if not self.hash:
            self.hash = compute_hash(self.to_evidence())

    def to_evidence(self) -> dict:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "dataset_hash": self.dataset_hash,
            "dataset_size": self.dataset_size,
            "overall_score": self.overall_score,
            "compliant": self.compliant,
            "records": [r.to_evidence() for r in self.records],
            "hash": self.hash,
        }


# V-model adjacency: which phase links to which (downward + upward)
V_MODEL_PHASE_PAIRS: List[Tuple[EN50128Phase, EN50128Phase]] = [
    (EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS, EN50128Phase.PHASE_14_SYSTEM_VALIDATION),
    (EN50128Phase.PHASE_3_SAFETY_REQUIREMENTS, EN50128Phase.PHASE_12_OVERALL_SOFTWARE_TESTING),
    (EN50128Phase.PHASE_5_SOFTWARE_REQUIREMENTS, EN50128Phase.PHASE_11_SOFTWARE_INTEGRATION_TESTING),
    (EN50128Phase.PHASE_6_SOFTWARE_ARCHITECTURE, EN50128Phase.PHASE_10_SOFTWARE_INTEGRATION),
    (EN50128Phase.PHASE_7_SOFTWARE_DESIGN, EN50128Phase.PHASE_9_SOFTWARE_MODULE_TESTING),
    (EN50128Phase.PHASE_8_SOFTWARE_MODULE_DESIGN, EN50128Phase.PHASE_9_SOFTWARE_MODULE_TESTING),
]

V_MODEL_DOWNWARD: List[Tuple[EN50128Phase, EN50128Phase]] = [
    (EN50128Phase.PHASE_1_SYSTEM_REQUIREMENTS, EN50128Phase.PHASE_2_HAZARD_RISK_ANALYSIS),
    (EN50128Phase.PHASE_2_HAZARD_RISK_ANALYSIS, EN50128Phase.PHASE_3_SAFETY_REQUIREMENTS),
    (EN50128Phase.PHASE_3_SAFETY_REQUIREMENTS, EN50128Phase.PHASE_4_SYSTEM_ARCHITECTURE),
    (EN50128Phase.PHASE_4_SYSTEM_ARCHITECTURE, EN50128Phase.PHASE_5_SOFTWARE_REQUIREMENTS),
    (EN50128Phase.PHASE_5_SOFTWARE_REQUIREMENTS, EN50128Phase.PHASE_6_SOFTWARE_ARCHITECTURE),
    (EN50128Phase.PHASE_6_SOFTWARE_ARCHITECTURE, EN50128Phase.PHASE_7_SOFTWARE_DESIGN),
    (EN50128Phase.PHASE_7_SOFTWARE_DESIGN, EN50128Phase.PHASE_8_SOFTWARE_MODULE_DESIGN),
]


def get_downstream_phase(phase: EN50128Phase) -> Optional[EN50128Phase]:
    """Get the downstream (decomposition) phase"""
    for src, dst in V_MODEL_DOWNWARD:
        if src == phase:
            return dst
    return None


def get_upstream_phase(phase: EN50128Phase) -> Optional[EN50128Phase]:
    """Get the upstream (composition/verification target) phase"""
    for src, dst in V_MODEL_DOWNWARD:
        if dst == phase:
            return src
    return None


def get_verification_pair(phase: EN50128Phase) -> Optional[EN50128Phase]:
    """Get the matching verification phase (left-to-right in V-model)"""
    for left, right in V_MODEL_PHASE_PAIRS:
        if left == phase:
            return right
        if right == phase:
            return left
    return None
