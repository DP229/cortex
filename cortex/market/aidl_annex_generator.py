"""
Cortex AI Planning - Annex E AI Development Lifecycle Documentation

Phase 5 Enhancement: Automated generation of IEC 62304 Edition 2
Annex E "AI Development Lifecycle" (AIDL) documentation for
AI-enabled medical device manufacturers.

Key Features:
- Automated AIDL document generation
- IEC 62304 Edition 2 compliance mapping
- AI-specific risk management documentation
- Training data provenance tracking
- Model monitoring and update procedures
- FDA AI/ML Action Plan alignment

For the 2026 regulatory shift where medical device manufacturers
must document their AI development lifecycle.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json


class AIDLPhase(str, Enum):
    """AI Development Lifecycle phases (per IEC 62304 Annex E)"""
    PLANNING = "planning"
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"
    MAINTENANCE = "maintenance"


class RiskLevel(str, Enum):
    """Risk classification for AI features"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AIDLRequirement:
    """A requirement from the AI Development Plan"""
    req_id: str
    phase: AIDLPhase
    description: str
    rationale: str
    regulation_reference: str


@dataclass
class TrainingDataRecord:
    """Record of training data used for AI model"""
    data_id: str
    source: str
    description: str
    volume: str
    collection_date: str
    preprocessing_steps: List[str]
    bias_assessment: str
    consent_verified: bool
    regulatory_basis: str


@dataclass
class ModelVersionRecord:
    """Record of a model version"""
    version_id: str
    training_data_ids: List[str]
    training_date: str
    architecture: str
    hyperparameters: Dict[str, Any]
    performance_metrics: Dict[str, float]
    limitations: List[str]
    approved_for_deployment: bool
    reviewer: str
    approval_date: str


@dataclass
class MonitoringMetric:
    """Metric for post-deployment monitoring"""
    metric_name: str
    baseline_value: float
    threshold: str  # acceptable range
    current_value: Optional[float] = None
    last_measured: Optional[str] = None
    alert_triggered: bool = False


@dataclass
class AIDLDocument:
    """
    Complete AI Development Lifecycle documentation.
    
    This document satisfies IEC 62304 Edition 2 Annex E requirements.
    """
    
    # Document metadata
    document_id: str = ""
    device_name: str = ""
    device_description: str = ""
    software_version: str = ""
    generated_date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    
    # AI System Description
    ai_system_purpose: str = ""
    ai_system_inputs: List[str] = field(default_factory=list)
    ai_system_outputs: List[str] = field(default_factory=list)
    ai_system_classification: str = ""  # A, B, or C per IEC 62304
    
    # Development Lifecycle
    development_approach: str = ""
    ai_specific_activities: Dict[AIDLPhase, List[str]] = field(default_factory=dict)
    
    # Requirements
    functional_requirements: List[AIDLRequirement] = field(default_factory=list)
    performance_requirements: List[AIDLRequirement] = field(default_factory=list)
    safety_requirements: List[AIDLRequirement] = field(default_factory=list)
    
    # Training Data Documentation
    training_data: List[TrainingDataRecord] = field(default_factory=list)
    test_data: List[TrainingDataRecord] = field(default_factory=list)
    
    # Model Version History
    model_versions: List[ModelVersionRecord] = field(default_factory=list)
    
    # Risk Management
    risk_level: RiskLevel = RiskLevel.MODERATE
    risk_management_approach: str = ""
    identified_hazards: List[Dict[str, str]] = field(default_factory=list)
    mitigation_measures: List[Dict[str, str]] = field(default_factory=list)
    
    # Monitoring
    monitoring_metrics: List[MonitoringMetric] = field(default_factory=list)
    update_procedure: str = ""
    rollback_procedure: str = ""
    
    # FDA Alignment
    fda_action_plan_alignment: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "document_id": self.document_id,
            "device_name": self.device_name,
            "device_description": self.device_description,
            "software_version": self.software_version,
            "generated_date": self.generated_date,
            "ai_system": {
                "purpose": self.ai_system_purpose,
                "inputs": self.ai_system_inputs,
                "outputs": self.ai_system_outputs,
                "classification": self.ai_system_classification,
            },
            "development_approach": self.development_approach,
            "requirements": {
                "functional": [r.__dict__ for r in self.functional_requirements],
                "performance": [r.__dict__ for r in self.performance_requirements],
                "safety": [r.__dict__ for r in self.safety_requirements],
            },
            "training_data": [t.__dict__ for t in self.training_data],
            "test_data": [t.__dict__ for t in self.test_data],
            "model_versions": [m.__dict__ for m in self.model_versions],
            "risk_management": {
                "level": self.risk_level.value,
                "approach": self.risk_management_approach,
                "hazards": self.identified_hazards,
                "mitigations": self.mitigation_measures,
            },
            "monitoring": {
                "metrics": [m.__dict__ for m in self.monitoring_metrics],
                "update_procedure": self.update_procedure,
                "rollback_procedure": self.rollback_procedure,
            },
            "fda_alignment": self.fda_action_plan_alignment,
        }
    
    def to_json(self) -> str:
        """Export as JSON"""
        return json.dumps(self.to_dict(), indent=2)


