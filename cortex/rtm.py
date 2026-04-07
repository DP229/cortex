"""
Cortex RTM Generator - Requirements Traceability Matrix

Phase 2 Enhancement: Generates bidirectional Requirements Traceability
Matrices (RTMs) in HTML and CSV formats from tagged wiki content.

Features:
- Bidirectional traceability (Requirement ↔ Test)
- Multiple output formats (HTML, CSV)
- Safety class breakdown (IEC 62304)
- Coverage analysis
- Export to ReqIF for enterprise tools
- Circular dependency detection via Tarjan's algorithm
"""

import csv
import json
from io import StringIO
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCULAR DEPENDENCY EXCEPTION
# =============================================================================

class CircularDependencyError(Exception):
    """
    Raised when circular traceability dependencies are detected.
    
    Attributes:
        cycle_path: List of IDs forming the cycle
        cycle_type: Type of cycle (req_req, req_test, test_test)
    """
    
    def __init__(self, message: str, cycle_path: List[str], cycle_type: str = "unknown"):
        self.message = message
        self.cycle_path = cycle_path
        self.cycle_type = cycle_type
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": "circular_dependency_detected",
            "message": self.message,
            "cycle_path": self.cycle_path,
            "cycle_type": self.cycle_type,
            "formatted_path": " -> ".join(self.cycle_path),
        }


# =============================================================================
# TARJAN'S STRONGLY CONNECTED COMPONENTS ALGORITHM
# =============================================================================

