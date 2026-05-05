"""
Cortex Compliance Tags - Structured Requirement & Test Tagging

Phase 2 Enhancement: Parser that recognizes structured compliance tags
natively within Markdown wiki documents.

Supported Tags:
- `` - Requirement specification
- `` - Test case definition
- `` - Verification method (inspection/analysis/test/demonstration)
- `` - Safety requirement marker
- `` - Traceability link to parent requirement
- `` - Risk assessment reference
- `` - Compliance standard reference (IEC 62304, EN 50128, etc.)

These tags enable:
- Automated RTM generation
- ReqIF export for enterprise tools
- Compliance verification workflows
"""

import re
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RequirementType(Enum):
    """Types of requirements"""
    FUNCTIONAL = "functional"
    SAFETY = "safety"
    PERFORMANCE = "performance"
    INTERFACE = "interface"
    DESIGN = "design"
    REGULATORY = "regulatory"
    SECURITY = "security"
    USABILITY = "usability"
    OTHER = "other"


class TestType(Enum):
    """Types of tests"""
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    ACCEPTANCE = "acceptance"
    REGRESSION = "regression"
    MANUAL = "manual"
    AUTOMATED = "automated"
    ANALYSIS = "analysis"  # Review, inspection, walkthrough
    DEMONSTRATION = "demonstration"


class VerificationMethod(Enum):
    """IEC 62304 verification methods"""
    INSPECTION = "inspection"
    ANALYSIS = "analysis"
    TEST = "test"
    DEMONSTRATION = "demonstration"


class ComplianceStandard(Enum):
    """Supported compliance standards"""
    IEC_62304 = "IEC 62304"
    EN_50128 = "EN 50128"
    ISO_14971 = "ISO 14971"
    IEC_62443 = "IEC 62443"
    ISO_13485 = "ISO 13485"
    FDA_21CFR_PART11 = "FDA 21 CFR Part 11"
    GDPR = "GDPR"
    EU_AI_ACT = "EU AI Act"


@dataclass
class RequirementTag:
    """A parsed requirement tag"""
    req_id: str
    content: str
    requirement_type: str
    priority: str  #shall, should, may
    source_standard: Optional[str] = None
    safety_class: Optional[str] = None  # A, B, C for IEC 62304
    risk_level: Optional[str] = None
    parent_req_id: Optional[str] = None
    line_number: int = 0
    file_path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id,
            "content": self.content,
            "type": self.requirement_type,
            "priority": self.priority,
            "source_standard": self.source_standard,
            "safety_class": self.safety_class,
            "risk_level": self.risk_level,
            "parent_req_id": self.parent_req_id,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class TestCaseTag:
    """A parsed test case tag"""
    test_id: str
    content: str
    test_type: str
    verification_method: str  # inspection/analysis/test/demonstration
    verifies_req_id: Optional[str] = None
    test_input: Optional[str] = None
    expected_result: Optional[str] = None
    test_environment: Optional[str] = None
    automated: bool = False
    line_number: int = 0
    file_path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "content": self.content,
            "test_type": self.test_type,
            "verification_method": self.verification_method,
            "verifies_req_id": self.verifies_req_id,
            "test_input": self.test_input,
            "expected_result": self.expected_result,
            "test_environment": self.test_environment,
            "automated": self.automated,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class TraceLink:
    """A traceability link between requirements"""
    source_id: str
    source_type: str  # "requirement" or "test"
    target_id: str
    target_type: str
    link_type: str  # "verifies", "refines", "conflicts", "derived_from"
    file_path: str = ""
    line_number: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "link_type": self.link_type,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