class AIDLGenerator:
    """
    Generator for AI Development Lifecycle documentation.
    
    Creates IEC 62304 Annex E compliant documentation
    from structured inputs.
    """
    
    def __init__(self):
        self.document = AIDLDocument()
    
    def configure(
        self,
        device_name: str,
        device_description: str,
        software_version: str,
        ai_system_purpose: str,
        ai_system_inputs: List[str],
        ai_system_outputs: List[str],
        classification: str = "B",
    ) -> 'AIDLGenerator':
        """Configure basic document metadata"""
        self.document.document_id = f"AIDL-{device_name.upper().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d')}"
        self.document.device_name = device_name
        self.document.device_description = device_description
        self.document.software_version = software_version
        self.document.ai_system_purpose = ai_system_purpose
        self.document.ai_system_inputs = ai_system_inputs
        self.document.ai_system_outputs = ai_system_outputs
        self.document.ai_system_classification = classification
        return self
    
    def add_training_data(
        self,
        source: str,
        description: str,
        volume: str,
        collection_date: str,
        preprocessing: List[str],
        bias_assessment: str,
        consent_verified: bool,
    ) -> 'AIDLGenerator':
        """Add a training data record"""
        data_id = f"TD-{len(self.document.training_data) + 1:03d}"
        
        record = TrainingDataRecord(
            data_id=data_id,
            source=source,
            description=description,
            volume=volume,
            collection_date=collection_date,
            preprocessing_steps=preprocessing,
            bias_assessment=bias_assessment,
            consent_verified=consent_verified,
            regulatory_basis="GDPR, HIPAA, or applicable regulation",
        )
        
        self.document.training_data.append(record)
        return self
    
    def add_model_version(
        self,
        training_data_ids: List[str],
        architecture: str,
        hyperparameters: Dict[str, Any],
        performance_metrics: Dict[str, float],
        limitations: List[str],
        approved: bool,
        reviewer: str,
    ) -> 'AIDLGenerator':
        """Add a model version record"""
        version_id = f"MV-{len(self.document.model_versions) + 1:03d}"
        
        record = ModelVersionRecord(
            version_id=version_id,
            training_data_ids=training_data_ids,
            training_date=datetime.now().strftime('%Y-%m-%d'),
            architecture=architecture,
            hyperparameters=hyperparameters,
            performance_metrics=performance_metrics,
            limitations=limitations,
            approved_for_deployment=approved,
            reviewer=reviewer,
            approval_date=datetime.now().strftime('%Y-%m-%d') if approved else "Pending",
        )
        
        self.document.model_versions.append(record)
        return self
    
    def add_functional_requirement(
        self,
        req_id: str,
        description: str,
        rationale: str,
    ) -> 'AIDLGenerator':
        """Add a functional requirement"""
        req = AIDLRequirement(
            req_id=req_id,
            phase=AIDLPhase.REQUIREMENTS,
            description=description,
            rationale=rationale,
            regulation_reference="IEC 62304:2024 Annex E.4.1",
        )
        self.document.functional_requirements.append(req)
        return self
    
    def add_safety_requirement(
        self,
        req_id: str,
        description: str,
        rationale: str,
    ) -> 'AIDLGenerator':
        """Add a safety requirement"""
        req = AIDLRequirement(
            req_id=req_id,
            phase=AIDLPhase.REQUIREMENTS,
            description=description,
            rationale=rationale,
            regulation_reference="IEC 62304:2024 Annex E.4.3",
        )
        self.document.safety_requirements.append(req)
        return self
    
    def add_monitoring_metric(
        self,
        name: str,
        baseline: float,
        threshold: str,
    ) -> 'AIDLGenerator':
        """Add a monitoring metric"""
        metric = MonitoringMetric(
            metric_name=name,
            baseline_value=baseline,
            threshold=threshold,
        )
        self.document.monitoring_metrics.append(metric)
        return self
    
    def generate(self) -> AIDLDocument:
        """Generate the complete AIDL document"""
        # Set default development approach if not specified
        if not self.document.development_approach:
            self.document.development_approach = (
                "Agile development with continuous integration/continuous deployment (CI/CD). "
                "AI model training performed in isolated environment with version control. "
                "All model versions documented with performance metrics and approved prior to deployment."
            )
        
        # Set default risk management approach
        if not self.document.risk_management_approach:
            self.document.risk_management_approach = (
                "Risk management performed per ISO 14971. AI-specific hazards identified through "
                "Failure Mode and Effects Analysis (FMEA) and Hazard Analysis. "
                "Mitigation measures include deterministic post-processing, confidence thresholds, "
                "and human-in-the-loop verification for critical decisions."
            )
        
        # Set default update/rollback procedures
        if not self.document.update_procedure:
            self.document.update_procedure = (
                "Model updates require: (1) New training data documentation, "
                "(2) Performance validation against baseline, "
                "(3) Safety regression testing, "
                "(4) QA review and approval, "
                "(5) Documented change record in design history file."
            )
        
        if not self.document.rollback_procedure:
            self.document.rollback_procedure = (
                "Previous validated model version maintained in model registry. "
                "Rollback procedure: (1) Disable current model, (2) Activate previous version, "
                "(3) Verify system behavior, (4) Document rollback in change record."
            )
        
        # FDA Action Plan alignment
        self.document.fda_action_plan_alignment = {
            "1_improve": "Multi-factor performance monitoring with alerting",
            "2_good_ml": "Bias and fairness testing per IEEE 7001",
            "3_real_world": "Post-deployment monitoring metrics defined",
            "4_focus": "Training data provenance documented",
            "5_independence": "Human oversight of AI decisions documented",
            "6_t grasslands": "Model limitations documented and communicated",
        }
        
        return self.document


