"""
Cortex Database - SQLAlchemy Models for PostgreSQL

This module defines all database models for the Healthcare Compliance Agent:
- Users and authentication
- Role-based access control
- Patients (PHI)
- Consent management
- Audit logging
- Care teams
- And more...

Uses PostgreSQL with SQLAlchemy ORM for robust data management.
"""

from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text, 
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


# === Enums ===

class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    CLINICIAN = "clinician"
    RESEARCHER = "researcher"
    AUDITOR = "auditor"


class ConsentType(str, enum.Enum):
    """Types of patient consent"""
    TREATMENT = "treatment"
    RESEARCH = "research"
    DISCLOSURE = "disclosure"
    AGENT_PROCESSING = "agent_processing"
    MARKETING = "marketing"


class IncidentType(str, enum.Enum):
    """Security incident types"""
    POTENTIAL_BREACH = "potential_breach"
    CONFIRMED_BREACH = "confirmed_breach"
    FALSE_POSITIVE = "false_positive"


class IncidentSeverity(str, enum.Enum):
    """Incident severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    """Incident status"""
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    CLOSED = "closed"


# === Base Mixins ===

class TimestampMixin:
    """Add created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UUIDMixin:
    """Add UUID primary key"""
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)


# === User Management ===

class User(UUIDMixin, TimestampMixin, Base):
    """User account"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name_encrypted = Column(Text, nullable=False)  # Encrypted for PHI
    role = Column(SQLEnum(UserRole), default=UserRole.CLINICIAN, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRoleMapping", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
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
    
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index('idx_sessions_user', 'user_id'),
        Index('idx_sessions_expires', 'expires_at'),
    )


# === Role-Based Access Control ===

class Role(UUIDMixin, TimestampMixin, Base):
    """User roles"""
    __tablename__ = "roles"
    
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False, default=list)  # JSON array of permissions
    
    # Relationships
    user_roles = relationship("UserRoleMapping", back_populates="role", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Role {self.name}>"


class UserRoleMapping(UUIDMixin, TimestampMixin, Base):
    """User-Role mapping (many-to-many)"""
    __tablename__ = "user_roles"
    
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
        Index('idx_user_roles_user', 'user_id'),
    )


# === Patient Management ===

class Patient(UUIDMixin, TimestampMixin, Base):
    """Patient record (contains PHI)"""
    __tablename__ = "patients"
    
    mrn = Column(String(50), unique=True, nullable=False, index=True)  # Medical Record Number
    first_name_encrypted = Column(Text, nullable=False)  # Encrypted
    last_name_encrypted = Column(Text, nullable=False)   # Encrypted
    dob_encrypted = Column(Text, nullable=False)          # Encrypted
    gender = Column(String(20), nullable=True)
    
    # Relationships
    consent_records = relationship("ConsentRecord", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    care_team = relationship("CareTeam", back_populates="patient", uselist=False, cascade="all, delete-orphan")
    notes = relationship("CareNote", back_populates="patient", cascade="all, delete-orphan")
    tasks = relationship("CareTask", back_populates="patient", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_patients_mrn', 'mrn'),
    )
    
    def __repr__(self):
        return f"<Patient MRN={self.mrn}>"


# === Consent Management ===

class ConsentRecord(UUIDMixin, TimestampMixin, Base):
    """Patient consent records"""
    __tablename__ = "consent_records"
    
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    consented = Column(Boolean, nullable=False)
    consent_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    consent_form_encrypted = Column(Text, nullable=True)  # Encrypted PDF
    obtained_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="consent_records")
    
    # Indexes
    __table_args__ = (
        Index('idx_consent_patient', 'patient_id'),
        Index('idx_consent_type', 'consent_type'),
        Index('idx_consent_date', 'consent_date'),
    )
    
    def __repr__(self):
        return f"<ConsentRecord patient={self.patient_id} type={self.consent_type}>"


# === Audit Logging ===

class AuditLog(UUIDMixin, Base):
    """Comprehensive audit log for HIPAA compliance"""
    __tablename__ = "audit_log"
    
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # System actions can be NULL
    action = Column(String(100), nullable=False)  # e.g., "patient_read", "phi_access"
    resource_type = Column(String(50), nullable=True)  # "patient", "document", "agent"
    resource_id = Column(PGUUID(as_uuid=True), nullable=True)
    patient_id = Column(PGUUID(as_uuid=True), nullable=True)  # If PHI accessed
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional context
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_user', 'user_id', 'timestamp'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_patient', 'patient_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id}>"


# === Care Team ===

class CareTeam(UUIDMixin, TimestampMixin, Base):
    """Care team for patient"""
    __tablename__ = "care_teams"
    
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(255), nullable=True)
    primary_provider = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    patient = relationship("Patient", back_populates="care_team")
    members = relationship("CareTeamMember", back_populates="team", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_care_team_patient', 'patient_id'),
    )


class CareTeamMember(UUIDMixin, TimestampMixin, Base):
    """Care team member"""
    __tablename__ = "care_team_members"
    
    team_id = Column(PGUUID(as_uuid=True), ForeignKey("care_teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), nullable=False)  # 'primary_physician', 'specialist', 'nurse', 'care_coordinator'
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    team = relationship("CareTeam", back_populates="members")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
        Index('idx_care_team_member_team', 'team_id'),
    )


# === Care Notes ===

class CareNote(UUIDMixin, TimestampMixin, Base):
    """Clinical notes"""
    __tablename__ = "care_notes"
    
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    note_type = Column(String(50), nullable=False)  # 'progress', 'consultation', 'discharge'
    content_encrypted = Column(Text, nullable=False)  # Encrypted
    is_shared = Column(Boolean, default=False, nullable=False)
    shared_with = Column(ARRAY(PGUUID(as_uuid=True)), nullable=True)  # Array of user IDs
    
    # Relationships
    patient = relationship("Patient", back_populates="notes")
    
    # Indexes
    __table_args__ = (
        Index('idx_care_notes_patient', 'patient_id'),
        Index('idx_care_notes_created', 'created_at'),
    )


# === Care Tasks ===

class CareTask(UUIDMixin, TimestampMixin, Base):
    """Care tasks and follow-ups"""
    __tablename__ = "care_tasks"
    
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task_type = Column(String(50), nullable=False)  # 'follow_up', 'test_order', 'referral'
    title = Column(String(255), nullable=False)
    description_encrypted = Column(Text, nullable=True)  # Encrypted
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(20), default="medium", nullable=False)  # 'low', 'medium', 'high', 'urgent'
    status = Column(String(20), default="pending", nullable=False)  # 'pending', 'in_progress', 'completed', 'cancelled'
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="tasks")
    
    # Indexes
    __table_args__ = (
        Index('idx_care_tasks_patient', 'patient_id'),
        Index('idx_care_tasks_status', 'status'),
        Index('idx_care_tasks_due', 'due_date'),
    )


# === Document Management ===

class DocumentStatus(str, enum.Enum):
    """Document status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PENDING_REVIEW = "pending_review"
    RETENTION_HOLD = "retention_hold"


