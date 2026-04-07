"""
Cortex Tool Qualification Kit (TQK) - IEC 62304 / EN 50128 Compliance

Phase 4 Enhancement: Documentation and procedures for qualifying Cortex
as a Tool Class 2 (T2) verification asset in safety-critical workflows.

IEC 62304 (Medical Device Software) Classification:
- Tool Class 1: Tools that don't affect software output
- Tool Class 2 (T2): Tools that generate output affecting safety
- Tool Class 3 (T3): Tools whose failure could cause hazard

EN 50128 (Railway) Classification:
- Similar T2 classification for tools used in SIL 0-4 development

This module provides:
- Tool Operational Requirements (TOR)
- Tool Verification Plans (TVP)
- Tool Verification Procedures (TVC)
- Tool Verification Results (TVR) generation
- Automated test scripts for qualification
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
    SILLevel,
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
    "SILLevel",
]