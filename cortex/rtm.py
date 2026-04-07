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
"""

import csv
import json
from io import StringIO
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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


class RTMGenerator:
    """
    Generates Requirements Traceability Matrices.
    
    Supports:
    - Forward traceability (Requirement → Test)
    - Backward traceability (Test → Requirement)
    - Safety class analysis (IEC 62304 Class A/B/C)
    - Coverage reporting
    """
    
    def __init__(self, scanner):
        """
        Initialize with a ComplianceWikiScanner.
        """
        self.scanner = scanner
    
    def generate_rtm(self) -> List[RTMEntry]:
        """
        Generate the full traceability matrix.
        
        Returns list of RTMEntry with requirement-test mappings.
        """
        scan_results = self.scanner.scan_all()
        
        # Build lookup maps
        req_by_id = {r['req_id']: r for r in scan_results['requirements']}
        test_by_id = {t['test_id']: t for t in scan_results['test_cases']}
        
        # Build trace map
        req_to_tests: Dict[str, List[str]] = {}
        
        for link in scan_results['trace_links']:
            if link['link_type'] == 'verifies':
                target = link['target_id']
                if target not in req_to_tests:
                    req_to_tests[target] = []
                req_to_tests[target].append(link['source_id'])
        
        # Add tests that verify via attribute
        for test in scan_results['test_cases']:
            if test.get('verifies_req_id'):
                req_id = test['verifies_req_id']
                if req_id not in req_to_tests:
                    req_to_tests[req_id] = []
                if test['test_id'] not in req_to_tests[req_id]:
                    req_to_tests[req_id].append(test['test_id'])
        
        # Generate RTM entries
        rtm_entries = []
        
        for req in scan_results['requirements']:
            req_id = req['req_id']
            tests = req_to_tests.get(req_id, [])
            
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
                ))
        
        return rtm_entries
    
    def _infer_test_status(self, test: Dict) -> str:
        """Infer test status from test definition"""
        # This would be enhanced with actual test execution results
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
            'Status', 'Trace Type'
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


# === RTM Writer ===

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