class AIDLDocumentExporter:
    """Exports AIDL documents to various formats"""
    
    def __init__(self, document: AIDLDocument):
        self.document = document
    
    def to_markdown(self) -> str:
        """Generate Markdown version of AIDL document"""
        lines = [
            f"# AI Development Lifecycle (AIDL) Document",
            f"# Annex E - IEC 62304 Edition 2",
            "",
            f"**Document ID:** {self.document.document_id}",
            f"**Device:** {self.document.device_name}",
            f"**Version:** {self.document.software_version}",
            f"**Date:** {self.document.generated_date}",
            "",
            "---",
            "",
        ]
        
        # AI System Description
        lines.extend([
            "## 1. AI System Description",
            "",
            f"**Purpose:** {self.document.ai_system_purpose}",
            "",
            f"**Classification:** IEC 62304 Class {self.document.ai_system_classification}",
            "",
            "**Inputs:**",
        ])
        for inp in self.document.ai_system_inputs:
            lines.append(f"- {inp}")
        
        lines.extend([
            "",
            "**Outputs:**",
        ])
        for out in self.document.ai_system_outputs:
            lines.append(f"- {out}")
        
        # Development Approach
        lines.extend([
            "",
            "## 2. Development Approach",
            "",
            self.document.development_approach,
            "",
        ])
        
        # Requirements
        lines.extend([
            "",
            "## 3. Requirements",
            "",
            "### 3.1 Functional Requirements",
            "",
        ])
        for req in self.document.functional_requirements:
            lines.extend([
                f"**{req.req_id}:** {req.description}",
                f"- Rationale: {req.rationale}",
                f"- Reference: {req.regulation_reference}",
                "",
            ])
        
        lines.extend([
            "",
            "### 3.2 Safety Requirements",
            "",
        ])
        for req in self.document.safety_requirements:
            lines.extend([
                f"**{req.req_id}:** {req.description}",
                f"- Rationale: {req.rationale}",
                f"- Reference: {req.regulation_reference}",
                "",
            ])
        
        # Training Data
        lines.extend([
            "",
            "## 4. Training Data Documentation",
            "",
            "### 4.1 Training Data",
            "",
        ])
        
        for td in self.document.training_data:
            lines.extend([
                f"#### {td.data_id}: {td.source}",
                "",
                f"- **Description:** {td.description}",
                f"- **Volume:** {td.volume}",
                f"- **Collection Date:** {td.collection_date}",
                f"- **Preprocessing:** {', '.join(td.preprocessing_steps)}",
                f"- **Bias Assessment:** {td.bias_assessment}",
                f"- **Consent Verified:** {'Yes' if td.consent_verified else 'No'}",
                "",
            ])
        
        # Model Versions
        lines.extend([
            "",
            "## 5. Model Version History",
            "",
        ])
        
        for mv in self.document.model_versions:
            lines.extend([
                f"### {mv.version_id}",
                "",
                f"- **Architecture:** {mv.architecture}",
                f"- **Training Date:** {mv.training_date}",
                f"- **Approved:** {'Yes' if mv.approved_for_deployment else 'No'}",
                f"- **Reviewer:** {mv.reviewer}",
                "",
                f"**Performance Metrics:**",
            ])
            for metric, value in mv.performance_metrics.items():
                lines.append(f"- {metric}: {value:.4f}")
            
            if mv.limitations:
                lines.extend([
                    "",
                    f"**Limitations:**",
                ])
                for limit in mv.limitations:
                    lines.append(f"- {limit}")
            
            lines.append("")
        
        # Risk Management
        lines.extend([
            "",
            "## 6. Risk Management",
            "",
            f"**Risk Level:** {self.document.risk_level.value.upper()}",
            "",
            f"**Approach:** {self.document.risk_management_approach}",
            "",
        ])
        
        if self.document.identified_hazards:
            lines.extend([
                "",
                "**Identified Hazards:**",
            ])
            for hazard in self.document.identified_hazards:
                lines.append(f"- {hazard.get('description', '')}")
            lines.append("")
        
        if self.document.mitigation_measures:
            lines.extend([
                "",
                "**Mitigation Measures:**",
            ])
            for mit in self.document.mitigation_measures:
                lines.append(f"- {mit.get('description', '')}")
            lines.append("")
        
        # Monitoring
        lines.extend([
            "",
            "## 7. Post-Market Monitoring",
            "",
            "**Monitoring Metrics:**",
        ])
        
        for metric in self.document.monitoring_metrics:
            lines.extend([
                f"- **{metric.metric_name}:**",
                f"  - Baseline: {metric.baseline_value}",
                f"  - Threshold: {metric.threshold}",
                f"  - Last Value: {metric.current_value or 'N/A'}",
                "",
            ])
        
        lines.extend([
            "",
            "**Update Procedure:**",
            f"{self.document.update_procedure}",
            "",
            "**Rollback Procedure:**",
            f"{self.document.rollback_procedure}",
            "",
        ])
        
        # FDA Alignment
        lines.extend([
            "",
            "## 8. FDA AI/ML Action Plan Alignment",
            "",
            "| Action | Implementation |",
            "|--------|---------------|",
        ])
        for action, implementation in self.document.fda_action_plan_alignment.items():
            lines.append(f"| {action} | {implementation} |")
        
        lines.extend([
            "",
            "---",
            "",
            f"*Generated by Cortex AI Planning Module - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        
        return "\n".join(lines)
    
    def to_html(self) -> str:
        """Generate HTML version"""
        md = self.to_markdown()
        
        # Simple Markdown to HTML conversion
        html = md.replace('# ', '<h1>').replace('\n## ', '</h1>\n<h2>').replace('\n### ', '</h2>\n<h3>')
        html = html.replace('**', '<strong>').replace('**', '</strong>')
        html = html.replace('- ', '<li>').replace('\n\n', '</li>\n')
        html = html.replace('---', '<hr>')
        html = f"<html><body>{html}</body></html>"
        
        return html


def create_aidl_document(
    device_name: str,
    device_description: str,
    version: str,
    ai_purpose: str,
    inputs: List[str],
    outputs: List[str],
    classification: str = "B",
) -> AIDLDocumentExporter:
    """
    Factory function to create an AIDL document.
    
    Usage:
        exporter = create_aidl_document(
            device_name="Cardiac Risk Predictor",
            device_description="ML-based cardiac risk assessment tool",
            version="2.0.0",
            ai_purpose="Predict 5-year cardiovascular risk",
            inputs=["Patient demographics", "Lab results", "ECG data"],
            outputs=["Risk score", "Risk category", "Contributing factors"],
            classification="B",
        )
        
        exporter.add_training_data(
            source="Hospital EHR",
            description="Anonymized patient records",
            volume="50,000 patients",
            collection_date="2024-01-15",
            preprocessing=["De-identification", "Outlier removal"],
            bias_assessment="Demographic distribution verified",
            consent_verified=True,
        )
        
        md = exporter.to_markdown()
    """
    generator = AIDLGenerator()
    generator.configure(
        device_name=device_name,
        device_description=device_description,
        software_version=version,
        ai_system_purpose=ai_purpose,
        ai_system_inputs=inputs,
        ai_system_outputs=outputs,
        classification=classification,
    )
    
    return AIDLDocumentExporter(generator.document)