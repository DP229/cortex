"""
Cortex Tool Operational Requirements (TOR)

Part of the Tool Qualification Kit (TQK).

Defines the operational and functional requirements that Cortex
must meet to be qualified as a Tool Class 2 verification asset.

For IEC 62304 and EN 50128 compliance, the TOR must specify:
1. Purpose and scope of the tool
2. Functional requirements
3. Performance requirements
4. Interface requirements
5. Environmental requirements
6. Quality requirements
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from cortex.deterministic_core import compute_hash, commit, ComplianceResult, ModuleVersion


class RequirementPriority(str, Enum):
    """Priority levels for requirements"""
    MANDATORY = "M"  # Must meet for qualification
    IMPORTANT = "I"  # Should meet, deviation requires justification
    DESIRABLE = "D"  # Nice to have


class RequirementStatus(str, Enum):
    """Status of requirement verification"""
    VERIFIED = "verified"
    PARTIAL = "partial"
    NOT_VERIFIED = "not_verified"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class TORRequirement:
    """A single requirement in the TOR"""
    req_id: str
    category: str  # operational, functional, performance, interface, environmental
    title: str
    description: str
    priority: RequirementPriority
    verification_method: str  # inspection, analysis, test
    acceptance_criteria: str
    status: RequirementStatus = RequirementStatus.NOT_VERIFIED
    sil_level: str = "SIL0"
    evidence_hash: str = ""

    def __post_init__(self):
        if not self.evidence_hash:
            self.evidence_hash = compute_hash({
                "req_id": self.req_id,
                "category": self.category,
                "title": self.title,
                "description": self.description,
                "sil_level": self.sil_level,
            })


@dataclass
class ToolOperationalRequirements:
    """
    Tool Operational Requirements document.
    
    This document defines what Cortex must do to be qualified
    as a Tool Class 2 verification tool.
    """
    
    tool_name: str = "Cortex"
    tool_version: str = "1.0.0"
    tool_class: str = "T2"  # Tool Class 2
    standards: List[str] = field(default_factory=lambda: [
        "IEC 62304:2006+AMD1:2015",
        "EN 50128:2011",
        "ISO 14971:2019",
        "IEC 62443",
    ])
    
    # Requirements by category
    operational_requirements: List[TORRequirement] = field(default_factory=list)
    functional_requirements: List[TORRequirement] = field(default_factory=list)
    performance_requirements: List[TORRequirement] = field(default_factory=list)
    interface_requirements: List[TORRequirement] = field(default_factory=list)
    environmental_requirements: List[TORRequirement] = field(default_factory=list)
    quality_requirements: List[TORRequirement] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.operational_requirements:
            self._initialize_default_requirements()
    
    def _initialize_default_requirements(self):
        """Initialize default TOR requirements for Cortex"""
        
        # === OPERATIONAL REQUIREMENTS ===
        self.operational_requirements = [
            TORRequirement(
                req_id="TOR-OP-001",
                category="operational",
                title="Purpose Definition",
                description="Cortex shall provide a knowledge management system for organizing and retrieving compliance documentation.",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="Documentation exists describing purpose and scope"
            ),
            TORRequirement(
                req_id="TOR-OP-002",
                category="operational",
                title="Deterministic Output",
                description="Cortex shall generate deterministic, reproducible outputs for the same inputs.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Same query with same knowledge base returns identical results >95% of cases"
            ),
            TORRequirement(
                req_id="TOR-OP-003",
                category="operational",
                title="Audit Trail",
                description="Cortex shall maintain a complete audit trail of all operations for regulatory review.",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="Audit log captures user, action, timestamp, and outcome"
            ),
            TORRequirement(
                req_id="TOR-OP-004",
                category="operational",
                title="Data Integrity",
                description="Cortex shall preserve the integrity of ingested documents without unauthorized modification.",
                priority=RequirementPriority.MANDATORY,
                verification_method="analysis",
                acceptance_criteria="Document hash verification confirms no unauthorized changes"
            ),
        ]
        
        # === FUNCTIONAL REQUIREMENTS ===
        self.functional_requirements = [
            TORRequirement(
                req_id="TOR-FN-001",
                category="functional",
                title="Document Ingestion",
                description="Cortex shall ingest Markdown documents and maintain their structure.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Markdown with headings, lists, and code blocks is preserved"
            ),
            TORRequirement(
                req_id="TOR-FN-002",
                category="functional",
                title="Semantic Search",
                description="Cortex shall provide semantic search across indexed documents.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Vector similarity search returns relevant documents"
            ),
            TORRequirement(
                req_id="TOR-FN-003",
                category="functional",
                title="Citation Verification",
                description="Cortex shall verify that generated citations match source documents.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Deterministic quoting returns match/nomatch with source evidence"
            ),
            TORRequirement(
                req_id="TOR-FN-004",
                category="functional",
                title="Traceability Matrix Generation",
                description="Cortex shall generate bidirectional traceability matrices from tagged requirements.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="RTM links requirements to tests bidirectionally"
            ),
            TORRequirement(
                req_id="TOR-FN-005",
                category="functional",
                title="ReqIF Export",
                description="Cortex shall export requirements in ReqIF format for enterprise tools.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="Generated ReqIF file passes schema validation"
            ),
            TORRequirement(
                req_id="TOR-FN-006",
                category="functional",
                title="Hybrid Search",
                description="Cortex shall combine vector and BM25 search with configurable weighting.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="Hybrid search provides improved recall over single-method search"
            ),
            TORRequirement(
                req_id="TOR-FN-007",
                category="functional",
                title="Chunking with Parent Context",
                description="Cortex shall index small chunks for retrieval while preserving parent document context.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="analysis",
                acceptance_criteria="Retrieved chunks include parent document for full context"
            ),
            TORRequirement(
                req_id="TOR-FN-008",
                category="functional",
                title="Compliance Tag Parsing",
                description="Cortex shall parse structured compliance tags in Markdown documents.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="<requirement>, <test>, <trace> tags are correctly parsed"
            ),
        ]
        
        # === PERFORMANCE REQUIREMENTS ===
        self.performance_requirements = [
            TORRequirement(
                req_id="TOR-PF-001",
                category="performance",
                title="Search Latency",
                description="Cortex shall respond to search queries within 5 seconds for knowledge bases up to 10,000 documents.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="95th percentile response time < 5 seconds"
            ),
            TORRequirement(
                req_id="TOR-PF-002",
                category="performance",
                title="Indexing Throughput",
                description="Cortex shall index documents at a rate of at least 100 documents per minute.",
                priority=RequirementPriority.DESIRABLE,
                verification_method="test",
                acceptance_criteria="Indexing rate > 100 docs/min for typical Markdown files"
            ),
            TORRequirement(
                req_id="TOR-PF-003",
                category="performance",
                title="Memory Efficiency",
                description="Cortex shall operate within 8GB RAM for knowledge bases up to 50,000 documents.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="Memory usage < 8GB for specified document count"
            ),
        ]
        
        # === INTERFACE REQUIREMENTS ===
        self.interface_requirements = [
            TORRequirement(
                req_id="TOR-IF-001",
                category="interface",
                title="Local Ollama Integration",
                description="Cortex shall interface with local Ollama instances for LLM inference.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Cortex can call Ollama /api/generate and /api/tags endpoints"
            ),
            TORRequirement(
                req_id="TOR-IF-002",
                category="interface",
                title="File System Access",
                description="Cortex shall read/write documents to local file system.",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="File system operations work for configured wiki paths"
            ),
            TORRequirement(
                req_id="TOR-IF-003",
                category="interface",
                title="API Export",
                description="Cortex shall export RTM data via API endpoints.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="RTM generation endpoint returns HTML/CSV/JSON"
            ),
        ]
        
        # === ENVIRONMENTAL REQUIREMENTS ===
        self.environmental_requirements = [
            TORRequirement(
                req_id="TOR-EN-001",
                category="environmental",
                title="Python Environment",
                description="Cortex shall run on Python 3.10+ with pip package management.",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="Installation succeeds on clean Python 3.10+ environment"
            ),
            TORRequirement(
                req_id="TOR-EN-002",
                category="environmental",
                title="Operating System Compatibility",
                description="Cortex shall run on Linux and Windows WSL2 environments.",
                priority=RequirementPriority.MANDATORY,
                verification_method="test",
                acceptance_criteria="Core functions work on Ubuntu 22.04 and Windows 11 WSL2"
            ),
            TORRequirement(
                req_id="TOR-EN-003",
                category="environmental",
                title="Hardware Requirements",
                description="Cortex shall operate on hardware with minimum 16GB RAM and multi-core CPU.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="inspection",
                acceptance_criteria="Documentation specifies minimum hardware requirements"
            ),
        ]
        
        # === QUALITY REQUIREMENTS ===
        self.quality_requirements = [
            TORRequirement(
                req_id="TOR-QA-001",
                category="quality",
                title="Code Documentation",
                description="Cortex shall have comprehensive code documentation.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="inspection",
                acceptance_criteria="Docstrings exist for all public APIs"
            ),
            TORRequirement(
                req_id="TOR-QA-002",
                category="quality",
                title="Version Control",
                description="Cortex source code shall be maintained in version control.",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="Git repository exists with commit history"
            ),
            TORRequirement(
                req_id="TOR-QA-003",
                category="quality",
                title="Unit Test Coverage",
                description="Cortex shall have unit tests covering core functionality.",
                priority=RequirementPriority.IMPORTANT,
                verification_method="test",
                acceptance_criteria="Unit tests pass with >70% code coverage on core modules"
            ),
            TORRequirement(
                req_id="TOR-QA-004",
                category="quality",
                title="SOUP Documentation",
                description="Cortex shall document all third-party components (SOUP).",
                priority=RequirementPriority.MANDATORY,
                verification_method="inspection",
                acceptance_criteria="SOUP manifest exists listing all third-party dependencies"
            ),
        ]
    
    def get_all_requirements(self) -> List[TORRequirement]:
        """Get all requirements in a flat list"""
        all_reqs = []
        all_reqs.extend(self.operational_requirements)
        all_reqs.extend(self.functional_requirements)
        all_reqs.extend(self.performance_requirements)
        all_reqs.extend(self.interface_requirements)
        all_reqs.extend(self.environmental_requirements)
        all_reqs.extend(self.quality_requirements)
        return all_reqs
    
    def get_requirements_by_priority(self, priority: RequirementPriority) -> List[TORRequirement]:
        """Get requirements filtered by priority"""
        return [r for r in self.get_all_requirements() if r.priority == priority]
    
    def get_requirements_by_category(self, category: str) -> List[TORRequirement]:
        """Get requirements filtered by category"""
        return [r for r in self.get_all_requirements() if r.category == category]
    
    def get_unverified_requirements(self) -> List[TORRequirement]:
        """Get requirements not yet verified"""
        return [r for r in self.get_all_requirements() if r.status == RequirementStatus.NOT_VERIFIED]

    def get_requirement_by_id(self, req_id: str) -> Optional[TORRequirement]:
        """Get a single requirement by ID"""
        for r in self.get_all_requirements():
            if r.req_id == req_id:
                return r
        return None

    def apply_sil_mapping(self, sil_target: str) -> None:
        """
        Apply SIL-level mapping to all requirements.

        EN 50128 Annexe B: Higher SIL tools require stricter verification.
        SIL0: Standard quality requirements
        SIL1/2: Enhanced verification, automated test evidence
        SIL3/4: Full formal verification, independent assessment

        Mandatory requirements inherit the target SIL level.
        Important requirements get one level lower.
        Desirable requirements default to SIL0.
        """
        sil_map = {
            "SIL4": {"MANDATORY": "SIL4", "IMPORTANT": "SIL3", "DESIRABLE": "SIL2"},
            "SIL3": {"MANDATORY": "SIL3", "IMPORTANT": "SIL2", "DESIRABLE": "SIL1"},
            "SIL2": {"MANDATORY": "SIL2", "IMPORTANT": "SIL1", "DESIRABLE": "SIL0"},
            "SIL1": {"MANDATORY": "SIL1", "IMPORTANT": "SIL0", "DESIRABLE": "SIL0"},
            "SIL0": {"MANDATORY": "SIL0", "IMPORTANT": "SIL0", "DESIRABLE": "SIL0"},
        }

        mapping = sil_map.get(sil_target.upper(), sil_map["SIL2"])

        for req in self.get_all_requirements():
            priority_key = req.priority.name
            req.sil_level = mapping.get(priority_key, "SIL0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "tool_class": self.tool_class,
            "standards": self.standards,
            "requirements": {
                "operational": [self._req_to_dict(r) for r in self.operational_requirements],
                "functional": [self._req_to_dict(r) for r in self.functional_requirements],
                "performance": [self._req_to_dict(r) for r in self.performance_requirements],
                "interface": [self._req_to_dict(r) for r in self.interface_requirements],
                "environmental": [self._req_to_dict(r) for r in self.environmental_requirements],
                "quality": [self._req_to_dict(r) for r in self.quality_requirements],
            }
        }
    
    def _req_to_dict(self, req: TORRequirement) -> Dict[str, str]:
        return {
            "req_id": req.req_id,
            "category": req.category,
            "title": req.title,
            "description": req.description,
            "priority": req.priority.value,
            "verification_method": req.verification_method,
            "acceptance_criteria": req.acceptance_criteria,
            "status": req.status.value,
            "sil_level": req.sil_level,
            "evidence_hash": req.evidence_hash,
        }
    
    def to_markdown(self) -> str:
        """Generate Markdown documentation"""
        lines = [
            f"# Tool Operational Requirements (TOR)",
            f"# {self.tool_name} v{self.tool_version}",
            f"# Tool Class: {self.tool_class}",
            "",
            f"**Document generated:** {datetime.now().strftime('%Y-%m-%d')}",
            f"**Applicable Standards:** {', '.join(self.standards)}",
            "",
            "---",
            "",
        ]
        
        categories = [
            ("operational", "Operational Requirements"),
            ("functional", "Functional Requirements"),
            ("performance", "Performance Requirements"),
            ("interface", "Interface Requirements"),
            ("environmental", "Environmental Requirements"),
            ("quality", "Quality Requirements"),
        ]
        
        for cat_id, cat_name in categories:
            lines.append(f"## {cat_name}")
            lines.append("")
            
            reqs = self.get_requirements_by_category(cat_id)
            for req in reqs:
                priority_icon = "🔴" if req.priority == RequirementPriority.MANDATORY else "🟡" if req.priority == RequirementPriority.IMPORTANT else "🟢"
                lines.append(f"### {priority_icon} {req.req_id}: {req.title}")
                lines.append("")
                lines.append(f"**Priority:** {req.priority.value} ({req.priority.name})")
                lines.append(f"**Category:** {req.category}")
                lines.append("")
                lines.append(f"**Description:**")
                lines.append(f"{req.description}")
                lines.append("")
                lines.append(f"**Verification Method:** {req.verification_method}")
                lines.append("")
                lines.append(f"**Acceptance Criteria:**")
                lines.append(f"{req.acceptance_criteria}")
                lines.append("")
                lines.append(f"**Status:** {req.status.value}")
                lines.append("")
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)