class DocumentType(str, enum.Enum):
    """Document types"""
    MEDICAL_RECORD = "medical_record"
    LAB_RESULT = "lab_result"
    IMAGING = "imaging"
    CONSENT_FORM = "consent_form"
    INSURANCE = "insurance"
    REFERRAL = "referral"
    CLINICAL_NOTE = "clinical_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    OTHER = "other"


class Document(UUIDMixin, TimestampMixin, Base):
    """Patient documents"""
    __tablename__ = "documents"
    
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256
    current_version = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.ACTIVE, nullable=False)
    uploaded_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    consent_id = Column(PGUUID(as_uuid=True), ForeignKey("consent_records.id"), nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    retention_until = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deletion_reason = Column(Text, nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="documents")
    
    # Indexes
    __table_args__ = (
        Index('idx_document_patient', 'patient_id'),
        Index('idx_document_type', 'document_type'),
        Index('idx_document_status', 'status'),
        Index('idx_document_retention', 'retention_until'),
    )
    
    def __repr__(self):
        return f"<Document {self.title}: {self.document_type}>"


class DocumentVersion(UUIDMixin, TimestampMixin, Base):
    """Document version history"""
    __tablename__ = "document_versions"
    
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)
    uploaded_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    document = relationship("Document", backref="versions")
    
    # Indexes
    __table_args__ = (
        Index('idx_document_version', 'document_id', 'version_number'),
        UniqueConstraint('document_id', 'version_number', name='uq_document_version'),
    )
    
    def __repr__(self):
        return f"<DocumentVersion {self.document_id}: v{self.version_number}>"


