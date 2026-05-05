"""
Cortex Database - SQLAlchemy Models for Railway Safety Compliance

EN 50128 Class B compliant:
- Users and authentication
- Role-based access control (RBAC)
- Railway asset management
- Safety case and requirement traceability
- Audit logging (Merkle tree verifiable)
- SOUP (Software of Unknown Provenance) management

For IEC 62443 (P2): cybersecurity requirements model to be added.
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional, List, Dict, Any
import os
import logging
import enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text,
    ForeignKey, Index, UniqueConstraint, JSON,
)
from sqlalchemy.orm import relationship, declarative_base

SQLITE_UUID_MODE = os.getenv("CORTEX_SQLITE", "").lower() in ("1", "true", "yes")

Base = declarative_base()


# === Enums ===

class UserRole(str, enum.Enum):
    """Railway compliance user roles"""
    ADMIN = "admin"
    SAFETY_ENGINEER = "safety_engineer"
    REQUIREMENTS_ENGINEER = "requirements_engineer"
    TEST_ENGINEER = "test_engineer"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class IncidentType(str, enum.Enum):
    """Railway safety incident types (EN 50128 / ISO 9001)"""
    NEAR_MISS = "near_miss"
    SAFETY_FAILURE = "safety_failure"
    REQUIREMENT_DEVIATION = "requirement_deviation"
    TEST_FAIL = "test_fail"
    CYBERSECURITY = "cybersecurity"
    ENVIRONMENTAL = "environmental"


class IncidentSeverity(str, enum.Enum):
    """Incident severity (IEC 62443 / ISO 9001)"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    """Incident lifecycle status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    CLOSED = "closed"


class SafetyClass(str, enum.Enum):
    """IEC 62304 software safety classification"""
    CLASS_A = "class_a"  # Cannot contribute to hazardous situation
    CLASS_B = "class_b"  # Could contribute to hazardous situation, no serious injury
    CLASS_C = "class_c"  # Could contribute to hazardous situation with serious injury or death


class SILLevel(str, enum.Enum):
    """EN 50128 Safety Integrity Level (0-4)"""
    SIL0 = "sil0"
    SIL1 = "sil1"
    SIL2 = "sil2"
    SIL3 = "sil3"
    SIL4 = "sil4"


class DocumentType(str, enum.Enum):
    """Railway compliance document types"""
    SAFETY_PLAN = "safety_plan"
    SOFTWARE_REQUIREMENTS = "software_requirements"
    SOFTWARE_ARCHITECTURE = "software_architecture"
    SOFTWARE_DESIGN = "software_design"
    VERIFICATION_REPORT = "verification_report"
    VALIDATION_PLAN = "validation_plan"
    VALIDATION_REPORT = "validation_report"
    SAFETY_CASE = "safety_case"
    HAZARD_ANALYSIS = "hazard_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    CONFIGURATION_MANIFEST = "configuration_manifest"
    DRP_PACKAGE = "drp_package"  # Decision Reproducibility Package
    SOUP_DOCUMENTATION = "soup_documentation"
    MAINTENANCE_LOG = "maintenance_log"
    INCIDENT_REPORT = "incident_report"
    OTHER = "other"


class AssetType(str, enum.Enum):
    """Railway asset types"""
    ROLLING_STOCK = "rolling_stock"
    TRACK = "track"
    SIGNAL = "signal"
    SWITCH = "switch"
    BRIDGE = "bridge"
    TUNNEL = "tunnel"
    STATION = "station"
    OVERHEAD_LINE = "overhead_line"
    POWER_SUPPLY = "power_supply"
    CONTROL_CENTER = "control_center"
    COMMUNICATION = "communication"
    DEPOT = "depot"
    OTHER = "other"


class RequirementPriority(str, enum.Enum):
    """Requirement priority (EN 50128)"""
    SHALL = "shall"      # Mandatory — regulatory
    MUST = "must"        # Mandatory — safety critical
    SHOULD = "should"    # Recommended
    MAY = "may"          # Optional