@dataclass
class ComplianceReference:
    """A compliance standard reference"""
    standard: str
    clause: Optional[str] = None
    description: Optional[str] = None
    line_number: int = 0
    file_path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard": self.standard,
            "clause": self.clause,
            "description": self.description,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class T2TraceTag:
    """A T2 tool qualification trace tag"""
    tag_id: str
    tool: str = ""
    operation: str = ""
    evidence_hash: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "tag_id": self.tag_id,
            "tool": self.tool,
            "operation": self.operation,
            "evidence_hash": self.evidence_hash,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class RailPhaseTag:
    """A railway lifecycle phase tag"""
    phase: str
    sil: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "sil": self.sil,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class ToolClassTag:
    """A tool class declaration tag"""
    tool_class: str  # T1, T2, T3
    standard: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "tool_class": self.tool_class,
            "standard": self.standard,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class DataProvenanceTag:
    """Data provenance tag per EN 50716"""
    source: str
    collected: str = ""
    preprocessing: str = ""
    data_hash: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "collected": self.collected,
            "preprocessing": self.preprocessing,
            "data_hash": self.data_hash,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class DesignRefTag:
    """Design reference tag linking design to requirement"""
    design_id: str
    implements_req: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "design_id": self.design_id,
            "implements_req": self.implements_req,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class CodeRefTag:
    """Code reference tag linking code to design"""
    code_id: str
    implements_design: str = ""
    file: str = ""
    line_number: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "code_id": self.code_id,
            "implements_design": self.implements_design,
            "file": self.file,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }


@dataclass
class ParsedDocument:
    """A document with all parsed compliance tags"""
    path: str
    title: str
    requirements: List[RequirementTag] = field(default_factory=list)
    test_cases: List[TestCaseTag] = field(default_factory=list)
    trace_links: List[TraceLink] = field(default_factory=list)
    compliance_refs: List[ComplianceReference] = field(default_factory=list)
    t2_traces: List[T2TraceTag] = field(default_factory=list)
    rail_phases: List[RailPhaseTag] = field(default_factory=list)
    tool_classes: List[ToolClassTag] = field(default_factory=list)
    data_provenances: List[DataProvenanceTag] = field(default_factory=list)
    design_refs: List[DesignRefTag] = field(default_factory=list)
    code_refs: List[CodeRefTag] = field(default_factory=list)
    raw_content: str = ""
    
    def get_coverage(self) -> Dict[str, Any]:
        """Calculate test coverage metrics"""
        req_ids = {r.req_id for r in self.requirements}
        verified_reqs = {t.verifies_req_id for t in self.test_cases if t.verifies_req_id}
        
        uncovered = req_ids - verified_reqs
        
        return {
            "total_requirements": len(req_ids),
            "total_test_cases": len(self.test_cases),
            "verified_requirements": len(verified_reqs),
            "uncovered_requirements": len(uncovered),
            "coverage_percentage": len(verified_reqs) / max(len(req_ids), 1) * 100,
            "uncovered_list": list(uncovered),
        }