# === Retention Policies ===

class RetentionPolicy(UUIDMixin, TimestampMixin, Base):
    """Data retention policies"""
    __tablename__ = "retention_policies"
    
    resource_type = Column(String(50), nullable=False, unique=True)
    retention_years = Column(Integer, default=6, nullable=False)
    retention_trigger = Column(String(50), default="creation", nullable=False)  # 'creation', 'last_access'
    delete_after_retention = Column(Boolean, default=True, nullable=False)
    archive_before_delete = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<RetentionPolicy {self.resource_type}: {self.retention_years} years>"


class RetentionSchedule(UUIDMixin, TimestampMixin, Base):
    """Retention schedule for resources"""
    __tablename__ = "retention_schedule"
    
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(PGUUID(as_uuid=True), nullable=False)
    creation_date = Column(DateTime, nullable=False)
    last_access_date = Column(DateTime, nullable=True)
    retention_until = Column(DateTime, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # 'active', 'archived', 'deleted'
    archived_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_retention_resource', 'resource_type', 'resource_id'),
        Index('idx_retention_until', 'retention_until'),
    )


# === Security Incidents ===

class SecurityIncident(UUIDMixin, TimestampMixin, Base):
    """Security incident and breach tracking"""
    __tablename__ = "security_incidents"
    
    incident_type = Column(SQLEnum(IncidentType), nullable=False)
    severity = Column(SQLEnum(IncidentSeverity), nullable=False)
    detected_at = Column(DateTime, nullable=False)
    detected_by = Column(String(50), nullable=True)  # 'system', 'user', 'audit'
    description = Column(Text, nullable=False)
    affected_patients = Column(ARRAY(PGUUID(as_uuid=True)), nullable=True)
    affected_records = Column(Integer, default=0, nullable=False)
    users_involved = Column(ARRAY(PGUUID(as_uuid=True)), nullable=True)
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.INVESTIGATING, nullable=False)
    investigation_notes = Column(Text, nullable=True)
    mitigation_steps = Column(Text, nullable=True)
    notification_sent = Column(Boolean, default=False, nullable=False)
    notification_date = Column(DateTime, nullable=True)
    hhs_notification_required = Column(Boolean, default=False, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    notifications = relationship("BreachNotification", back_populates="incident", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_incident_detected', 'detected_at'),
        Index('idx_incident_status', 'status'),
        Index('idx_incident_severity', 'severity'),
    )


class BreachNotification(UUIDMixin, TimestampMixin, Base):
    """Breach notification records"""
    __tablename__ = "breach_notifications"
    
    incident_id = Column(PGUUID(as_uuid=True), ForeignKey("security_incidents.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), nullable=False)  # 'patient', 'hhs', 'media'
    recipient_type = Column(String(50), nullable=False)  # 'patient', 'hhs', 'media_outlet'
    recipient_email = Column(String(255), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    sent_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    delivery_status = Column(String(20), nullable=True)  # 'sent', 'delivered', 'failed'
    content = Column(Text, nullable=True)
    
    # Relationships
    incident = relationship("SecurityIncident", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('idx_notification_incident', 'incident_id'),
    )


# === Medical Codes ===

class ICD10Code(Base):
    """ICD-10 diagnosis codes"""
    __tablename__ = "icd10_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    chapter = Column(String(100), nullable=True)
    is_billable = Column(Boolean, default=True, nullable=False)
    synonyms = Column(ARRAY(String), nullable=True)  # Array of synonyms
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_icd10_category', 'category'),
    )


class CPTCode(Base):
    """CPT procedure codes"""
    __tablename__ = "cpt_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    section = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    work_rvu = Column(Integer, nullable=True)  # Relative Value Unit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_cpt_category', 'category'),
    )


class CodeMapping(UUIDMixin, Base):
    """ICD-10 to CPT code mappings"""
    __tablename__ = "code_mappings"
    
    icd10_code = Column(String(10), ForeignKey("icd10_codes.code"), nullable=False)
    cpt_code = Column(String(10), ForeignKey("cpt_codes.code"), nullable=False)
    mapping_confidence = Column(Integer, nullable=False, default=80)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_mapping_icd10', 'icd10_code'),
        Index('idx_mapping_cpt', 'cpt_code'),
    )


# === Metrics (for monitoring) ===

class RequestMetric(Base):
    """Request metrics for monitoring"""
    __tablename__ = "request_metrics"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(String(100), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), nullable=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_timestamp', 'timestamp'),
        Index('idx_metrics_endpoint', 'endpoint'),
    )