class CycleDetector:
    """
    Detects circular dependencies in traceability graphs using
    Tarjan's Strongly Connected Components (SCC) algorithm.
    
    A cycle exists when a requirement or test can be reached from itself
    through a chain of trace links (e.g., REQ-001 -> TEST-001 -> REQ-001).
    
    Tarjan's algorithm runs in O(V+E) time and identifies all SCCs.
    Any SCC with more than 1 node, or a single node with a self-loop,
    indicates a cycle.
    
    Safety-Critical Context:
    - Circular dependencies violate IEC 62304 traceability requirements
    - They create ambiguous verification chains (which verifies what?)
    - Must be resolved before audit/regulatory submission
    """
    
    def __init__(self):
        # Graph adjacency list: node -> set of nodes it points to
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self.node_types: Dict[str, str] = {}  # node_id -> 'requirement' or 'test'
        self.all_nodes: Set[str] = set()
    
    def add_requirement(self, req_id: str) -> None:
        """Register a requirement node"""
        self.all_nodes.add(req_id)
        self.node_types[req_id] = 'requirement'
        if req_id not in self.graph:
            self.graph[req_id] = set()
    
    def add_test(self, test_id: str) -> None:
        """Register a test node"""
        self.all_nodes.add(test_id)
        self.node_types[test_id] = 'test'
        if test_id not in self.graph:
            self.graph[test_id] = set()
    
    def add_trace_link(self, source_id: str, target_id: str, link_type: str) -> None:
        """
        Add a traceability link between nodes.
        
        Args:
            source_id: The node making the claim (test verifies requirement)
            target_id: The node being claimed (requirement being verified)
            link_type: 'verifies', 'refines', 'conflicts', etc.
        """
        self.graph[source_id].add(target_id)
        self.all_nodes.add(source_id)
        self.all_nodes.add(target_id)
    
    def detect_cycles(self) -> List[List[str]]:
        """
        Run Tarjan's algorithm to find all cycles.
        
        Returns:
            List of cycles, where each cycle is a list of node IDs forming a loop.
            Empty list if no cycles detected.
        """
        # Tarjan's SCC algorithm state
        index_counter = [0]  # Use list for mutable int in nested function
        stack: List[str] = []
        on_stack: Set[str] = set()
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        SCCs: List[List[str]] = []
        
        def strongconnect(node: str) -> None:
            # Set the depth index for node
            indices[node] = index_counter[0]
            lowlinks[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack.add(node)
            
            # Consider successors
            for successor in self.graph.get(node, set()):
                if successor not in indices:
                    # Successor has not yet been visited
                    strongconnect(successor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[successor])
                elif successor in on_stack:
                    # Successor is on stack, hence in current SCC
                    lowlinks[node] = min(lowlinks[node], indices[successor])
            
            # If node is a root, pop the stack and generate an SCC
            if lowlinks[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                
                # Sort SCC for deterministic output
                scc.sort()
                SCCs.append(scc)
        
        # Run Tarjan's algorithm on all unvisited nodes
        for node in sorted(self.all_nodes):
            if node not in indices:
                strongconnect(node)
        
        # Filter to only actual cycles (SCCs with >1 node, or self-loops)
        cycles = []
        for scc in SCCs:
            if len(scc) > 1:
                # Multi-node cycle
                cycles.append(scc)
            elif len(scc) == 1:
                # Check for self-loop
                node = scc[0]
                if node in self.graph.get(node, set()):
                    # Self-loop detected
                    cycles.append(scc)
        
        return cycles
    
    def get_cycle_type(self, cycle: List[str]) -> str:
        """Determine the type of cycle based on node types"""
        types_in_cycle = set(self.node_types.get(node, 'unknown') for node in cycle)
        
        if 'requirement' in types_in_cycle and 'test' in types_in_cycle:
            return 'req_test'  # Requirement <-> Test cycle
        elif 'requirement' in types_in_cycle:
            return 'req_req'  # Requirement <-> Requirement cycle
        elif 'test' in types_in_cycle:
            return 'test_test'  # Test <-> Test cycle
        else:
            return 'unknown'
    
    def validate(self) -> None:
        """
        Validate the traceability graph for cycles.
        
        Raises:
            CircularDependencyError: If any cycles are detected
        """
        cycles = self.detect_cycles()
        
        if not cycles:
            return  # No cycles - graph is valid
        
        # Build detailed error messages
        errors = []
        for cycle in cycles:
            cycle_type = self.get_cycle_type(cycle)
            
            # Create cycle path with types
            path_parts = []
            for node in cycle:
                node_type = self.node_types.get(node, 'unknown')
                path_parts.append(f"{node}[{node_type}]")
            
            # Complete the cycle back to start
            path_parts.append(cycle[0])
            
            cycle_path_str = " -> ".join(path_parts)
            
            error_msg = (
                f"Circular traceability dependency detected: {cycle_path_str}. "
                f"Type: {cycle_type}. "
                f"This violates IEC 62304 traceability requirements. "
                f"Resolve by removing one of the trace links in the cycle."
            )
            
            errors.append(CircularDependencyError(
                message=error_msg,
                cycle_path=cycle,
                cycle_type=cycle_type,
            ))
        
        # Raise the first error with full details
        # (In practice, you might want to collect all and report together)
        first_error = errors[0]
        logger.error(
            "circular_dependency_detected",
            cycle_path=first_error.cycle_path,
            cycle_type=first_error.cycle_type,
        )
        raise first_error


# =============================================================================
# TOPOLOGICAL SORT
# =============================================================================

class TopologicalSorter:
    """
    Performs topological sorting on the traceability graph.
    
    Used for:
    - Determining verification order (verify leaf requirements first)
    - Ensuring no requirement is verified before its dependencies
    - Validating that trace chains don't create impossible ordering
    
    Uses Kahn's algorithm for topological sort with cycle detection.
    """
    
    def __init__(self, graph: Dict[str, Set[str]]):
        """
        Initialize with graph adjacency list.
        
        Args:
            graph: Dict mapping node ID to set of nodes it depends on
        """
        self.graph = graph
        self.all_nodes: Set[str] = set(graph.keys()) | set(
            target for targets in graph.values() for target in targets
        )
    
    def sort(self) -> Tuple[List[str], bool]:
        """
        Perform topological sort using Kahn's algorithm.
        
        Returns:
            Tuple of (sorted_list, has_cycle)
            - sorted_list: Nodes in topological order (dependencies first)
            - has_cycle: True if graph has cycles (sort is invalid)
        
        Example:
            Given: REQ-002 depends on REQ-001, TEST-001 verifies REQ-002
            Sort order: REQ-001, REQ-002, TEST-001
        """
        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {node: 0 for node in self.all_nodes}
        for node in self.graph:
            for target in self.graph[node]:
                if target in in_degree:
                    in_degree[target] += 1
        
        # Queue of nodes with no incoming edges
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        sorted_list: List[str] = []
        
        while queue:
            node = queue.popleft()
            sorted_list.append(node)
            
            # Reduce in-degree for dependent nodes
            for target in self.graph.get(node, set()):
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
        
        has_cycle = len(sorted_list) != len(self.all_nodes)
        
        return sorted_list, has_cycle
    
    def get_verification_order(self) -> Dict[str, int]:
        """
        Get verification order for requirements/tests.
        
        Returns:
            Dict mapping node ID to its position in verification order
            (lower number = verify first)
        
        Nodes are sorted by:
        1. Type (requirements before tests)
        2. Dependency depth (leaf nodes first)
        """
        sorted_list, has_cycle = self.sort()
        
        if has_cycle:
            logger.warning("verification_order_has_cycles_order_may_be_invalid")
        
        # Group by type
        requirements = []
        tests = []
        
        for node in sorted_list:
            if node.startswith('REQ-') or node.startswith('SWRS-') or node.startswith('SRS-'):
                requirements.append(node)
            elif node.startswith('TEST-') or node.startswith('TC-'):
                tests.append(node)
            else:
                # Unknown type - append at end
                requirements.append(node)
        
        # Interleave: requirements first, then tests
        ordered = requirements + tests
        
        return {node: idx for idx, node in enumerate(ordered)}


# =============================================================================
# RTM ENTRY
# =============================================================================

@dataclass
class RTMEntry:
    """A single entry in the traceability matrix"""
    req_id: str
    req_content: str
    req_type: str
    safety_class: Optional[str]
    priority: str
    test_id: Optional[str]
    test_content: Optional[str]
    test_type: Optional[str]
    verification_method: Optional[str]
    test_status: str  # verified, pending, failed, not_covered
    trace_type: str  # direct, indirect, none
    depth: int = 0  # Dependency depth for verification ordering


@dataclass
class TraceValidationResult:
    """Result of trace validation"""
    valid: bool
    cycles: List[List[str]] = field(default_factory=list)
    sorted_order: List[str] = field(default_factory=list)
    has_cycles: bool = False
    error_messages: List[str] = field(default_factory=list)


# =============================================================================
# RTM GENERATOR
# =============================================================================

class RTMGenerator:
    """
    Generates Requirements Traceability Matrices.
    
    Supports:
    - Forward traceability (Requirement → Test)
    - Backward traceability (Test → Requirement)
    - Safety class analysis (IEC 62304 Class A/B/C)
    - Coverage reporting
    - Circular dependency detection (Tarjan's SCC)
    - Topological sort for verification ordering
    """
    
    def __init__(self, scanner, strict_cycle_check: bool = True):
        """
        Initialize with a ComplianceWikiScanner.
        
        Args:
            scanner: ComplianceWikiScanner instance
            strict_cycle_check: If True, raise exception on cycles.
                               If False, warn but continue.
        """
        self.scanner = scanner
        self.strict_cycle_check = strict_cycle_check
    
    def _build_trace_map(self) -> Tuple[Dict[str, List[str]], CycleDetector]:
        """
        Build the traceability map from scan results.
        
        Returns:
            Tuple of (req_to_tests dict, CycleDetector instance)
        
        The trace map maps each requirement to the tests that verify it:
            REQ-001 -> [TEST-001, TEST-002]
            REQ-002 -> [TEST-003]
        
        Also builds reverse mapping for cycle detection:
            TEST-001 -> [REQ-001]
            TEST-002 -> [REQ-001]
            TEST-003 -> [REQ-002]
        """
        scan_results = self.scanner.scan_all()
        
        # Initialize cycle detector
        cycle_detector = CycleDetector()
        
        # Register all requirements and tests as nodes
        for req in scan_results['requirements']:
            cycle_detector.add_requirement(req['req_id'])
        
        for test in scan_results['test_cases']:
            cycle_detector.add_test(test['test_id'])
        
        # Build forward trace map (requirement -> tests that verify it)
        req_to_tests: Dict[str, List[str]] = defaultdict(list)
        
        # Process trace links
        for link in scan_results['trace_links']:
            source_id = link['source_id']
            target_id = link['target_id']
            link_type = link['link_type']
            
            # Add edge for cycle detection
            # Direction: test -> requirement (test points to what it verifies)
            cycle_detector.add_trace_link(source_id, target_id, link_type)
            
            # Build forward map
            if link_type == 'verifies':
                req_to_tests[target_id].append(source_id)
        
        # Add tests that verify via attribute
        for test in scan_results['test_cases']:
            if test.get('verifies_req_id'):
                req_id = test['verifies_req_id']
                test_id = test['test_id']
                
                # Add edge for cycle detection
                cycle_detector.add_trace_link(test_id, req_id, 'verifies')
                
                # Build forward map
                if req_id not in req_to_tests:
                    req_to_tests[req_id] = []
                if test_id not in req_to_tests[req_id]:
                    req_to_tests[req_id].append(test_id)
        
        return dict(req_to_tests), cycle_detector
    
    def _validate_traceability(self) -> TraceValidationResult:
        """
        Validate traceability graph for cycles and ordering.
        
        Returns:
            TraceValidationResult with validation status and details
        """
        req_to_tests, cycle_detector = self._build_trace_map()
        
        result = TraceValidationResult(valid=True)
        
        # Check for cycles using Tarjan's algorithm
        cycles = cycle_detector.detect_cycles()
        
        if cycles:
            result.has_cycles = True
            result.cycles = cycles
            result.valid = False
            
            for cycle in cycles:
                cycle_type = cycle_detector.get_cycle_type(cycle)
                path_str = " -> ".join(cycle + [cycle[0]])
                result.error_messages.append(
                    f"Circular dependency ({cycle_type}): {path_str}"
                )
            
            logger.error(
                "traceability_validation_failed",
                cycle_count=len(cycles),
                cycles=cycles,
            )
        else:
            # Perform topological sort for ordering
            # Build graph for sorting: requirement -> tests
            graph: Dict[str, Set[str]] = defaultdict(set)
            for req_id, test_ids in req_to_tests.items():
                for test_id in test_ids:
                    graph[req_id].add(test_id)
            
            sorter = TopologicalSorter(graph)
            sorted_list, has_cycle = sorter.sort()
            result.sorted_order = sorted_list
            
            if has_cycle:
                logger.warning("graph_has_cycles_despite_tarjan_check")
        
        return result
    
    def generate_rtm(self, validate: bool = True) -> List[RTMEntry]:
        """
        Generate the full traceability matrix.
        
        Args:
            validate: If True, validate for cycles before generating.
                     If cycles found in strict mode, raises CircularDependencyError.
        
        Returns:
            List of RTMEntry with requirement-test mappings.
        
        Raises:
            CircularDependencyError: If validate=True and cycles detected
        """
        # Validate traceability if requested
        if validate:
            validation_result = self._validate_traceability()
            
            if not validation_result.valid:
                if self.strict_cycle_check:
                    # Raise exception with first cycle
                    first_cycle = validation_result.cycles[0]
                    cycle_detector = CycleDetector()
                    # Re-build to get cycle type
                    _, cd = self._build_trace_map()
                    for cycle in validation_result.cycles:
                        if cycle == first_cycle:
                            cycle_type = cd.get_cycle_type(cycle)
                            path_str = " -> ".join(cycle + [cycle[0]])
                            raise CircularDependencyError(
                                message=(
                                    f"Traceability graph contains circular dependency: {path_str}. "
                                    f"This must be resolved before generating RTM. "
                                    f"Remove one trace link from the cycle to proceed."
                                ),
                                cycle_path=cycle,
                                cycle_type=cycle_type,
                            )
                else:
                    # Warning only mode
                    logger.warning(
                        "rtm_generated_with_circular_dependencies",
                        errors=validation_result.error_messages,
                    )
        
        scan_results = self.scanner.scan_all()
        
        # Build lookup maps
        req_by_id = {r['req_id']: r for r in scan_results['requirements']}
        test_by_id = {t['test_id']: t for t in scan_results['test_cases']}
        
        # Build trace map
        req_to_tests, _ = self._build_trace_map()
        
        # Calculate verification depths using topological sort
        verification_order: Dict[str, int] = {}
        try:
            _, cycle_detector = self._build_trace_map()
            # Build graph for depth calculation
            graph: Dict[str, Set[str]] = defaultdict(set)
            for req_id, test_ids in req_to_tests.items():
                for test_id in test_ids:
                    graph[req_id].add(test_id)
            
            sorter = TopologicalSorter(graph)
            verification_order = sorter.get_verification_order()
        except Exception:
            # If ordering fails, use default order
            verification_order = {req_id: idx for idx, req_id in enumerate(req_to_tests.keys())}
        
        # Generate RTM entries
        rtm_entries = []
        
        for req in scan_results['requirements']:
            req_id = req['req_id']
            tests = req_to_tests.get(req_id, [])
            depth = verification_order.get(req_id, 0)
            
            if tests:
                for test_id in tests:
                    test = test_by_id.get(test_id)
                    if test:
                        rtm_entries.append(RTMEntry(
                            req_id=req_id,
                            req_content=req['content'],
                            req_type=req['type'],
                            safety_class=req.get('safety_class'),
                            priority=req['priority'],
                            test_id=test_id,
                            test_content=test['content'],
                            test_type=test['test_type'],
                            verification_method=test['verification_method'],
                            test_status=self._infer_test_status(test),
                            trace_type='direct',
                            depth=depth,
                        ))
            else:
                rtm_entries.append(RTMEntry(
                    req_id=req_id,
                    req_content=req['content'],
                    req_type=req['type'],
                    safety_class=req.get('safety_class'),
                    priority=req['priority'],
                    test_id=None,
                    test_content=None,
                    test_type=None,
                    verification_method=None,
                    test_status='not_covered',
                    trace_type='none',
                    depth=depth,
                ))
        
        # Handle orphan tests (tests without traced requirements)
        covered_req_ids = set(req_to_tests.keys())
        for test in scan_results['test_cases']:
            if test.get('verifies_req_id') and test['verifies_req_id'] not in covered_req_ids:
                rtm_entries.append(RTMEntry(
                    req_id=test['verifies_req_id'],
                    req_content='[Requirement not found in wiki]',
                    req_type='unknown',
                    safety_class=None,
                    priority='unknown',
                    test_id=test['test_id'],
                    test_content=test['content'],
                    test_type=test['test_type'],
                    verification_method=test['verification_method'],
                    test_status='orphan_test',
                    trace_type='indirect',
                    depth=verification_order.get(test['test_id'], 999),
                ))
        
        # Sort by verification order (depth)
        rtm_entries.sort(key=lambda e: (e.depth, e.req_id))
        
        return rtm_entries
    
    def generate_rtm_unsafe(self) -> List[RTMEntry]:
        """
        Generate RTM without cycle validation.
        
        WARNING: Use only for debugging/inspection. The resulting RTM
        may contain circular dependencies that violate compliance requirements.
        """
        return self.generate_rtm(validate=False)
    
    def _infer_test_status(self, test: Dict) -> str:
        """Infer test status from test definition"""
        content_lower = test.get('content', '').lower()
        
        if 'pass' in content_lower or 'verified' in content_lower:
            return 'verified'
        elif 'fail' in content_lower or 'rejected' in content_lower:
            return 'failed'
        elif test.get('automated'):
            return 'pending'
        else:
            return 'pending'
    
    def to_html(
        self,
        title: str = "Requirements Traceability Matrix",
        include_css: bool = True,
    ) -> str:
        """
        Generate RTM as HTML table.
        """
        entries = self.generate_rtm()
        
        html_parts = []
        
        # HTML header
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html><head>')
        html_parts.append(f'<title>{title}</title>')
        html_parts.append('<meta charset="utf-8">')
        
        if include_css:
            html_parts.append(self._get_css())
        
        html_parts.append('</head><body>')
        html_parts.append(f'<h1>{title}</h1>')
        html_parts.append(f'<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
        
        # Summary
        summary = self._generate_summary(entries)
        html_parts.append(self._summary_to_html(summary))
        
        # Coverage by safety class
        html_parts.append(self._safety_class_html(entries))
        
        # Main table
        html_parts.append('<table class="rtm-table">')
        html_parts.append(self._table_header())
        
        for entry in entries:
            html_parts.append(self._entry_to_row(entry))
        
        html_parts.append('</table>')
        
        # Footer
        html_parts.append('<div class="footer">')
        html_parts.append('<p>Generated by Cortex Compliance Engine</p>')
        html_parts.append('</div>')
        
        html_parts.append('</body></html>')
        
        return '\n'.join(html_parts)
    
    def to_csv(self) -> str:
        """
        Generate RTM as CSV.
        """
        entries = self.generate_rtm()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Req ID', 'Requirement', 'Req Type', 'Safety Class', 'Priority',
            'Test ID', 'Test Description', 'Test Type', 'Verification Method',
            'Status', 'Trace Type', 'Verification Depth'
        ])
        
        for entry in entries:
            writer.writerow([
                entry.req_id,
                entry.req_content[:200] + '...' if len(entry.req_content) > 200 else entry.req_content,
                entry.req_type,
                entry.safety_class or '',
                entry.priority,
                entry.test_id or '',
                entry.test_content[:100] + '...' if entry.test_content and len(entry.test_content) > 100 else (entry.test_content or ''),
                entry.test_type or '',
                entry.verification_method or '',
                entry.test_status,
                entry.trace_type,
                entry.depth,
            ])
        
        return output.getvalue()
    
    def to_json(self) -> str:
        """
        Generate RTM as JSON.
        """
        entries = self.generate_rtm()
        
        return json.dumps({
            "generated_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "summary": self._generate_summary(entries),
            "entries": [
                {
                    "req_id": e.req_id,
                    "req_content": e.req_content,
                    "req_type": e.req_type,
                    "safety_class": e.safety_class,
                    "priority": e.priority,
                    "test_id": e.test_id,
                    "test_content": e.test_content,
                    "test_type": e.test_type,
                    "verification_method": e.verification_method,
                    "test_status": e.test_status,
                    "trace_type": e.trace_type,
                    "verification_depth": e.depth,
                }
                for e in entries
            ]
        }, indent=2)
    
    def _generate_summary(self, entries: List[RTMEntry]) -> Dict[str, Any]:
        """Generate summary statistics"""
        total_reqs = len(set(e.req_id for e in entries))
        covered_reqs = len(set(e.req_id for e in entries if e.test_status != 'not_covered'))
        verified = sum(1 for e in entries if e.test_status == 'verified')
        pending = sum(1 for e in entries if e.test_status == 'pending')
        failed = sum(1 for e in entries if e.test_status == 'failed')
        not_covered = sum(1 for e in entries if e.test_status == 'not_covered')
        
        # Safety class breakdown
        safety_classes: Dict[str, Dict] = {}
        for e in entries:
            if e.safety_class:
                if e.safety_class not in safety_classes:
                    safety_classes[e.safety_class] = {'total': 0, 'covered': 0}
                safety_classes[e.safety_class]['total'] += 1
                if e.test_status != 'not_covered':
                    safety_classes[e.safety_class]['covered'] += 1
        
        return {
            'total_requirements': total_reqs,
            'covered_requirements': covered_reqs,
            'coverage_percentage': (covered_reqs / max(total_reqs, 1)) * 100,
            'verified': verified,
            'pending': pending,
            'failed': failed,
            'not_covered': not_covered,
            'safety_classes': safety_classes,
        }
    
    def _summary_to_html(self, summary: Dict) -> str:
        """Convert summary to HTML"""
        html = '<div class="summary">'
        html += '<h2>Summary</h2>'
        html += '<table>'
        html += f'<tr><td>Total Requirements</td><td>{summary["total_requirements"]}</td></tr>'
        html += f'<tr><td>Covered Requirements</td><td>{summary["covered_requirements"]} ({summary["coverage_percentage"]:.1f}%)</td></tr>'
        html += f'<tr><td>Verified</td><td class="status-verified">{summary["verified"]}</td></tr>'
        html += f'<tr><td>Pending</td><td class="status-pending">{summary["pending"]}</td></tr>'
        html += f'<tr><td>Failed</td><td class="status-failed">{summary["failed"]}</td></tr>'
        html += f'<tr><td>Not Covered</td><td class="status-not-covered">{summary["not_covered"]}</td></tr>'
        html += '</table>'
        html += '</div>'
        return html
    
    def _safety_class_html(self, entries: List[RTMEntry]) -> str:
        """Generate safety class breakdown HTML"""
        safety_classes: Dict[str, Dict[str, int]] = {}
        
        for e in entries:
            sc = e.safety_class or 'unclassified'
            if sc not in safety_classes:
                safety_classes[sc] = {'total': 0, 'covered': 0}
            safety_classes[sc]['total'] += 1
            if e.test_status != 'not_covered':
                safety_classes[sc]['covered'] += 1
        
        html = '<div class="safety-breakdown">'
        html += '<h2>Coverage by Safety Class (IEC 62304)</h2>'
        html += '<table>'
        html += '<tr><th>Safety Class</th><th>Total</th><th>Covered</th><th>Coverage</th></tr>'
        
        for sc in sorted(safety_classes.keys()):
            data = safety_classes[sc]
            coverage = (data['covered'] / max(data['total'], 1)) * 100
            css_class = 'high' if coverage >= 80 else 'medium' if coverage >= 50 else 'low'
            html += f'<tr><td>{sc}</td><td>{data["total"]}</td><td>{data["covered"]}</td>'
            html += f'<td class="coverage-{css_class}">{coverage:.1f}%</td></tr>'
        
        html += '</table></div>'
        return html
    
    def _table_header(self) -> str:
        """Generate HTML table header"""
        return '''
        <thead>
        <tr>
            <th>Req ID</th>
            <th>Requirement</th>
            <th>Type</th>
            <th>Class</th>
            <th>Priority</th>
            <th>Test ID</th>
            <th>Test Description</th>
            <th>Method</th>
            <th>Status</th>
            <th>Depth</th>
        </tr>
        </thead>
        <tbody>
        '''
    
    def _entry_to_row(self, entry: RTMEntry) -> str:
        """Convert RTMEntry to HTML table row"""
        status_class = f'status-{entry.test_status}'
        
        req_cell = entry.req_content[:80] + '...' if len(entry.req_content) > 80 else entry.req_content
        req_cell = req_cell.replace('<', '&lt;').replace('>', '&gt;')
        
        test_cell = ''
        if entry.test_content:
            test_cell = entry.test_content[:60] + '...' if len(entry.test_content) > 60 else entry.test_content
            test_cell = test_cell.replace('<', '&lt;').replace('>', '&gt;')
        
        return f'''
        <tr>
            <td class="req-id">{entry.req_id}</td>
            <td class="req-content">{req_cell}</td>
            <td>{entry.req_type}</td>
            <td class="safety-class">{entry.safety_class or ''}</td>
            <td>{entry.priority}</td>
            <td class="test-id">{entry.test_id or ''}</td>
            <td class="test-content">{test_cell}</td>
            <td>{entry.verification_method or ''}</td>
            <td class="{status_class}">{entry.test_status}</td>
            <td>{entry.depth}</td>
        </tr>
        '''
    
    def _get_css(self) -> str:
        """Get CSS for HTML output"""
        return '''
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        h2 { color: #555; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4472C4; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .summary { background-color: #f0f0f0; padding: 15px; border-radius: 5px; }
        .summary table { width: auto; }
        .req-id, .test-id { font-family: monospace; font-weight: bold; }
        .status-verified { background-color: #d4edda; color: #155724; }
        .status-pending { background-color: #fff3cd; color: #856404; }
        .status-failed { background-color: #f8d7da; color: #721c24; }
        .status-not-covered { background-color: #f1f1f1; color: #666; }
        .coverage-high { color: green; font-weight: bold; }
        .coverage-medium { color: orange; }
        .coverage-low { color: red; }
        .footer { margin-top: 30px; font-size: 0.8em; color: #666; }
        </style>
        '''


# =============================================================================
# RTM WRITER
# =============================================================================

class RTMExporter:
    """
    Exports RTM to various formats.
    """
    
    def __init__(self, generator: RTMGenerator):
        self.generator = generator
    
    def export_html(self, output_path: str) -> None:
        """Export RTM to HTML file"""
        html = self.generator.to_html()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Exported RTM to {output_path}")
    
    def export_csv(self, output_path: str) -> None:
        """Export RTM to CSV file"""
        csv_content = self.generator.to_csv()
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_content)
        logger.info(f"Exported RTM to {output_path}")
    
    def export_json(self, output_path: str) -> None:
        """Export RTM to JSON file"""
        json_content = self.generator.to_json()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
        logger.info(f"Exported RTM to {output_path}")