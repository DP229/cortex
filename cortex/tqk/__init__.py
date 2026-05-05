"""
Cortex Tool Qualification Kit (TQK) - EN 50128 / EN 50716 Compliance

Tool Class 2 (T2) self-qualification engine for Cortex.

This module provides:
- Tool Operational Requirements (TOR) with SIL mapping
- Tool Verification Plans (TVP) with equivalence partitioning
- Tool Verification Results (TVR) with HMAC signing
- T2 Qualification Engine (self-qualifying)
- T2 Evidence Package (signed regulatory evidence)
- SOUP (Software of Unknown Provenance) management
"""

from cortex.tqk.tor import (
    ToolOperationalRequirements,
    TORRequirement,
    RequirementPriority,
    RequirementStatus,
)
from cortex.tqk.tvp import (
    ToolVerificationPlan,
    VerificationTestCase,
    TestCategory,
)
from cortex.tqk.tvr import (
    ToolVerificationReport,
    TestExecutionResult,
    TestResult,
    AutomatedTVRunner,
)
from cortex.tqk.soup import (
    SOUPManagement,
    SOUPComponent,
    SOUPCategory,
    IEC62304Class,
)
from cortex.tqk.t2_qualifier import (
    QualificationEngine,
    T2EvidencePackage,
    QualificationRun,
)
from cortex.tqk.t2_evidence import (
    EvidenceCollector,
    SignedT2Evidence,
    T2EvidenceManifest,
    EvidenceFile,
)

__all__ = [
    # TOR
    "ToolOperationalRequirements",
    "TORRequirement",
    "RequirementPriority",
    "RequirementStatus",
    # TVP
    "ToolVerificationPlan",
    "VerificationTestCase",
    "TestCategory",
    # TVR
    "ToolVerificationReport",
    "TestExecutionResult",
    "TestResult",
    "AutomatedTVRunner",
    # SOUP
    "SOUPManagement",
    "SOUPComponent",
    "SOUPCategory",
    "IEC62304Class",
    # T2 Qualifier
    "QualificationEngine",
    "T2EvidencePackage",
    "QualificationRun",
    # T2 Evidence
    "EvidenceCollector",
    "SignedT2Evidence",
    "T2EvidenceManifest",
    "EvidenceFile",
]