# === Create all tables function ===

def create_all_tables(engine):
    """Create all tables in database"""
    Base.metadata.create_all(engine)
    print("✓ All tables created successfully")


# === Initialize default data ===

def initialize_default_data(session):
    """Initialize default roles and data"""
    from datetime import timedelta
    
    # Default roles
    roles_data = [
        {
            "name": "admin",
            "description": "Administrator with full access",
            "permissions": ["*"]  # All permissions
        },
        {
            "name": "clinician",
            "description": "Clinical staff with PHI access",
            "permissions": [
                "patient:read", "patient:write",
                "document:read", "document:write", "document:delete",
                "agent:run",
                "memory:read", "memory:write"
            ]
        },
        {
            "name": "researcher",
            "description": "Research staff with anonymized data access",
            "permissions": [
                "document:read",
                "agent:run",
                "data:anonymized",
                "memory:read"
            ]
        },
        {
            "name": "auditor",
            "description": "Compliance auditor with read-only access",
            "permissions": [
                "audit:read",
                "logs:read",
                "compliance:read"
            ]
        }
    ]
    
    for role_data in roles_data:
        role = Role(**role_data)
        session.add(role)
    
    # Default retention policies (HIPAA: 6 years)
    retention_policies = [
        RetentionPolicy(resource_type="patient", retention_years=6, retention_trigger="last_access"),
        RetentionPolicy(resource_type="document", retention_years=6, retention_trigger="creation"),
        RetentionPolicy(resource_type="audit_log", retention_years=6, retention_trigger="creation"),
        RetentionPolicy(resource_type="consent", retention_years=6, retention_trigger="last_access"),
    ]
    
    for policy in retention_policies:
        session.add(policy)
    
    session.commit()
    print("✓ Default data initialized successfully")


# === Export all models ===

__all__ = [
    "Base",
    "User",
    "Session",
    "Role",
    "UserRoleMapping",
    "Patient",
    "ConsentRecord",
    "AuditLog",
    "CareTeam",
    "CareTeamMember",
    "CareNote",
    "CareTask",
    "RetentionPolicy",
    "RetentionSchedule",
    "SecurityIncident",
    "BreachNotification",
    "ICD10Code",
    "CPTCode",
    "CodeMapping",
    "RequestMetric",
    "create_all_tables",
    "initialize_default_data",
    "UserRole",
    "ConsentType",
    "IncidentType",
    "IncidentSeverity",
    "IncidentStatus",
]