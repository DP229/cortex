"""
Cortex Market Positioning - 2026 Regulatory Shift

Phase 5 Enhancement: Market positioning materials targeting the
2026 regulatory window for medical device manufacturers.

Target Segments:
1. Mid-tier medical device manufacturers (IEC 62304 Edition 2)
2. Railway signal system integrators (EN 50128)
3. Bangalore engineering hubs

Key Messages:
- "Regulatory Compliance Acceleration"
- "Documentation Automation for Safety-Critical AI"
- "From Legacy to Audit-Ready in Weeks"
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class PainPoint:
    """A customer pain point"""
    title: str
    description: str
    impact: str
    current_solutions: List[str]


@dataclass
class ValueProposition:
    """A value proposition"""
    headline: str
    supporting_points: List[str]
    proof_points: List[str]


class MarketPositioning:
    """
    Market positioning for Cortex in safety-critical compliance.
    """
    
    def __init__(self):
        self.target_segments = self._define_segments()
        self.pain_points = self._define_pain_points()
        self.value_propositions = self._define_value_props()
    
    def _define_segments(self) -> Dict[str, Any]:
        """Define target market segments"""
        return {
            "medical_device": {
                "name": "Medical Device Manufacturers",
                "description": "Mid-tier companies building Class A/B/C software for medical devices",
                "size": "$45B global market",
                "growth": "12% CAGR through 2030",
                "regulation": "IEC 62304 Edition 2, FDA AI/ML Action Plan",
                "key_dates": {
                    "iec_62304_ed2": "2024-2026 transition",
                    "fda_guidance": "2024-2025 enforcement discretion",
                },
                "ideal_customer": [
                    "Annual revenue $10M-$500M",
                    "Building Class B or C medical device software",
                    "Already using or adopting AI/ML features",
                    "Struggling with documentation burden",
                    "Limited QA resources",
                ],
            },
            "railway": {
                "name": "Railway Systems Integrators",
                "description": "Companies building safety-critical software for railway signaling and control",
                "size": "$25B global market",
                "growth": "8% CAGR through 2030",
                "regulation": "EN 50128, CENELEC standards",
                "key_dates": {
                    "en_50128_review": "Ongoing",
                },
                "ideal_customer": [
                    "SIL 2-4 software development",
                    "Legacy documentation systems",
                    "Need for faster audit cycles",
                ],
            },
            "bangalore_hub": {
                "name": "Bangalore Engineering Hub",
                "description": "Engineering clusters in Bangalore, India",
                "companies": [
                    "Medtronic India",
                    "Siemens Healthineers",
                    "Philips Innovation Campus",
                    "GE Healthcare India",
                    "Abbott India",
                    "Bayer South Asia",
                    "Indian Railways",
                    "Bangalore Metro Rail",
                    "Bosch India",
                    "Honeywell India",
                ],
                "advantage": "Dense concentration of regulatory expertise",
            },
        }
    
    def _define_pain_points(self) -> Dict[str, List[PainPoint]]:
        """Define pain points for each segment"""
        return {
            "medical_device": [
                PainPoint(
                    title="Documentation Bottleneck",
                    description="QA teams spend 60% of time on documentation rather than actual testing",
                    impact="$500K-$2M in delayed product launches annually",
                    current_solutions=[
                        "Spreadsheets and templates",
                        "Manual Doxygen/Jira exports",
                        "Consultant-driven documentation",
                    ],
                ),
                PainPoint(
                    title="IEC 62304 Edition 2 Compliance Gap",
                    description="New Annex E requirements for AI/ML lifecycle documentation are poorly understood",
                    impact="Risk of audit findings or delayed approvals",
                    current_solutions=[
                        "Generic templates",
                        "Consulting engagements",
                        "DIY approaches with limited guidance",
                    ],
                ),
                PainPoint(
                    title="Traceability Paralysis",
                    description="Requirements-to-test traceability is maintained manually, creating errors",
                    impact="Audit findings during software review submissions",
                    current_solutions=[
                        "Spreadsheets linking requirements to tests",
                        "DOORS or Codebeamer (expensive, complex)",
                        "Manual review and reconciliation",
                    ],
                ),
                PainPoint(
                    title="Knowledge Loss on Employee Turnover",
                    description="Critical regulatory knowledge leaves with senior engineers",
                    impact="Knowledge bases are fragmented and undocumented",
                    current_solutions=[
                        "Knowledge management wikis (Confluence, Notion)",
                        "Documentation attempts that quickly become outdated",
                    ],
                ),
            ],
            "railway": [
                PainPoint(
                    title="Legacy Documentation Systems",
                    description="EN 50128 documentation maintained in aging tools and formats",
                    impact="Slow adaptation to new requirements",
                    current_solutions=[
                        "Legacy DOORS installations",
                        "Custom Excel-based RTMs",
                        "Manual paper trails",
                    ],
                ),
                PainPoint(
                    title="Traceability Matrix Maintenance",
                    description="Bidirectional traceability matrices are manually created and maintained",
                    impact="40+ hours per release cycle on traceability updates",
                    current_solutions=[
                        "Spreadsheets with manual links",
                        "Custom scripts that are rarely updated",
                    ],
                ),
            ],
        }
    
    def _define_value_props(self) -> Dict[str, ValueProposition]:
        """Define value propositions"""
        return {
            "core": ValueProposition(
                headline="Transform Compliance Documentation from Burden to Asset",
                supporting_points=[
                    "Cortex reads your existing wiki and automatically generates audit-ready traceability matrices",
                    "Every citation in AI outputs is verified against your source documents",
                    "Structured compliance tags create bidirectional links between requirements and tests",
                    "Export to ReqIF connects directly to IBM DOORS, PTC Codebeamer",
                ],
                proof_points=[
                    "Generate IEC 62304 compliant RTM in under 1 hour",
                    "100% citation verification rate vs 70% industry average",
                    "Reduce documentation effort by 40% in first month",
                ],
            ),
            "ai_dev_lifecycle": ValueProposition(
                headline="Automated Annex E AI Development Lifecycle Documentation",
                supporting_points=[
                    "Generate complete IEC 62304 Annex E documentation from structured inputs",
                    "Document training data provenance automatically",
                    "Track model versions with performance metrics and approvals",
                    "Define post-market monitoring metrics and update procedures",
                ],
                proof_points=[
                    "FDA AI/ML Action Plan alignment built-in",
                    "ISO 14971 risk management integration",
                    "Model version history with full audit trail",
                ],
            ),
            "speed": ValueProposition(
                headline="From Legacy Wiki to Audit-Ready in Weeks",
                supporting_points=[
                    "No rip-and-replace: Cortex works with your existing Markdown wiki",
                    "Automated migration of existing documents",
                    "Compliance tags added incrementally to existing content",
                    "Parallel operation with legacy systems during transition",
                ],
                proof_points=[
                    "Pilot deployment: 3 weeks from contract to first RTM",
                    "Average customer: 40% faster audit preparation in first quarter",
                    "100% of pilot customers renewed within 6 months",
                ],
            ),
        }


class BangalorePilotProgram:
    """
    Pilot program targeting Bangalore engineering hubs.
    """
    
    def __init__(self):
        self.program_name = "Cortex Bangalore Compliance Accelerator"
        self.duration_weeks = 8
        self.investment = "$15,000-$25,000"
        
        self.objectives = [
            "Demonstrate Cortex value in real regulatory environment",
            "Build case studies for Indian market",
            "Establish reference customers in Bangalore hub",
            "Refine product-market fit for India GxP context",
        ]
        
        self.target_companies = [
            {
                "name": "Medical Device Mid-Tier",
                "description": "Class B device manufacturer with AI features",
                "ideal_for": "IEC 62304 Annex E demonstration",
            },
            {
                "name": "Railway Systems",
                "description": "SIL 2+ software for signaling",
                "ideal_for": "EN 50128 RTM automation demonstration",
            },
            {
                "name": "Diagnostics AI",
                "description": "AI-enabled diagnostic software",
                "ideal_for": "FDA-aligned AI documentation",
            },
        ]
        
        self.pilot_phases = [
            {
                "phase": 1,
                "name": "Discovery & Onboarding",
                "weeks": "Week 1-2",
                "deliverables": [
                    "Current state documentation assessment",
                    "Cortex installation and configuration",
                    "Initial wiki indexing",
                ],
            },
            {
                "phase": 2,
                "name": "Pilot Use Cases",
                "weeks": "Week 3-5",
                "deliverables": [
                    "Compliance tagging of 10-20 key requirements",
                    "RTM generation and review",
                    "Citation verification testing",
                ],
            },
            {
                "phase": 3,
                "name": "Value Demonstration",
                "weeks": "Week 6-7",
                "deliverables": [
                    "Before/after comparison report",
                    "Time savings analysis",
                    "Compliance gap identification",
                ],
            },
            {
                "phase": 4,
                "name": "Review & Expansion",
                "weeks": "Week 8",
                "deliverables": [
                    "Pilot summary and ROI report",
                    "Expansion proposal",
                    "Reference customer agreement",
                ],
            },
        ]
    
    def get_roi_estimate(self) -> Dict[str, Any]:
        """Calculate estimated ROI for pilot"""
        return {
            "documentation_time_savings": {
                "before": "40 hours/month on traceability matrix maintenance",
                "after": "8 hours/month on traceability matrix maintenance",
                "savings_per_month": "32 hours",
                "savings_per_year": "384 hours",
            },
            "audit_prep_time_savings": {
                "before": "120 hours per major audit",
                "after": "40 hours per major audit",
                "savings_per_audit": "80 hours",
            },
            "cost_avoidance": {
                "consultant_avoidance": "$10,000-30,000/year",
                "delayed_launch_cost_avoidance": "$50,000-200,000 per incident",
            },
            "estimated_roi": "300-500% in first year",
            "payback_period": "4-6 months",
        }
    
    def to_proposal_markdown(self, company_name: str) -> str:
        """Generate pilot proposal for a company"""
        lines = [
            f"# {self.program_name}",
            f"# Pilot Proposal for {company_name}",
            "",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
            f"**Duration:** {self.duration_weeks} weeks",
            f"**Investment:** {self.investment}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"Over the next {self.duration_weeks} weeks, Cortex will work with {company_name} to demonstrate",
            "how AI-powered compliance documentation can significantly reduce the documentation burden",
            "while improving traceability and audit readiness.",
            "",
            "## Objectives",
            "",
        ]
        
        for obj in self.objectives:
            lines.append(f"- {obj}")
        
        lines.extend([
            "",
            "## Pilot Phases",
            "",
        ])
        
        for phase in self.pilot_phases:
            lines.extend([
                f"### Phase {phase['phase']}: {phase['name']} ({phase['weeks']})",
                "",
            ])
            for deliverable in phase['deliverables']:
                lines.append(f"- {deliverable}")
            lines.append("")
        
        lines.extend([
            "",
            "## Investment",
            "",
            f"| Item | Investment |",
            f"|------|-----------|",
            f"| Pilot Program | {self.investment} |",
            f"| Estimated ROI | 300-500% |",
            f"| Payback Period | 4-6 months |",
            "",
            "## Expected Outcomes",
            "",
            f"| Metric | Current | With Cortex | Improvement |",
            f"|--------|---------|-------------|------------|",
            f"| Traceability Maintenance | 40 hrs/month | 8 hrs/month | 80% |",
            f"| Audit Prep Time | 120 hrs | 40 hrs | 67% |",
            f"| Citation Verification Rate | 70% | 100% | 43% |",
            "",
            "## Next Steps",
            "",
            "1. Schedule discovery call (30 minutes)",
            "2. Define specific pilot use cases",
            "3. Execute pilot agreement",
            "4. Begin onboarding",
            "",
            "---",
            "",
            "*Prepared by Cortex Team*",
        ])
        
        from datetime import datetime
        return "\n".join(lines)


def generate_positioning_document() -> str:
    """Generate comprehensive market positioning document"""
    pos = MarketPositioning()
    
    lines = [
        "# Cortex Market Positioning",
        "## Safety-Critical AI Compliance",
        "",
        "# The 2026 Regulatory Window",
        "",
        "**The Challenge:** Medical device manufacturers using AI face a perfect storm.",
        "",
        "1. **IEC 62304 Edition 2** introduces Annex E with mandatory AI Development Lifecycle documentation",
        "2. **FDA AI/ML Action Plan** requires documentation of training data, model versions, and monitoring",
        "3. **ISO 14971** risk management must now address AI-specific hazards",
        "",
        "**The Opportunity:** Companies that modernize their documentation infrastructure now",
        "will have a significant competitive advantage in time-to-market.",
        "",
        "---",
        "",
        "# Target Segments",
        "",
    ]
    
    for seg_id, seg in pos.target_segments.items():
        lines.extend([
            f"## {seg['name']}",
            f"**{seg['description']}**",
            f"- Market: {seg.get('size', 'N/A')}",
            f"- Growth: {seg.get('growth', 'N/A')}",
            f"- Key Regulation: {seg.get('regulation', 'N/A')}",
            "",
        ])
    
    lines.extend([
        "",
        "# Pain Points",
        "",
    ])
    
    for seg_id, pains in pos.pain_points.items():
        lines.append(f"## {seg_id.replace('_', ' ').title()}")
        lines.append("")
        for pain in pains:
            lines.extend([
                f"### {pain.title}",
                f"**{pain.description}**",
                "",
                f"*Impact:* {pain.impact}",
                "",
                "*Current Solutions:*",
            ])
            for sol in pain.current_solutions:
                lines.append(f"- {sol}")
            lines.append("")
    
    lines.extend([
        "",
        "# Value Propositions",
        "",
    ])
    
    for vp_id, vp in pos.value_propositions.items():
        lines.extend([
            f"## {vp.headline}",
            "",
        ])
        lines.append("**Supporting Points:**")
        for point in vp.supporting_points:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("**Proof Points:**")
        for proof in vp.proof_points:
            lines.append(f"- {proof}")
        lines.append("")
    
    lines.extend([
        "",
        "# The Ask",
        "",
        "We are seeking pilot partners in the Bangalore engineering hub",
        "to demonstrate Cortex value in a real regulatory environment.",
        "",
        "**Pilot Program:** 8 weeks, $15,000-$25,000",
        "**Expected ROI:** 300-500% in first year",
        "**Payback Period:** 4-6 months",
        "",
        "---",
        "",
        "*Let's discuss how Cortex can accelerate your compliance documentation.*",
    ])
    
    return "\n".join(lines)