class RequirementStatus(str, enum.Enum):
    """Requirement lifecycle status"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    VERIFIED = "verified"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


class VerificationStatus(str, enum.Enum):
    """Verification result status"""
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


class SoupStatus(str, enum.Enum):
    """SOUP lifecycle status"""
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_EVALUATION = "under_evaluation"


# === Base Mixins ===

class TimestampMixin:
    """Add created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UUIDMixin:
    """Add UUID primary key"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))


# === User Management ===

class User(UUIDMixin, TimestampMixin, Base):
    """User account for railway compliance system"""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name_encrypted = Column(Text, nullable=False)  # Encrypted PII
    role = Column(String(30), default=UserRole.VIEWER.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRoleMapping", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserRoleMapping.user_id")

    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('idx_users_active', 'is_active'),
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Session(UUIDMixin, TimestampMixin, Base):
    """User session for JWT refresh tokens"""
    __tablename__ = "sessions"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index('idx_sessions_user', 'user_id'),
        Index('idx_sessions_expires', 'expires_at'),
    )


# === Role-Based Access Control ===

class Role(UUIDMixin, TimestampMixin, Base):
    """User roles with permission sets (EN 50128 / IEC 62443)"""
    __tablename__ = "roles"

    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False, default=list)  # JSON array of permissions

    user_roles = relationship("UserRoleMapping", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role {self.name}>"


class UserRoleMapping(UUIDMixin, TimestampMixin, Base):
    """User-Role mapping (many-to-many)"""
    __tablename__ = "user_roles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
        Index('idx_user_roles_user', 'user_id'),
    )


# === Railway Asset Management ===

class RailwayAsset(UUIDMixin, TimestampMixin, Base):
    """Railway infrastructure asset for traceability (EN 50128)"""
    __tablename__ = "railway_assets"

    asset_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "SIG-001", "TRK-North-A"
    asset_type = Column(String(30), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)  # GPS coordinates or line/station designation
    safety_class = Column(String(10), default=SafetyClass.CLASS_B.value, nullable=False)  # IEC 62304
    sil_level = Column(String(10), default=SILLevel.SIL2.value, nullable=False)  # EN 50128
    parent_asset_id = Column(String(36), ForeignKey("railway_assets.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)  # Additional asset-specific data

    # Relationships
    documents = relationship("Document", back_populates="asset", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="asset", cascade="all, delete-orphan")
    incidents = relationship("RailwayIncident", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_asset_asset_id', 'asset_id'),
        Index('idx_asset_type', 'asset_type'),
        Index('idx_asset_safety_class', 'safety_class'),
        Index('idx_asset_parent', 'parent_asset_id'),
    )

    def __repr__(self):
        return f"<RailwayAsset {self.asset_id}: {self.name}>"


# === SOUP Management (EN 50128) ===

class SOUP(UUIDMixin, TimestampMixin, Base):
    """Software of Unknown Provenance — EN 50128 Section 4.2"""
    __tablename__ = "soups"

    name = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=True)
    version = Column(String(50), nullable=False)
    previous_version = Column(String(50), nullable=True)
    download_url = Column(Text, nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA-256 of downloaded artifact
    license_type = Column(String(100), nullable=True)
    status = Column(String(30), default=SoupStatus.CANDIDATE.value, nullable=False)
    safety_relevance = Column(String(10), default=SafetyClass.CLASS_B.value, nullable=False)
    justification = Column(Text, nullable=True)  # Why this SOUP is acceptable
    integration_notes = Column(Text, nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    review_due_date = Column(DateTime, nullable=True)
    risk_assessment = Column(Text, nullable=True)  # Known failure modes, mitigations
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    requirements = relationship("Requirement", back_populates="soup", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_soup_name_version', 'name', 'version'),
        UniqueConstraint('name', 'version', name='uq_soup_name_version'),
        Index('idx_soup_status', 'status'),
        Index('idx_soup_safety_class', 'safety_relevance'),
    )

    def __repr__(self):
        return f"<SOUP {self.name} v{self.version} ({self.status})>"


# === Requirements Management (EN 50128) ===

class Requirement(UUIDMixin, TimestampMixin, Base):
    """Software requirement with EN 50128 traceability"""
    __tablename__ = "requirements"

    requirement_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "REQ-SIG-001"
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(10), default=RequirementPriority.SHALL.value, nullable=False)
    status = Column(String(20), default=RequirementStatus.DRAFT.value, nullable=False)
    safety_class = Column(String(10), default=SafetyClass.CLASS_B.value, nullable=False)  # IEC 62304
    sil_level = Column(String(10), default=SILLevel.SIL2.value, nullable=False)  # EN 50128
    category = Column(String(50), nullable=True)  # "functional", "safety", "security", "performance"
    asset_id = Column(String(36), ForeignKey("railway_assets.id"), nullable=True)
    soup_id = Column(String(36), ForeignKey("soups.id"), nullable=True)  # If derived from SOUP
    parent_requirement_id = Column(String(36), ForeignKey("requirements.id"), nullable=True)
    traceability_tags = Column(JSON, nullable=True)  # Links to upstream standards: ISO 9001, CENELEC, etc.
    risk_level = Column(String(20), nullable=True)  # "high", "medium", "low" — ISO 14971
    verification_method = Column(String(50), nullable=True)  # "inspection", "analysis", "test"
    verification_status = Column(String(20), default=VerificationStatus.PENDING.value, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    asset = relationship("RailwayAsset", back_populates="requirements")
    soup = relationship("SOUP", back_populates="requirements")
    test_records = relationship("TestRecord", back_populates="requirement", cascade="all, delete-orphan")
    citations = relationship("RequirementCitation", back_populates="source_req", foreign_keys="RequirementCitation.source_requirement_id", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_req_id', 'requirement_id'),
        Index('idx_req_status', 'status'),
        Index('idx_req_safety_class', 'safety_class'),
        Index('idx_req_asset', 'asset_id'),
        Index('idx_req_soup', 'soup_id'),
    )

    def __repr__(self):
        return f"<Requirement {self.requirement_id}: {self.title}>"


class RequirementCitation(UUIDMixin, Base):
    """Bidirectional traceability link between requirements (EN 50128)"""
    __tablename__ = "requirement_citations"

    source_requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    target_requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    citation_type = Column(String(30), nullable=False)  # "verifies", "satisfies", "conflicts_with", "refines"
    citation_text = Column(Text, nullable=True)  # How the citation relates
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    source_req = relationship("Requirement", foreign_keys=[source_requirement_id], back_populates="citations")
    target_req = relationship("Requirement", foreign_keys=[target_requirement_id])

    __table_args__ = (
        UniqueConstraint('source_requirement_id', 'target_requirement_id', name='uq_requirement_citation'),
        Index('idx_citation_source', 'source_requirement_id'),
        Index('idx_citation_target', 'target_requirement_id'),
    )


# === Verification Records (EN 50128) ===

class TestRecord(UUIDMixin, TimestampMixin, Base):
    """Verification test record (EN 50128 Table A.3)"""
    __tablename__ = "test_records"

    test_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "TEST-SIG-001-01"
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    test_type = Column(String(50), nullable=False)  # "unit_test", "integration_test", "system_test", "acceptance_test"
    test_description = Column(Text, nullable=False)
    test_results = Column(Text, nullable=True)  # Actual output
    expected_results = Column(Text, nullable=True)
    status = Column(String(20), default=VerificationStatus.PENDING.value, nullable=False)
    executed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    test_environment = Column(Text, nullable=True)  # Platform, configuration
    test_artifacts = Column(JSON, nullable=True)  # Paths to logs, screenshots, etc.
    passed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    blocked_count = Column(Integer, default=0, nullable=False)
    is_closed = Column(Boolean, default=False, nullable=False)

    requirement = relationship("Requirement", back_populates="test_records")

    __table_args__ = (
        Index('idx_test_req', 'requirement_id'),
        Index('idx_test_status', 'status'),
        Index('idx_test_executed', 'executed_at'),
    )

    def __repr__(self):
        return f"<TestRecord {self.test_id} ({self.status})>"


# === Document Management ===

class DocumentStatus(str, enum.Enum):
    """Document lifecycle status"""
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ARCHIVED = "archived"
    DELETED = "deleted"
    RETENTION_HOLD = "retention_hold"


class Document(UUIDMixin, TimestampMixin, Base):
    """Railway compliance document"""
    __tablename__ = "documents"

    asset_id = Column(String(36), ForeignKey("railway_assets.id", ondelete="SET NULL"), nullable=True)
    document_type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256
    current_version = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default=DocumentStatus.ACTIVE.value, nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    tags = Column(JSON, nullable=True)
    retention_until = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    deletion_reason = Column(Text, nullable=True)

    asset = relationship("RailwayAsset", back_populates="documents")

    __table_args__ = (
        Index('idx_document_asset', 'asset_id'),
        Index('idx_document_type', 'document_type'),
        Index('idx_document_status', 'status'),
        Index('idx_document_retention', 'retention_until'),
    )

    def __repr__(self):
        return f"<Document {self.title}: {self.document_type}>"


class DocumentVersion(UUIDMixin, TimestampMixin, Base):
    """Document version history with integrity verification"""
    __tablename__ = "document_versions"

    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 for integrity
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)

    document = relationship("Document", backref="versions")

    __table_args__ = (
        Index('idx_doc_version_doc', 'document_id', 'version_number'),
        UniqueConstraint('document_id', 'version_number', name='uq_document_version'),
    )

    def __repr__(self):
        return f"<DocumentVersion {self.document_id}: v{self.version_number}>"


# === Railway Safety Incidents ===

class RailwayIncident(UUIDMixin, TimestampMixin, Base):
    """Railway safety incident tracking (EN 50128 / ISO 9001)"""
    __tablename__ = "railway_incidents"

    incident_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "INC-2026-001"
    asset_id = Column(String(36), ForeignKey("railway_assets.id", ondelete="SET NULL"), nullable=True)
    incident_type = Column(String(30), nullable=False)
    severity = Column(String(20), nullable=False)
    status = Column(String(20), default=IncidentStatus.OPEN.value, nullable=False)
    detected_at = Column(DateTime, nullable=False)
    detected_by = Column(String(50), nullable=True)  # 'system', 'user', 'audit'
    description = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=True)
    affected_assets = Column(JSON, nullable=True)  # Array of asset IDs
    affected_systems = Column(JSON, nullable=True)  # Array of system names
    is_safety_critical = Column(Boolean, default=False, nullable=False)
    is_reportable = Column(Boolean, default=False, nullable=False)  # Regulatory reporting required
    reported_to = Column(String(100), nullable=True)  # Regulatory body
    reported_at = Column(DateTime, nullable=True)
    investigation_notes = Column(Text, nullable=True)
    mitigation_steps = Column(Text, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    asset = relationship("RailwayAsset", back_populates="incidents")

    __table_args__ = (
        Index('idx_incident_asset', 'asset_id'),
        Index('idx_incident_type', 'incident_type'),
        Index('idx_incident_severity', 'severity'),
        Index('idx_incident_status', 'status'),
        Index('idx_incident_detected', 'detected_at'),
    )

    def __repr__(self):
        return f"<RailwayIncident {self.incident_id} ({self.severity})>"


# === Retention Policies (EN 50128: 10-year retention) ===

class RetentionPolicy(UUIDMixin, TimestampMixin, Base):
    """Data retention policies for railway compliance (EN 50128 requires 10 years)"""
    __tablename__ = "retention_policies"

    resource_type = Column(String(50), nullable=False, unique=True)
    retention_years = Column(Integer, default=10, nullable=False)  # EN 50128: 10 years minimum
    retention_trigger = Column(String(50), default="creation", nullable=False)  # 'creation', 'last_access'
    delete_after_retention = Column(Boolean, default=False, nullable=False)  # Safety-critical: archive, don't delete
    archive_before_delete = Column(Boolean, default=True, nullable=False)
    is_regulatory_required = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<RetentionPolicy {self.resource_type}: {self.retention_years} years>"


class RetentionSchedule(UUIDMixin, TimestampMixin, Base):
    """Retention schedule for individual resources"""
    __tablename__ = "retention_schedule"

    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=False)
    creation_date = Column(DateTime, nullable=False)
    last_access_date = Column(DateTime, nullable=True)
    retention_until = Column(DateTime, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # 'active', 'archived', 'deleted'
    archived_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_retention_resource', 'resource_type', 'resource_id'),
        Index('idx_retention_until', 'retention_until'),
    )


# === Audit Logging (Merkle tree verifiable — EN 50128) ===

class AuditLog(UUIDMixin, Base):
    """Comprehensive audit log with Merkle tree integrity (EN 50128 / IEC 62443)"""
    __tablename__ = "audit_log"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # NULL for system actions
    action = Column(String(100), nullable=False)  # e.g., "requirement_created", "document_uploaded"
    resource_type = Column(String(50), nullable=True)  # "requirement", "document", "soup", "asset"
    resource_id = Column(String(36), nullable=True)
    asset_id = Column(String(36), ForeignKey("railway_assets.id"), nullable=True)  # For asset traceability
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional structured context
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes for common audit queries
    __table_args__ = (
        Index('idx_audit_user', 'user_id', 'timestamp'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_asset', 'asset_id'),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"


# === Create all tables function ===

def create_all_tables(engine):
    """Create all tables in database"""
    Base.metadata.create_all(engine)
    print("✓ All tables created successfully")


# === Initialize default data ===

def initialize_default_data(session):
    """Initialize default roles and data for railway compliance (idempotent)"""
    from datetime import timedelta

    existing_roles = session.query(Role).count()
    if existing_roles > 0:
        return

    roles_data = [
        {
            "name": UserRole.ADMIN.value,
            "description": "Administrator with full system access",
            "permissions": ["*"],
        },
        {
            "name": UserRole.SAFETY_ENGINEER.value,
            "description": "Safety engineer — manages safety requirements, hazard analysis, and IEC 62304 Class B/C compliance",
            "permissions": [
                "asset:read", "asset:write",
                "requirement:read", "requirement:write", "requirement:approve",
                "soup:read", "soup:write", "soup:approve",
                "document:read", "document:write",
                "test_record:read", "test_record:write",
                "incident:read", "incident:write",
                "audit:read",
                "drp:generate",
            ],
        },
        {
            "name": UserRole.REQUIREMENTS_ENGINEER.value,
            "description": "Requirements engineer — authors and traces EN 50128 requirements",
            "permissions": [
                "asset:read",
                "requirement:read", "requirement:write",
                "soup:read",
                "document:read",
                "audit:read",
            ],
        },
        {
            "name": UserRole.TEST_ENGINEER.value,
            "description": "Test engineer — executes verification (EN 50128 Table A.3)",
            "permissions": [
                "asset:read",
                "requirement:read",
                "test_record:read", "test_record:write",
                "document:read", "document:write",
                "audit:read",
            ],
        },
        {
            "name": UserRole.AUDITOR.value,
            "description": "Compliance auditor — read-only access for EN 50128 / IEC 62443 audits",
            "permissions": [
                "asset:read",
                "requirement:read",
                "soup:read",
                "document:read",
                "test_record:read",
                "incident:read",
                "audit:read",
                "compliance:read",
            ],
        },
        {
            "name": UserRole.VIEWER.value,
            "description": "Read-only viewer for all compliance documents",
            "permissions": [
                "asset:read",
                "requirement:read",
                "soup:read",
                "document:read",
                "test_record:read",
                "incident:read",
            ],
        },
    ]

    for role_data in roles_data:
        role = Role(**role_data)
        session.add(role)

    # Default retention policies (EN 50128 requires minimum 10 years for safety-critical software)
    retention_policies = [
        RetentionPolicy(resource_type="requirement", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="test_record", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="document", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="audit_log", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="soup", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="incident", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
        RetentionPolicy(resource_type="drp_package", retention_years=10, retention_trigger="creation",
                        delete_after_retention=False, is_regulatory_required=True),
    ]

    for policy in retention_policies:
        session.add(policy)

    # Create default admin user
    from cortex.security.encryption import hash_password
    admin = User(
        id=str(uuid4()),
        email="admin@cortex.dev",
        password_hash=hash_password("AdminPass12!"),
        full_name_encrypted="Railway Admin",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    session.add(admin)

    session.commit()
    print("✓ Default data initialized successfully")


# === Export all models ===

__all__ = [
    "Base",
    # Enums
    "UserRole", "IncidentType", "IncidentSeverity", "IncidentStatus",
    "SafetyClass", "SILLevel", "DocumentType", "AssetType",
    "RequirementPriority", "RequirementStatus", "VerificationStatus", "SoupStatus",
    # Models
    "User", "Session", "Role", "UserRoleMapping",
    "RailwayAsset", "SOUP",
    "Requirement", "RequirementCitation", "TestRecord",
    "Document", "DocumentVersion",
    "RailwayIncident",
    "RetentionPolicy", "RetentionSchedule",
    "AuditLog",
    # Functions
    "create_all_tables", "initialize_default_data",
]