class ComplianceTagParser:
    """
    Parser for compliance tags in Markdown documents.
    
    Supports:
    - `` - Requirements
    - `` - Test cases
    - `` - Traceability links
    - `` - Compliance references
    - Inline `` - Risk markers
    """
    
    # Regex patterns for tags
    PATTERNS = {
        'requirement': re.compile(
            r'<requirement\s+id="([^"]+)"[^>]*>'
            r'(?:type="([^"]+)")?\s*'
            r'(?:priority="([^"]+)")?\s*'
            r'(?:safety-class="([^"]+)")?\s*'
            r'(?:parent="([^"]+)")?\s*'
            r'>(.*?)</requirement>',
            re.DOTALL | re.IGNORECASE
        ),
        'test': re.compile(
            r'<test\s+id="([^"]+)"[^>]*>'
            r'(?:type="([^"]+)")?\s*'
            r'(?:method="([^"]+)")?\s*'
            r'(?:verifies="([^"]+)")?\s*'
            r'(?:automated="([^"]+)")?\s*'
            r'>'
            r'(?:<input>(.*?)</input>)?'
            r'(?:<expected>(.*?)</expected>)?'
            r'(.*?)'
            r'</test>',
            re.DOTALL | re.IGNORECASE
        ),
        'trace': re.compile(
            r'<trace\s+from="([^"]+)"[^>]*>'
            r'(?:from-type="([^"]+)")?\s*'
            r'to="([^"]+)"\s*'
            r'(?:to-type="([^"]+)")?\s*'
            r'(?:type="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'compliance': re.compile(
            r'<compliance\s+standard="([^"]+)"[^>]*>'
            r'(?:clause="([^"]+)")?\s*'
            r'(?:description="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'risk': re.compile(
            r'<risk\s+level="([^"]+)"[^>]*/?>',
            re.IGNORECASE
        ),
        't2_trace': re.compile(
            r'<t2_trace\s+id="([^"]+)"[^>]*>'
            r'(?:tool="([^"]+)")?\s*'
            r'(?:operation="([^"]+)")?\s*'
            r'(?:evidence_hash="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'rail_phase': re.compile(
            r'<rail_phase\s+phase="([^"]+)"[^>]*>'
            r'(?:sil="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'tcl': re.compile(
            r'<tcl\s+class="(T[123])"[^>]*>'
            r'(?:standard="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'data_provenance': re.compile(
            r'<data_provenance\s+source="([^"]+)"[^>]*>'
            r'(?:collected="([^"]+)")?\s*'
            r'(?:preprocessing="([^"]+)")?\s*'
            r'(?:hash="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'design_ref': re.compile(
            r'<design_ref\s+id="([^"]+)"[^>]*>'
            r'(?:implements_req="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
        'code_ref': re.compile(
            r'<code_ref\s+id="([^"]+)"[^>]*>'
            r'(?:implements_design="([^"]+)")?\s*'
            r'(?:file="([^"]+)")?\s*'
            r'/>',
            re.IGNORECASE
        ),
    }
    
    def __init__(self):
        self.current_file = ""
        self.current_line = 0
    
    def parse_document(self, path: str, content: str) -> ParsedDocument:
        """
        Parse all compliance tags from a document.
        
        Returns:
            ParsedDocument with all extracted tags
        """
        self.current_file = path
        lines = content.split('\n')
        
        requirements = []
        test_cases = []
        trace_links = []
        compliance_refs = []
        t2_traces = []
        rail_phases = []
        tool_classes = []
        data_provenances = []
        design_refs = []
        code_refs = []

        for i, line in enumerate(lines, 1):
            self.current_line = i

            for match in self.PATTERNS['requirement'].finditer(line):
                req = self._parse_requirement(match)
                if req: requirements.append(req)

            for match in self.PATTERNS['test'].finditer(line):
                test = self._parse_test(match)
                if test: test_cases.append(test)

            for match in self.PATTERNS['trace'].finditer(line):
                trace = self._parse_trace(match)
                if trace: trace_links.append(trace)

            for match in self.PATTERNS['compliance'].finditer(line):
                ref = self._parse_compliance(match)
                if ref: compliance_refs.append(ref)

            for match in self.PATTERNS['t2_trace'].finditer(line):
                tag = self._parse_t2_trace(match)
                if tag: t2_traces.append(tag)

            for match in self.PATTERNS['rail_phase'].finditer(line):
                tag = self._parse_rail_phase(match)
                if tag: rail_phases.append(tag)

            for match in self.PATTERNS['tcl'].finditer(line):
                tag = self._parse_tcl(match)
                if tag: tool_classes.append(tag)

            for match in self.PATTERNS['data_provenance'].finditer(line):
                tag = self._parse_data_provenance(match)
                if tag: data_provenances.append(tag)

            for match in self.PATTERNS['design_ref'].finditer(line):
                tag = self._parse_design_ref(match)
                if tag: design_refs.append(tag)

            for match in self.PATTERNS['code_ref'].finditer(line):
                tag = self._parse_code_ref(match)
                if tag: code_refs.append(tag)

        title = self._extract_title(content)

        return ParsedDocument(
            path=path,
            title=title,
            requirements=requirements,
            test_cases=test_cases,
            trace_links=trace_links,
            compliance_refs=compliance_refs,
            t2_traces=t2_traces,
            rail_phases=rail_phases,
            tool_classes=tool_classes,
            data_provenances=data_provenances,
            design_refs=design_refs,
            code_refs=code_refs,
            raw_content=content,
        )
    
    def _parse_requirement(self, match: re.Match) -> Optional[RequirementTag]:
        """Parse a requirement tag"""
        try:
            req_id = match.group(1)
            content = match.group(6).strip()
            req_type = match.group(2) or "functional"
            priority = match.group(3) or "shall"
            safety_class = match.group(4)
            parent = match.group(5)
            
            return RequirementTag(
                req_id=req_id,
                content=content,
                requirement_type=req_type,
                priority=priority,
                safety_class=safety_class,
                parent_req_id=parent,
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning(f"Failed to parse requirement at {self.current_file}:{self.current_line}: {e}")
            return None
    
    def _parse_test(self, match: re.Match) -> Optional[TestCaseTag]:
        """Parse a test case tag"""
        try:
            test_id = match.group(1)
            test_type = match.group(2) or "system"
            method = match.group(3) or "test"
            verifies = match.group(4)
            automated_str = match.group(5)
            test_input = match.group(6)
            expected = match.group(7)
            content = match.group(8).strip()
            
            automated = automated_str.lower() in ('true', 'yes', '1') if automated_str else False
            
            return TestCaseTag(
                test_id=test_id,
                content=content,
                test_type=test_type,
                verification_method=method,
                verifies_req_id=verifies,
                test_input=test_input,
                expected_result=expected,
                automated=automated,
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning(f"Failed to parse test at {self.current_file}:{self.current_line}: {e}")
            return None
    
    def _parse_trace(self, match: re.Match) -> Optional[TraceLink]:
        """Parse a trace tag"""
        try:
            source_id = match.group(1)
            source_type = match.group(2) or "requirement"
            target_id = match.group(3)
            target_type = match.group(4) or "requirement"
            link_type = match.group(5) or "verifies"
            
            return TraceLink(
                source_id=source_id,
                source_type=source_type,
                target_id=target_id,
                target_type=target_type,
                link_type=link_type,
                file_path=self.current_file,
                line_number=self.current_line,
            )
        except Exception as e:
            logger.warning(f"Failed to parse trace at {self.current_file}:{self.current_line}: {e}")
            return None
    
    def _parse_compliance(self, match: re.Match) -> Optional[ComplianceReference]:
        """Parse a compliance reference tag"""
        try:
            standard = match.group(1)
            clause = match.group(2)
            description = match.group(3)
            
            return ComplianceReference(
                standard=standard,
                clause=clause,
                description=description,
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning(f"Failed to parse compliance ref at {self.current_file}:{self.current_line}: {e}")
            return None
    
    def _parse_t2_trace(self, match: re.Match) -> Optional[T2TraceTag]:
        try:
            return T2TraceTag(
                tag_id=match.group(1),
                tool=match.group(2) or "",
                operation=match.group(3) or "",
                evidence_hash=match.group(4) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("t2_trace_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _parse_rail_phase(self, match: re.Match) -> Optional[RailPhaseTag]:
        try:
            return RailPhaseTag(
                phase=match.group(1),
                sil=match.group(2) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("rail_phase_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _parse_tcl(self, match: re.Match) -> Optional[ToolClassTag]:
        try:
            return ToolClassTag(
                tool_class=match.group(1),
                standard=match.group(2) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("tcl_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _parse_data_provenance(self, match: re.Match) -> Optional[DataProvenanceTag]:
        try:
            return DataProvenanceTag(
                source=match.group(1),
                collected=match.group(2) or "",
                preprocessing=match.group(3) or "",
                data_hash=match.group(4) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("data_provenance_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _parse_design_ref(self, match: re.Match) -> Optional[DesignRefTag]:
        try:
            return DesignRefTag(
                design_id=match.group(1),
                implements_req=match.group(2) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("design_ref_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _parse_code_ref(self, match: re.Match) -> Optional[CodeRefTag]:
        try:
            return CodeRefTag(
                code_id=match.group(1),
                implements_design=match.group(2) or "",
                file=match.group(3) or "",
                line_number=self.current_line,
                file_path=self.current_file,
            )
        except Exception as e:
            logger.warning("code_ref_parse_failed", extra={"file": self.current_file, "line": self.current_line, "error": str(e)})
            return None

    def _extract_title(self, content: str) -> str:
        """Extract title from first heading"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""


class ComplianceTagGenerator:
    """
    Generator for inserting compliance tags into Markdown.
    
    Provides helper methods to create properly formatted tags.
    """
    
    @staticmethod
    def requirement(
        req_id: str,
        content: str,
        req_type: str = "functional",
        priority: str = "shall",
        safety_class: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> str:
        """
        Generate a requirement tag.
        
        Example:
            {{< requirement id="REQ-001" type="safety" priority="shall" safety-class="C" >}}
            The system shall validate user input before processing.
            {{< /requirement >}}
        """
        attrs = f'id="{req_id}"'
        if req_type:
            attrs += f' type="{req_type}"'
        if priority:
            attrs += f' priority="{priority}"'
        if safety_class:
            attrs += f' safety-class="{safety_class}"'
        if parent:
            attrs += f' parent="{parent}"'
        
        return f'{{< requirement {attrs} >}}\n{content}\n{{< /requirement >}}'
    
    @staticmethod
    def test(
        test_id: str,
        content: str,
        test_type: str = "system",
        method: str = "test",
        verifies: Optional[str] = None,
        test_input: Optional[str] = None,
        expected: Optional[str] = None,
        automated: bool = False,
    ) -> str:
        """
        Generate a test case tag.
        
        Example:
            {{< test id="TEST-001" type="system" method="test" verifies="REQ-001" automated="true" >}}
            <input>Valid user credentials</input>
            <expected>Login successful, redirect to dashboard</expected>
            Verify user authentication flow.
            {{< /test >}}
        """
        attrs = f'id="{test_id}"'
        attrs += f' type="{test_type}"'
        attrs += f' method="{method}"'
        if verifies:
            attrs += f' verifies="{verifies}"'
        attrs += f' automated="{str(automated).lower()}"'
        
        tag = f'{{< test {attrs} >}}\n'
        
        if test_input:
            tag += f'<input>{test_input}</input>\n'
        if expected:
            tag += f'<expected>{expected}</expected>\n'
        
        tag += f'{content}\n'
        tag += '{{< /test >}}'
        
        return tag
    
    @staticmethod
    def trace(
        from_id: str,
        to_id: str,
        from_type: str = "requirement",
        to_type: str = "requirement",
        link_type: str = "verifies",
    ) -> str:
        """
        Generate a trace tag.
        
        Example:
            {{< trace from="TEST-001" from-type="test" to="REQ-001" to-type="requirement" type="verifies" />}}
        """
        return (
            f'{{< trace from="{from_id}" from-type="{from_type}" '
            f'to="{to_id}" to-type="{to_type}" type="{link_type}" />}}'
        )
    
    @staticmethod
    def compliance(standard: str, clause: Optional[str] = None, description: Optional[str] = None) -> str:
        """
        Generate a compliance reference tag.
        
        Example:
            {{< compliance standard="IEC 62304" clause="5.2.3" description="Software unit verification" />}}
        """
        attrs = f'standard="{standard}"'
        if clause:
            attrs += f' clause="{clause}"'
        if description:
            attrs += f' description="{description}"'
        
        return f'{{< compliance {attrs} />}}'
    
    @staticmethod
    def risk(level: str) -> str:
        """
        Generate a risk marker.
        
        Example:
            {{< risk level="high" />}}
        """
        return f'{{< risk level="{level}" />}}'


# === Wiki Scanner ===

class ComplianceWikiScanner:
    """
    Scans the entire wiki for compliance tags.
    
    Aggregates requirements, tests, and trace links across
    all documents for RTM generation.
    """
    
    def __init__(self, knowledgebase):
        self.kb = knowledgebase
        self.parser = ComplianceTagParser()
    
    def scan_all(self) -> Dict[str, Any]:
        """
        Scan entire knowledge base for compliance content.
        
        Returns aggregated results.
        """
        all_requirements = []
        all_test_cases = []
        all_trace_links = []
        all_compliance_refs = []
        documents_with_tags = []
        
        articles = self.kb.list_articles()
        
        for article in articles:
            parsed = self.parser.parse_document(article.path, article.content)
            
            if (parsed.requirements or parsed.test_cases or 
                parsed.trace_links or parsed.compliance_refs):
                documents_with_tags.append(article.path)
                all_requirements.extend(parsed.requirements)
                all_test_cases.extend(parsed.test_cases)
                all_trace_links.extend(parsed.trace_links)
                all_compliance_refs.extend(parsed.compliance_refs)
        
        # Build traceability map
        trace_map = self._build_trace_map(all_trace_links)
        
        # Calculate coverage
        coverage = self._calculate_coverage(
            all_requirements, 
            all_test_cases, 
            trace_map
        )
        
        return {
            "total_documents": len(articles),
            "documents_with_tags": len(documents_with_tags),
            "total_requirements": len(all_requirements),
            "total_test_cases": len(all_test_cases),
            "total_trace_links": len(all_trace_links),
            "total_compliance_refs": len(all_compliance_refs),
            "requirements": [r.to_dict() for r in all_requirements],
            "test_cases": [t.to_dict() for t in all_test_cases],
            "trace_links": [t.to_dict() for t in all_trace_links],
            "compliance_refs": [c.to_dict() for c in all_compliance_refs],
            "documents_with_tags": documents_with_tags,
            "trace_map": trace_map,
            "coverage": coverage,
        }
    
    def _build_trace_map(self, trace_links: List[TraceLink]) -> Dict[str, List[str]]:
        """Build a map of requirement -> test traceability"""
        trace_map: Dict[str, List[str]] = {}
        
        for link in trace_links:
            if link.link_type == "verifies":
                if link.target_id not in trace_map:
                    trace_map[link.target_id] = []
                trace_map[link.target_id].append(link.source_id)
        
        return trace_map
    
    def _calculate_coverage(
        self,
        requirements: List[RequirementTag],
        test_cases: List[TestCaseTag],
        trace_map: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Calculate test coverage metrics"""
        req_ids = {r.req_id for r in requirements}
        
        # Direct trace coverage
        traced_reqs = set(trace_map.keys())
        
        # Test case coverage (via verifies attribute)
        tested_via_attr = {t.verifies_req_id for t in test_cases if t.verifies_req_id}
        
        # Combined coverage
        all_verified = traced_reqs | tested_via_attr
        uncovered = req_ids - all_verified
        
        return {
            "total_requirements": len(req_ids),
            "verified_via_trace": len(traced_reqs),
            "verified_via_test_attr": len(tested_via_attr),
            "total_verified": len(all_verified),
            "uncovered_count": len(uncovered),
            "coverage_percentage": len(all_verified) / max(len(req_ids), 1) * 100,
            "uncovered_requirements": list(uncovered),
            "test_type_breakdown": self._count_by_type(test_cases),
            "requirement_type_breakdown": self._count_req_by_type(requirements),
        }
    
    def _count_by_type(self, test_cases: List[TestCaseTag]) -> Dict[str, int]:
        """Count test cases by type"""
        counts: Dict[str, int] = {}
        for t in test_cases:
            counts[t.test_type] = counts.get(t.test_type, 0) + 1
        return counts
    
    def _count_req_by_type(self, requirements: List[RequirementTag]) -> Dict[str, int]:
        """Count requirements by type"""
        counts: Dict[str, int] = {}
        for r in requirements:
            counts[r.requirement_type] = counts.get(r.requirement_type, 0) + 1
        return counts