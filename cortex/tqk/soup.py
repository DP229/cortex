"""
Cortex SOUP Management - Software of Unknown Provenance

Part of the Tool Qualification Kit (TQK).

Documents all third-party components (SOUP) in the Cortex stack
for integration into ISO 14971 risk management files.

IEC 62304 Definition:
SOUP (Software of Unknown Provenance) = Off-the-shelf software
used as a component of a medical device, where the device software
organization did not develop nor control the SOUP.

This module provides:
- SOUP component documentation
- Functional/performance requirements for each SOUP
- Known failure modes
- Environmental requirements
- Integration into risk management
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re


class SOUPCategory(str, Enum):
    """Categories of SOUP components"""
    LLM_PROVIDER = "llm_provider"
    EMBEDDINGS = "embeddings"
    DATABASE = "database"
    WEB_FRAMEWORK = "web_framework"
    AUTHENTICATION = "authentication"
    ENCRYPTION = "encryption"
    TESTING = "testing"
    UTILITY = "utility"


class SILLevel(str, Enum):
    """Safety Integrity Level (EN 50128)"""
    SIL0 = "SIL 0"
    SIL1 = "SIL 1"
    SIL2 = "SIL 2"
    SIL3 = "SIL 3"
    SIL4 = "SIL 4"


@dataclass
class SOUPComponent:
    """
    A single SOUP component in the Cortex stack.
    """
    name: str
    version: str
    category: SOUPCategory
    description: str
    license: str
    
    # Provenance
    supplier: str = ""
    supplier_url: str = ""
    download_url: str = ""
    
    # Safety classification
    sil_level: Optional[SILLevel] = None
    iec_62304_class: Optional[str] = None  # A, B, or C
    
    # Functional requirements for this component
    functional_requirements: List[str] = field(default_factory=list)
    performance_requirements: List[str] = field(default_factory=list)
    
    # Known failure modes
    failure_modes: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    
    # Environmental requirements
    min_python_version: str = "3.10"
    min_hardware: str = "4GB RAM"
    os_compatibility: List[str] = field(default_factory=lambda: ["Linux", "Windows WSL2"])
    
    # Risk assessment
    risk_level: str = "medium"  # low, medium, high
    risk_justification: str = ""
    
    # Compliance notes
    certifications: List[str] = field(default_factory=list)
    audit_dates: List[str] = field(default_factory=list)
    
    # Usage in Cortex
    usage_description: str = ""
    integration_points: List[str] = field(default_factory=list)
    
    # Review status
    last_review_date: str = ""
    review_status: str = "current"  # current, outdated, deprecated
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "description": self.description,
            "license": self.license,
            "supplier": self.supplier,
            "supplier_url": self.supplier_url,
            "download_url": self.download_url,
            "sil_level": self.sil_level.value if self.sil_level else None,
            "iec_62304_class": self.iec_62304_class,
            "functional_requirements": self.functional_requirements,
            "performance_requirements": self.performance_requirements,
            "failure_modes": self.failure_modes,
            "mitigation_strategies": self.mitigation_strategies,
            "min_python_version": self.min_python_version,
            "min_hardware": self.min_hardware,
            "os_compatibility": self.os_compatibility,
            "risk_level": self.risk_level,
            "risk_justification": self.risk_justification,
            "certifications": self.certifications,
            "audit_dates": self.audit_dates,
            "usage_description": self.usage_description,
            "integration_points": self.integration_points,
            "last_review_date": self.last_review_date,
            "review_status": self.review_status,
        }


class SOUPManagement:
    """
    Manages all SOUP components in the Cortex stack.
    
    Provides:
    - Component registry
    - Risk assessment aggregation
    - Export for ISO 14971 risk management
    - Audit trail
    """
    
    def __init__(self):
        self.components: List[SOUPComponent] = []
        self._initialize_default_components()
    
    def _initialize_default_components(self):
        """Initialize the default SOUP components for Cortex"""
        
        # === LLM PROVIDERS ===
        self.components.append(SOUPComponent(
            name="Ollama",
            version="latest",
            category=SOUPCategory.LLM_PROVIDER,
            description="Local LLM inference server",
            license="MIT",
            supplier="Ollama Inc.",
            supplier_url="https://ollama.com",
            download_url="https://github.com/ollama/ollama",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: Provide /api/generate endpoint for text generation",
                "FR-002: Provide /api/tags endpoint for model listing",
                "FR-003: Support GGUF model format",
                "FR-004: Support Llama, Mistral, Qwen model families",
            ],
            performance_requirements=[
                "PR-001: Generate tokens at minimum 10 tokens/second for 7B models",
                "PR-002: Support context lengths up to 128K tokens",
                "PR-003: Memory usage under 8GB for 7B parameter models",
            ],
            failure_modes=[
                "FM-001: Model hallucination - generates plausible but incorrect information",
                "FM-002: Context window overflow - loses early context",
                "FM-003: Memory exhaustion - system becomes unresponsive",
                "FM-004: Model loading failure - service unavailable",
            ],
            mitigation_strategies=[
                "MS-001: Deterministic quoting validates all citations",
                "MS-002: Chunking with parent context preserves context",
                "MS-003: Memory limits enforced by IAM gateway",
                "MS-004: Health checks detect service unavailability",
            ],
            min_hardware="8GB RAM, multi-core CPU",
            risk_level="medium",
            risk_justification="Ollama provides inference only; Cortex adds validation layer",
            certifications=["SOC 2 Type II"],
            usage_description="Used for text generation and inference. Cortex does not depend on Ollama for safety-critical decisions.",
            integration_points=["brain.py", "iam_gateway.py"],
        ))
        
        # === EMBEDDINGS ===
        self.components.append(SOUPComponent(
            name="Sentence Transformers",
            version="2.x",
            category=SOUPCategory.EMBEDDINGS,
            description="Sentence embedding library",
            license="Apache 2.0",
            supplier="Hugging Face",
            supplier_url="https://huggingface.co/sentence-transformers",
            download_url="https://pypi.org/project/sentence-transformers/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: Generate 384/768/1024 dimensional embeddings",
                "FR-002: Support batch processing for efficiency",
                "FR-003: Normalize embeddings for cosine similarity",
            ],
            performance_requirements=[
                "PR-001: Process 32 documents per batch",
                "PR-002: Generate embedding in under 100ms per document",
            ],
            failure_modes=[
                "FM-001: Model loading failure",
                "FM-002: Out of memory on large batches",
            ],
            mitigation_strategies=[
                "MS-001: Batch size limits enforced",
                "MS-002: Fallback to simple hash embeddings",
            ],
            usage_description="Used for semantic search indexing and retrieval",
            integration_points=["embeddings.py", "hybrid_search.py"],
        ))
        
        # === DATABASE ===
        self.components.append(SOUPComponent(
            name="SQLite",
            version="3.x",
            category=SOUPCategory.DATABASE,
            description="Embedded SQL database",
            license="Public Domain",
            supplier="SQLite Consortium",
            supplier_url="https://www.sqlite.org",
            download_url="https://pypi.org/project/sqlite3/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: ACID transaction support",
                "FR-002: SQL query execution",
                "FR-003: JSON storage and retrieval",
            ],
            performance_requirements=[
                "PR-001: Support databases up to 100GB",
                "PR-002: Query latency under 100ms for indexed queries",
            ],
            failure_modes=[
                "FM-001: Database corruption from power loss",
                "FM-002: Disk space exhaustion",
                "FM-003: Lock contention in high concurrency",
            ],
            mitigation_strategies=[
                "MS-001: WAL mode for durability",
                "MS-002: Regular integrity checks",
                "MS-003: Connection pooling",
            ],
            min_hardware="1GB free disk space",
            risk_level="low",
            risk_justification="SQLite is mature, widely-used, and Cortex data is recoverable",
            certifications=["ISO 9001 certified development"],
            usage_description="Used for memory storage, audit logs, and knowledge base metadata",
            integration_points=["memory.py", "database.py", "audit.py"],
        ))
        
        # === WEB FRAMEWORK ===
        self.components.append(SOUPComponent(
            name="FastAPI",
            version="0.100+",
            category=SOUPCategory.WEB_FRAMEWORK,
            description="Modern Python web framework",
            license="MIT",
            supplier="Tiangolo",
            supplier_url="https://fastapi.tiangolo.com",
            download_url="https://pypi.org/project/fastapi/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: REST API endpoint handling",
                "FR-002: Request/response validation with Pydantic",
                "FR-003: OpenAPI documentation generation",
            ],
            performance_requirements=[
                "PR-001: Handle 100 concurrent requests",
                "PR-002: Response time under 1 second for simple endpoints",
            ],
            failure_modes=[
                "FM-001: Request validation bypass",
                "FM-002: Memory leak from long-running connections",
            ],
            mitigation_strategies=[
                "MS-001: Pydantic validation at API boundary",
                "MS-002: Connection timeouts configured",
            ],
            usage_description="Used for API server",
            integration_points=["main.py", "api.py", "api_healthcare.py"],
        ))
        
        # === AUTHENTICATION ===
        self.components.append(SOUPComponent(
            name="PyJWT",
            version="2.x",
            category=SOUPCategory.AUTHENTICATION,
            description="JSON Web Token implementation",
            license="MIT",
            supplier="PyJWT Project",
            supplier_url="https://pyjwt.readthedocs.io",
            download_url="https://pypi.org/project/PyJWT/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: JWT encode/decode",
                "FR-002: RS256/HS256 algorithm support",
                "FR-003: Token expiration validation",
            ],
            failure_modes=[
                "FM-001: Algorithm confusion attack",
                "FM-002: Token expiration bypass",
            ],
            mitigation_strategies=[
                "MS-001: Algorithm allowlist configured",
                "MS-002: Token expiry enforced",
            ],
            usage_description="Used for authentication tokens",
            integration_points=["auth.py", "security/auth.py"],
        ))
        
        # === ENCRYPTION ===
        self.components.append(SOUPComponent(
            name="cryptography",
            version="41.x",
            category=SOUPCategory.ENCRYPTION,
            description="Cryptographic recipes and primitives",
            license="Apache 2.0 / BSD",
            supplier="PyCA",
            supplier_url="https://cryptography.io",
            download_url="https://pypi.org/project/cryptography/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="B",
            functional_requirements=[
                "FR-001: AES-256-GCM encryption",
                "FR-002: Argon2 password hashing",
                "FR-003: Secure random number generation",
            ],
            performance_requirements=[
                "PR-001: Encryption latency under 10ms",
            ],
            failure_modes=[
                "FM-001: Side-channel timing attack",
                "FM-002: Weak key generation",
            ],
            mitigation_strategies=[
                "MS-001: Use cryptography library's constant-time operations",
                "MS-002: Entropy source validation",
            ],
            risk_level="high",
            risk_justification="Encryption is safety-relevant; library is well-audited but in B-class",
            certifications=["SOC 2", "FIPS 140-2 validated"],
            usage_description="Used for encrypting PHI in audit logs",
            integration_points=["encryption.py", "security/encryption.py"],
        ))
        
        # === TESTING ===
        self.components.append(SOUPComponent(
            name="pytest",
            version="8.x",
            category=SOUPCategory.TESTING,
            description="Python testing framework",
            license="MIT",
            supplier="pytest Project",
            supplier_url="https://pytest.org",
            download_url="https://pypi.org/project/pytest/",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: Test discovery and execution",
                "FR-002: Fixture and parameterization support",
                "FR-003: Coverage reporting",
            ],
            usage_description="Used for unit testing only; not part of production",
            integration_points=["tests/"],
        ))
        
        # === LLM MODELS ===
        self.components.append(SOUPComponent(
            name="Llama 3 / 3.1 / 3.2",
            version="8B/70B/405B",
            category=SOUPCategory.LLM_PROVIDER,
            description="Meta open-source language models",
            license="LLAMA 3.2 COMMUNITY LICENSE",
            supplier="Meta AI",
            supplier_url="https://llama.meta.com",
            download_url="https://ollama.com/library/llama3",
            sil_level=SILLevel.SIL0,
            iec_62304_class="A",
            functional_requirements=[
                "FR-001: Text generation from prompts",
                "FR-002: Instruction following",
                "FR-003: Context length up to 128K tokens",
            ],
            failure_modes=[
                "FM-001: Hallucination - generates plausible but false information",
                "FM-002: Instruction following failure",
                "FM-003: Bias in generated content",
            ],
            mitigation_strategies=[
                "MS-001: Deterministic quoting validates all claims",
                "MS-002: Human review of safety-critical outputs",
                "MS-003: Prompt injection prevention",
            ],
            risk_level="high",
            risk_justification="LLM output is non-deterministic; Cortex adds verification layer",
            certifications=["Responsible AI guidelines"],
            usage_description="Used for inference only; all outputs verified before use",
            integration_points=["brain.py"],
        ))
    
    def add_component(self, component: SOUPComponent) -> None:
        """Add a new SOUP component"""
        self.components.append(component)
    
    def get_component(self, name: str) -> Optional[SOUPComponent]:
        """Get component by name"""
        for comp in self.components:
            if comp.name == name:
                return comp
        return None
    
    def get_components_by_category(self, category: SOUPCategory) -> List[SOUPComponent]:
        """Get components filtered by category"""
        return [c for c in self.components if c.category == category]
    
    def get_high_risk_components(self) -> List[SOUPComponent]:
        """Get components with high risk level"""
        return [c for c in self.components if c.risk_level == "high"]
    
    def get_total_risk_assessment(self) -> Dict[str, Any]:
        """Get overall risk assessment"""
        total = len(self.components)
        by_level = {
            "high": len([c for c in self.components if c.risk_level == "high"]),
            "medium": len([c for c in self.components if c.risk_level == "medium"]),
            "low": len([c for c in self.components if c.risk_level == "low"]),
        }
        
        high_risk_names = [c.name for c in self.get_high_risk_components()]
        
        return {
            "total_components": total,
            "by_risk_level": by_level,
            "high_risk_components": high_risk_names,
            "overall_risk": "high" if by_level["high"] > 0 else "medium" if by_level["medium"] > 0 else "low",
        }
    
    def generate_iso14971_annex(self) -> str:
        """Generate ISO 14971 risk management annex for SOUP"""
        risk = self.get_total_risk_assessment()
        
        lines = [
            "# Annex C (informative): Software of Unknown Provenance (SOUP)",
            "",
            "## C.1 Overview",
            "",
            f"This Annex documents all third-party software components (SOUP) used in Cortex.",
            f"A total of {risk['total_components']} SOUP components have been identified and assessed.",
            "",
            f"**Overall Risk Assessment:** {risk['overall_risk'].upper()}",
            "",
            "## C.2 Risk Level Summary",
            "",
            "| Risk Level | Count | Components |",
            "|------------|-------|------------|",
            f"| High | {risk['by_risk_level']['high']} | {', '.join(risk['high_risk_components']) if risk['high_risk_components'] else 'None'} |",
            f"| Medium | {risk['by_risk_level']['medium']} | - |",
            f"| Low | {risk['by_risk_level']['low']} | - |",
            "",
            "## C.3 SOUP Component Details",
            "",
        ]
        
        for comp in self.components:
            lines.extend([
                f"### C.3.{self.components.index(comp)+1} {comp.name}",
                "",
                f"**Version:** {comp.version}",
                f"**Category:** {comp.category.value}",
                f"**License:** {comp.license}",
                f"**Supplier:** {comp.supplier}",
                f"**Risk Level:** {comp.risk_level.upper()}",
                "",
            ])
            
            if comp.functional_requirements:
                lines.append("**Functional Requirements:**")
                for fr in comp.functional_requirements:
                    lines.append(f"- {fr}")
                lines.append("")
            
            if comp.failure_modes:
                lines.append("**Known Failure Modes:**")
                for fm in comp.failure_modes:
                    lines.append(f"- {fm}")
                lines.append("")
            
            if comp.mitigation_strategies:
                lines.append("**Mitigation Strategies:**")
                for ms in comp.mitigation_strategies:
                    lines.append(f"- {ms}")
                lines.append("")
        
        lines.extend([
            "",
            "## C.4 Conclusion",
            "",
            "The identified SOUP components have been assessed for their contribution",
            "to overall system risk. Mitigation strategies have been implemented in",
            "Cortex to address the known failure modes of high and medium risk components.",
            "",
            f"Document generated: {datetime.now().strftime('%Y-%m-%d')}",
        ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "generated_at": datetime.now().isoformat(),
            "total_components": len(self.components),
            "risk_assessment": self.get_total_risk_assessment(),
            "components": [c.to_dict() for c in self.components],
        }
    
    def to_json(self) -> str:
        """Export as JSON"""
        import json
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Generate comprehensive Markdown documentation"""
        risk = self.get_total_risk_assessment()
        
        lines = [
            "# Software of Unknown Provenance (SOUP) Manifest",
            f"# Cortex v1.0.0",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d')}",
            f"**Total Components:** {risk['total_components']}",
            "",
            "---",
            "",
            "## Risk Summary",
            "",
            f"**Overall Risk:** {risk['overall_risk'].upper()}",
            "",
            f"- 🔴 High Risk: {risk['by_risk_level']['high']} components",
            f"- 🟡 Medium Risk: {risk['by_risk_level']['medium']} components",
            f"- 🟢 Low Risk: {risk['by_risk_level']['low']} components",
            "",
            "---",
            "",
        ]
        
        # Group by category
        categories = set(c.category for c in self.components)
        
        for cat in categories:
            comps = self.get_components_by_category(cat)
            lines.append(f"## {cat.value.replace('_', ' ').title()}")
            lines.append("")
            
            for comp in comps:
                risk_icon = "🔴" if comp.risk_level == "high" else "🟡" if comp.risk_level == "medium" else "🟢"
                lines.append(f"### {risk_icon} {comp.name} v{comp.version}")
                lines.append("")
                lines.append(f"**Description:** {comp.description}")
                lines.append(f"**License:** {comp.license}")
                lines.append(f"**Supplier:** {comp.supplier}")
                lines.append(f"**Risk Level:** {comp.risk_level}")
                lines.append("")
                
                if comp.functional_requirements:
                    lines.append("**Functional Requirements:**")
                    for fr in comp.functional_requirements:
                        lines.append(f"- {fr}")
                    lines.append("")
                
                if comp.failure_modes:
                    lines.append("**Known Failure Modes:**")
                    for fm in comp.failure_modes:
                        lines.append(f"- {fm}")
                    lines.append("")
                
                if comp.mitigation_strategies:
                    lines.append("**Mitigation Strategies:**")
                    for ms in comp.mitigation_strategies:
                        lines.append(f"- {ms}")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)