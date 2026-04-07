"""
Cortex Tool Verification Plan (TVP)

Part of the Tool Qualification Kit (TQK).

Defines the verification procedures to confirm that Cortex meets
all Tool Operational Requirements (TOR).

The TVP includes:
1. Verification test cases
2. Test procedures for each TOR requirement
3. Expected results
4. Pass/fail criteria
"""

import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TestCategory(str, Enum):
    """Categories of verification tests"""
    INSPECTION = "inspection"  # Review of documentation, code
    ANALYSIS = "analysis"     # Calculations, modeling
    TEST = "test"            # Execution of software


@dataclass
class VerificationTestCase:
    """A single test case in the verification plan"""
    test_id: str
    tor_req_id: str  # Links to TOR requirement
    title: str
    category: TestCategory
    test_procedure: List[str]  # Step-by-step instructions
    expected_result: str
    pass_criteria: str
    required_equipment: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 30


@dataclass
class ToolVerificationPlan:
    """
    Tool Verification Plan document.
    
    Contains test cases to verify each TOR requirement.
    """
    
    tool_name: str = "Cortex"
    tool_version: str = "1.0.0"
    test_cases: List[VerificationTestCase] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.test_cases:
            self._initialize_default_test_cases()
    
    def _initialize_default_test_cases(self):
        """Initialize default test cases"""
        
        # === INSPECTION TESTS ===
        self.test_cases.extend([
            VerificationTestCase(
                test_id="TVP-INS-001",
                tor_req_id="TOR-OP-001",
                title="Purpose Definition Review",
                category=TestCategory.INSPECTION,
                test_procedure=[
                    "1. Review project README.md",
                    "2. Verify documentation describes knowledge management purpose",
                    "3. Verify scope covers compliance documentation",
                    "4. Document findings"
                ],
                expected_result="README contains clear purpose and scope statement",
                pass_criteria="Documentation exists and describes purpose",
                estimated_duration_minutes=15
            ),
            VerificationTestCase(
                test_id="TVP-INS-002",
                tor_req_id="TOR-OP-003",
                title="Audit Trail Capability Review",
                category=TestCategory.INSPECTION,
                test_procedure=[
                    "1. Review audit.py source code",
                    "2. Verify AuditLogEntry class structure",
                    "3. Check that user, action, timestamp, outcome are captured",
                    "4. Verify hash chain implementation"
                ],
                expected_result="Audit system captures all required fields",
                pass_criteria="All specified audit fields are implemented",
                estimated_duration_minutes=30
            ),
            VerificationTestCase(
                test_id="TVP-INS-003",
                tor_req_id="TOR-QA-004",
                title="SOUP Documentation Review",
                category=TestCategory.INSPECTION,
                test_procedure=[
                    "1. Review requirements.txt and requirements-dev.txt",
                    "2. Check for SOUP manifest in tqk/soup directory",
                    "3. Verify all third-party dependencies are listed",
                    "4. Confirm functional/performance requirements documented"
                ],
                expected_result="SOUP manifest exists with all dependencies",
                pass_criteria="All third-party components documented",
                estimated_duration_minutes=20
            ),
            VerificationTestCase(
                test_id="TVP-INS-004",
                tor_req_id="TOR-QA-001",
                title="Code Documentation Review",
                category=TestCategory.INSPECTION,
                test_procedure=[
                    "1. Run: pydocstyle or flake8 --docstring-style on codebase",
                    "2. Check all public classes have docstrings",
                    "3. Review API documentation completeness",
                    "4. Document any missing documentation"
                ],
                expected_result="Docstrings exist for all public APIs",
                pass_criteria="All public functions and classes have docstrings",
                estimated_duration_minutes=30
            ),
            VerificationTestCase(
                test_id="TVP-INS-005",
                tor_req_id="TOR-QA-002",
                title="Version Control Verification",
                category=TestCategory.INSPECTION,
                test_procedure=[
                    "1. Verify .git directory exists",
                    "2. Run: git log --oneline -10",
                    "3. Check commit messages follow convention",
                    "4. Verify repository structure"
                ],
                expected_result="Git repository with commit history exists",
                pass_criteria="Repository exists with meaningful commit history",
                estimated_duration_minutes=10
            ),
        ])
        
        # === ANALYSIS TESTS ===
        self.test_cases.extend([
            VerificationTestCase(
                test_id="TVP-ANL-001",
                tor_req_id="TOR-OP-002",
                title="Determinism Analysis",
                category=TestCategory.ANALYSIS,
                test_procedure=[
                    "1. Select 5 representative queries",
                    "2. Execute each query 3 times with identical knowledge base",
                    "3. Compare results for identical output",
                    "4. Calculate reproducibility percentage"
                ],
                expected_result="Same inputs produce same outputs",
                pass_criteria="Reproducibility rate > 95%",
                estimated_duration_minutes=45
            ),
            VerificationTestCase(
                test_id="TVP-ANL-002",
                tor_req_id="TOR-OP-004",
                title="Data Integrity Analysis",
                category=TestCategory.ANALYSIS,
                test_procedure=[
                    "1. Calculate SHA256 hash of original document",
                    "2. Ingest document into Cortex",
                    "3. Retrieve document from knowledge base",
                    "4. Compare hash values"
                ],
                expected_result="Document hash preserved after ingestion",
                pass_criteria="Original and retrieved document hashes match",
                estimated_duration_minutes=20
            ),
            VerificationTestCase(
                test_id="TVP-ANL-003",
                tor_req_id="TOR-FN-007",
                title="Parent Context Preservation Analysis",
                category=TestCategory.ANALYSIS,
                test_procedure=[
                    "1. Create test document with multiple sections",
                    "2. Index document with chunking",
                    "3. Search for specific content",
                    "4. Verify parent document context available"
                ],
                expected_result="Retrieved chunks include parent context",
                pass_criteria="Search results contain both chunk and parent document",
                estimated_duration_minutes=30
            ),
        ])
        
        # === TEST (EXECUTION) TESTS ===
        self.test_cases.extend([
            VerificationTestCase(
                test_id="TVP-TST-001",
                tor_req_id="TOR-FN-001",
                title="Markdown Structure Preservation Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create test Markdown with headings, lists, code blocks, tables",
                    "2. Ingest into Cortex: python -m cortex ingest test_file.md",
                    "3. Retrieve document content",
                    "4. Verify all Markdown elements preserved"
                ],
                expected_result="All Markdown elements preserved",
                pass_criteria="Headings, lists, code blocks, tables all intact",
                estimated_duration_minutes=20,
                prerequisites=["Cortex installed", "Ollama running"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-002",
                tor_req_id="TOR-FN-002",
                title="Semantic Search Functionality Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Ingest 10 test documents with known content",
                    "2. Execute: python -m cortex ask 'specific concept from doc 3'",
                    "3. Verify results include relevant document",
                    "4. Check citation matches source"
                ],
                expected_result="Relevant documents returned for query",
                pass_criteria="Top results include correct source documents",
                estimated_duration_minutes=30,
                prerequisites=["Documents ingested", "Embeddings generated"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-003",
                tor_req_id="TOR-FN-003",
                title="Citation Verification Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create test document with verifiable claim",
                    "2. Execute query that generates citation",
                    "3. Run deterministic quote validation",
                    "4. Verify citation matches source text"
                ],
                expected_result="Citation verification returns match",
                pass_criteria="Citation exactly matches or is within threshold of source",
                estimated_duration_minutes=30,
                prerequisites=["Deterministic quoting enabled"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-004",
                tor_req_id="TOR-FN-004",
                title="Traceability Matrix Generation Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create wiki with tagged requirements and tests",
                    "2. Run: python -m cortex rtm --format html",
                    "3. Review generated RTM",
                    "4. Verify bidirectional links"
                ],
                expected_result="RTM generated with requirement-test links",
                pass_criteria="All requirements linked to tests bidirectionally",
                estimated_duration_minutes=30,
                prerequisites=["Compliance tags in wiki"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-005",
                tor_req_id="TOR-FN-005",
                title="ReqIF Export Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create wiki with requirements",
                    "2. Run: python -m cortex reqif --output requirements.reqif",
                    "3. Validate generated ReqIF XML",
                    "4. Check against ReqIF schema"
                ],
                expected_result="Valid ReqIF file generated",
                pass_criteria="File passes XSD schema validation",
                estimated_duration_minutes=30,
                prerequisites=["Requirements in wiki"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-006",
                tor_req_id="TOR-FN-006",
                title="Hybrid Search Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Index test documents",
                    "2. Execute queries with hybrid search enabled",
                    "3. Compare with pure vector and pure BM25",
                    "4. Measure recall improvement"
                ],
                expected_result="Hybrid search provides improved recall",
                pass_criteria="Hybrid recall >= max(vector_recall, bm25_recall)",
                estimated_duration_minutes=45,
                prerequisites=["Documents indexed"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-007",
                tor_req_id="TOR-FN-008",
                title="Compliance Tag Parsing Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create Markdown with <requirement>, <test>, <trace> tags",
                    "2. Run compliance scanner",
                    "3. Verify all tags parsed correctly",
                    "4. Check extraction matches original"
                ],
                expected_result="All compliance tags correctly parsed",
                pass_criteria="100% of tags extracted with correct attributes",
                estimated_duration_minutes=25
            ),
            VerificationTestCase(
                test_id="TVP-TST-008",
                tor_req_id="TOR-IF-001",
                title="Ollama Integration Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Start Ollama service",
                    "2. Verify connection: curl http://localhost:11434/api/tags",
                    "3. Execute Cortex inference call",
                    "4. Verify response received"
                ],
                expected_result="Cortex successfully calls Ollama API",
                pass_criteria="Ollama /api/generate returns valid response",
                estimated_duration_minutes=20,
                prerequisites=["Ollama service running"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-009",
                tor_req_id="TOR-IF-003",
                title="API RTM Export Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Start Cortex API server",
                    "2. POST to /api/rtm with wiki path",
                    "3. Request HTML, CSV, and JSON formats",
                    "4. Verify all formats returned correctly"
                ],
                expected_result="All RTM formats available via API",
                pass_criteria="HTML, CSV, JSON all valid and complete",
                estimated_duration_minutes=30,
                prerequisites=["Cortex API running"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-010",
                tor_req_id="TOR-PF-001",
                title="Search Latency Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create knowledge base with 1000 test documents",
                    "2. Execute 100 search queries",
                    "3. Measure response times",
                    "4. Calculate 95th percentile"
                ],
                expected_result="Search completes within 5 seconds",
                pass_criteria="95th percentile < 5 seconds",
                estimated_duration_minutes=30,
                prerequisites=["1000 documents indexed"]
            ),
            VerificationTestCase(
                test_id="TVP-TST-011",
                tor_req_id="TOR-EN-001",
                title="Python Environment Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Create fresh Python 3.10 virtual environment",
                    "2. Run: pip install -e .",
                    "3. Run: python -m cortex --version",
                    "4. Execute basic commands"
                ],
                expected_result="Installation succeeds on Python 3.10+",
                pass_criteria="Install completes without errors",
                estimated_duration_minutes=20
            ),
            VerificationTestCase(
                test_id="TVP-TST-012",
                tor_req_id="TOR-QA-003",
                title="Unit Test Coverage Test",
                category=TestCategory.TEST,
                test_procedure=[
                    "1. Run: pytest --cov=cortex --cov-report=term",
                    "2. Review coverage report",
                    "3. Check core module coverage",
                    "4. Document coverage percentage"
                ],
                expected_result="Unit tests pass with >70% coverage",
                pass_criteria="Coverage >= 70% on core modules",
                estimated_duration_minutes=30,
                prerequisites=["Test suite available"]
            ),
        ])
    
    def get_test_cases_by_category(self, category: TestCategory) -> List[VerificationTestCase]:
        """Get test cases filtered by category"""
        return [tc for tc in self.test_cases if tc.category == category]
    
    def get_test_cases_by_tor(self, tor_req_id: str) -> List[VerificationTestCase]:
        """Get test cases for a specific TOR requirement"""
        return [tc for tc in self.test_cases if tc.tor_req_id == tor_req_id]
    
    def get_test_cases_by_id(self, test_id: str) -> Optional[VerificationTestCase]:
        """Get a specific test case by ID"""
        for tc in self.test_cases:
            if tc.test_id == test_id:
                return tc
        return None
    
    def get_total_estimated_duration(self) -> int:
        """Get total estimated duration in minutes"""
        return sum(tc.estimated_duration_minutes for tc in self.test_cases)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "generated_at": datetime.now().isoformat(),
            "total_test_cases": len(self.test_cases),
            "total_estimated_minutes": self.get_total_estimated_duration(),
            "by_category": {
                "inspection": len(self.get_test_cases_by_category(TestCategory.INSPECTION)),
                "analysis": len(self.get_test_cases_by_category(TestCategory.ANALYSIS)),
                "test": len(self.get_test_cases_by_category(TestCategory.TEST)),
            },
            "test_cases": [
                {
                    "test_id": tc.test_id,
                    "tor_req_id": tc.tor_req_id,
                    "title": tc.title,
                    "category": tc.category.value,
                    "procedure": tc.test_procedure,
                    "expected_result": tc.expected_result,
                    "pass_criteria": tc.pass_criteria,
                    "prerequisites": tc.prerequisites,
                    "estimated_minutes": tc.estimated_duration_minutes,
                }
                for tc in self.test_cases
            ]
        }
    
    def to_markdown(self) -> str:
        """Generate Markdown documentation"""
        lines = [
            f"# Tool Verification Plan (TVP)",
            f"# {self.tool_name} v{self.tool_version}",
            "",
            f"**Document generated:** {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## Summary",
            "",
            f"- **Total Test Cases:** {len(self.test_cases)}",
            f"- **Estimated Duration:** {self.get_total_estimated_duration()} minutes ({self.get_total_estimated_duration()//60}h {self.get_total_estimated_duration()%60}m)",
            "",
            f"- Inspection: {len(self.get_test_cases_by_category(TestCategory.INSPECTION))} tests",
            f"- Analysis: {len(self.get_test_cases_by_category(TestCategory.ANALYSIS))} tests",
            f"- Test (Execution): {len(self.get_test_cases_by_category(TestCategory.TEST))} tests",
            "",
            "---",
            "",
        ]
        
        # Group by category
        for cat in TestCategory:
            cases = self.get_test_cases_by_category(cat)
            if not cases:
                continue
            
            lines.append(f"## {cat.value.upper()} Tests")
            lines.append("")
            
            for tc in cases:
                lines.append(f"### {tc.test_id}: {tc.title}")
                lines.append("")
                lines.append(f"**TOR Requirement:** {tc.tor_req_id}")
                lines.append(f"**Category:** {tc.category.value}")
                lines.append(f"**Duration:** {tc.estimated_duration_minutes} minutes")
                lines.append("")
                
                if tc.prerequisites:
                    lines.append(f"**Prerequisites:** {', '.join(tc.prerequisites)}")
                    lines.append("")
                
                lines.append(f"**Test Procedure:**")
                for step in tc.test_procedure:
                    lines.append(f"- {step}")
                lines.append("")
                
                lines.append(f"**Expected Result:** {tc.expected_result}")
                lines.append("")
                
                lines.append(f"**Pass Criteria:** {tc.pass_criteria}")
                lines.append("")
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)