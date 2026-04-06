"""
Cortex Consent Management - HIPAA Compliant Consent Tracking

This module provides comprehensive consent management:
- Patient consent tracking
- Consent versioning and history
- Consent form templates
- Revocation workflow
- Expiration handling
- Authorization verification
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
import structlog

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from cortex.database import get_database_manager, get_db_session
from cortex.models import (
    Patient, ConsentRecord, ConsentType,
    AuditLog, User, UserRole
)
from cortex.audit import AuditLogger, AuditAction, log_audit
from cortex.security.encryption import EncryptionManager
import os

logger = structlog.get_logger()


class ConsentStatus(str, Enum):
    """Consent status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    SUSPENDED = "suspended"


class ConsentCategory(str, Enum):
    """Categories of consent"""
    TREATMENT = "treatment"
    RESEARCH = "research"
    DISCLOSURE = "disclosure"
    MARKETING = "marketing"
    ELECTRONIC_COMMUNICATION = "electronic_communication"
    DATA_SHARING = "data_sharing"
    AGENT_PROCESSING = "agent_processing"
    THIRD_PARTY = "third_party"


@dataclass
class ConsentTemplate:
    """Consent form template"""
    id: UUID
    name: str
    category: ConsentCategory
    version: str
    description: str
    content: str
    required_fields: List[str]
    expiration_days: Optional[int]
    created_at: datetime


class ConsentManager:
    """
    Manages patient consent lifecycle
    
    Features:
    - Create and track consent records
    - Versioning and history
    - Revocation workflow
    - Expiration handling
    - Authorization verification
    - Template management
    """
    
    # Default consent templates
    DEFAULT_TEMPLATES = {
        ConsentCategory.TREATMENT: {
            "name": "Treatment Consent",
            "description": "Consent for medical treatment and care",
            "content": """
TREATMENT CONSENT FORM

I, {patient_name}, hereby consent to:

1. Medical treatment and care by authorized healthcare providers
2. Access to my medical records by the care team
3. Sharing of my health information for treatment purposes

I understand that:
- I can revoke this consent at any time
- This consent will expire on {expiration_date}
- I have the right to a copy of this consent form

Patient Signature: _______________
Date: {consent_date}

Witness: _______________
Date: {witness_date}
            """,
            "required_fields": ["patient_name", "expiration_date", "consent_date"],
            "expiration_days": 365
        },
        ConsentCategory.RESEARCH: {
            "name": "Research Participation Consent",
            "description": "Consent for participation in medical research",
            "content": """
RESEARCH PARTICIPATION CONSENT FORM

Study: {study_name}

I, {patient_name}, consent to participate in this research study.

I understand that:
- My participation is voluntary
- I can withdraw at any time
- My data will be anonymized for publication
- Risks include: {risks}
- Benefits include: {benefits}

I consent to:
- Use of my health data for research
- Sharing anonymized data with researchers
- Long-term storage of my data

Patient Signature: _______________
Date: {consent_date}

Researcher: _______________
IRB Approval: {irb_number}
            """,
            "required_fields": ["patient_name", "study_name", "risks", "benefits", "irb_number"],
            "expiration_days": 730
        },
        ConsentCategory.DATA_SHARING: {
            "name": "Data Sharing Consent",
            "description": "Consent for sharing health data with third parties",
            "content": """
DATA SHARING CONSENT FORM

I, {patient_name}, authorize sharing of my health information with:

Recipient: {recipient_name}
Purpose: {purpose}
Data Types: {data_types}

I understand that:
- I can limit the data shared
- I can revoke this consent at any time
- The recipient must comply with HIPAA
- This consent expires on {expiration_date}

Patient Signature: _______________
Date: {consent_date}

Authorized Representative: _______________
            """,
            "required_fields": ["patient_name", "recipient_name", "purpose", "data_types", "expiration_date"],
            "expiration_days": 180
        },
        ConsentCategory.AGENT_PROCESSING: {
            "name": "AI Agent Processing Consent",
            "description": "Consent for processing health data by AI agents",
            "content": """
AI AGENT PROCESSING CONSENT

I, {patient_name}, consent to:

1. Processing of my health information by AI-powered agents
2. Use of AI for clinical decision support
3. Automated analysis of my medical records

I understand that:
- AI recommendations are advisory only
- Final decisions rest with my healthcare provider
- I can opt out of AI processing
- Data used for AI training will be anonymized

AI System: {ai_system_name}
Capabilities: {ai_capabilities}

Patient Signature: _______________
Date: {consent_date}

Healthcare Provider: _______________
            """,
            "required_fields": ["patient_name", "ai_system_name", "ai_capabilities"],
            "expiration_days": 365
        }
    }
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize consent manager"""
        self.db = db_session
        self.encryption = EncryptionManager(
            os.getenv("ENCRYPTION_KEY").encode() if os.getenv("ENCRYPTION_KEY") else None
        )
        self.audit_logger = AuditLogger(db_session)
    
    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_db_session()
    
    def create_consent(
        self,
        patient_id: UUID,
        consent_type: ConsentType,
        consented: bool,
        obtained_by: UUID,
        consent_form: Optional[str] = None,
        expiry_days: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Create a new consent record
        
        Args:
            patient_id: Patient UUID
            consent_type: Type of consent
            consented: Whether consent was given
            obtained_by: User who obtained consent
            consent_form: Consent form content (will be encrypted)
            expiry_days: Days until expiration (default from template)
            notes: Additional notes
            
        Returns:
            UUID of created consent record
        """
        try:
            db = self._get_db()
            
            # Determine expiration
            expiry_date = None
            if consented:
                # Get default expiration for consent type
                category_map = {
                    ConsentType.TREATMENT: ConsentCategory.TREATMENT,
                    ConsentType.RESEARCH: ConsentCategory.RESEARCH,
                    ConsentType.DISCLOSURE: ConsentCategory.DATA_SHARING,
                    ConsentType.AGENT_PROCESSING: ConsentCategory.AGENT_PROCESSING,
                }
                
                category = category_map.get(consent_type)
                if category and category in self.DEFAULT_TEMPLATES:
                    days = expiry_days or self.DEFAULT_TEMPLATES[category].get("expiration_days", 365)
                    expiry_date = datetime.utcnow() + timedelta(days=days)
            
            # Encrypt consent form
            encrypted_form = None
            if consent_form:
                encrypted = self.encryption.encrypt(consent_form)
                encrypted_form = encrypted["ciphertext"]
            
            # Create consent record
            consent = ConsentRecord(
                patient_id=patient_id,
                consent_type=consent_type,
                consented=consented,
                consent_date=datetime.utcnow(),
                expiry_date=expiry_date,
                consent_form_encrypted=encrypted_form,
                obtained_by=obtained_by,
                notes=notes
            )
            
            db.add(consent)
            db.commit()
            db.refresh(consent)
            
            # Audit log
            self.audit_logger.log(AuditEntry(
                action=AuditAction.CONSENT_GRANTED if consented else AuditAction.CONSENT_REVOKED,
                user_id=obtained_by,
                patient_id=patient_id,
                resource_type="consent",
                resource_id=consent.id,
                details={
                    "consent_type": consent_type.value,
                    "consented": consented,
                    "expiry_date": expiry_date.isoformat() if expiry_date else None
                }
            ))
            
            logger.info(
                "consent_created",
                consent_id=str(consent.id),
                patient_id=str(patient_id),
                consent_type=consent_type.value,
                consented=consented
            )
            
            return consent.id
            
        except SQLAlchemyError as e:
            logger.error("consent_creation_failed", error=str(e))
            return None
    
    def get_consent(
        self,
        consent_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get consent record by ID
        
        Args:
            consent_id: Consent UUID
            
        Returns:
            Consent record details
        """
        try:
            db = self._get_db()
            
            consent = db.query(ConsentRecord).filter(
                ConsentRecord.id == consent_id
            ).first()
            
            if not consent:
                return None
            
            # Decrypt consent form
            consent_form = None
            if consent.consent_form_encrypted:
                consent_form = self.encryption.decrypt({
                    "ciphertext": consent.consent_form_encrypted,
                    "nonce": ""
                })
            
            return {
                "id": str(consent.id),
                "patient_id": str(consent.patient_id),
                "consent_type": consent.consent_type.value,
                "consented": consent.consented,
                "consent_date": consent.consent_date.isoformat(),
                "expiry_date": consent.expiry_date.isoformat() if consent.expiry_date else None,
                "consent_form": consent_form,
                "obtained_by": str(consent.obtained_by),
                "notes": consent.notes,
                "created_at": consent.created_at.isoformat(),
                "updated_at": consent.updated_at.isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error("get_consent_failed", error=str(e))
            return None
    
    def get_patient_consents(
        self,
        patient_id: UUID,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all consents for a patient
        
        Args:
            patient_id: Patient UUID
            active_only: Only return active (non-expired, non-revoked) consents
            
        Returns:
            List of consent records
        """
        try:
            db = self._get_db()
            
            query = db.query(ConsentRecord).filter(
                ConsentRecord.patient_id == patient_id
            ).order_by(ConsentRecord.consent_date.desc())
            
            consents = query.all()
            
            # Filter for active if requested
            if active_only:
                consents = [
                    c for c in consents
                    if self._is_consent_active(c)
                ]
            
            return [
                {
                    "id": str(c.id),
                    "consent_type": c.consent_type.value,
                    "consented": c.consented,
                    "consent_date": c.consent_date.isoformat(),
                    "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
                    "status": self._get_consent_status(c).value
                }
                for c in consents
            ]
            
        except SQLAlchemyError as e:
            logger.error("get_patient_consents_failed", error=str(e))
            return []
    
    def revoke_consent(
        self,
        consent_id: UUID,
        revoked_by: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """
        Revoke a consent
        
        Args:
            consent_id: Consent UUID
            revoked_by: User revoking consent
            reason: Reason for revocation
            
        Returns:
            Success status
        """
        try:
            db = self._get_db()
            
            consent = db.query(ConsentRecord).filter(
                ConsentRecord.id == consent_id
            ).first()
            
            if not consent:
                logger.warning("consent_not_found", consent_id=str(consent_id))
                return False
            
            if not consent.consented:
                logger.warning("consent_already_revoked", consent_id=str(consent_id))
                return False
            
            # Update consent
            consent.consented = False
            consent.notes = f"Revoked: {reason}" if reason else "Revoked"
            consent.updated_at = datetime.utcnow()
            
            db.commit()
            
            # Audit log
            self.audit_logger.log(AuditEntry(
                action=AuditAction.CONSENT_REVOKED,
                user_id=revoked_by,
                patient_id=consent.patient_id,
                resource_type="consent",
                resource_id=consent_id,
                details={
                    "reason": reason
                }
            ))
            
            logger.info(
                "consent_revoked",
                consent_id=str(consent_id),
                revoked_by=str(revoked_by)
            )
            
            return True
            
        except SQLAlchemyError as e:
            logger.error("consent_revocation_failed", error=str(e))
            return False
    
    def check_consent(
        self,
        patient_id: UUID,
        consent_type: ConsentType
    ) -> bool:
        """
        Check if patient has valid consent for a specific type
        
        Args:
            patient_id: Patient UUID
            consent_type: Type of consent
            
        Returns:
            True if valid consent exists
        """
        try:
            db = self._get_db()
            
            consent = db.query(ConsentRecord).filter(
                ConsentRecord.patient_id == patient_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.consented == True
            ).first()
            
            if not consent:
                return False
            
            # Check if expired
            if consent.expiry_date and consent.expiry_date < datetime.utcnow():
                return False
            
            # Check if revoked
            if not consent.consented:
                return False
            
            return True
            
        except SQLAlchemyError as e:
            logger.error("check_consent_failed", error=str(e))
            return False
    
    def verify_authorization(
        self,
        patient_id: UUID,
        user: User,
        consent_types: List[ConsentType]
    ) -> Dict[str, Any]:
        """
        Verify user's authorization to access patient data
        
        Args:
            patient_id: Patient UUID
            user: User requesting access
            consent_types: Required consent types
            
        Returns:
            Authorization verification result
        """
        try:
            db = self._get_db()
            
            # Check role-based permissions
            from cortex.security.rbac import Permission, ROLE_PERMISSIONS
            
            user_permissions = ROLE_PERMISSIONS.get(user.role, [])
            
            # Admin has full access
            if Permission.PHI_FULL_ACCESS in user_permissions:
                return {
                    "authorized": True,
                    "reason": "Admin access",
                    "missing_consents": []
                }
            
            # Check each required consent
            missing_consents = []
            
            for consent_type in consent_types:
                if not self.check_consent(patient_id, consent_type):
                    missing_consents.append(consent_type.value)
            
            if missing_consents:
                return {
                    "authorized": False,
                    "reason": "Missing or expired consents",
                    "missing_consents": missing_consents
                }
            
            return {
                "authorized": True,
                "reason": "Valid consents present",
                "missing_consents": []
            }
            
        except Exception as e:
            logger.error("authorization_verification_failed", error=str(e))
            return {
                "authorized": False,
                "reason": f"Verification failed: {str(e)}",
                "missing_consents": []
            }
    
    def get_expiring_consents(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get consents expiring within specified days
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of expiring consents
        """
        try:
            db = self._get_db()
            
            expiry_threshold = datetime.utcnow() + timedelta(days=days)
            
            consents = db.query(ConsentRecord).filter(
                ConsentRecord.consented == True,
                ConsentRecord.expiry_date != None,
                ConsentRecord.expiry_date <= expiry_threshold,
                ConsentRecord.expiry_date > datetime.utcnow()
            ).order_by(ConsentRecord.expiry_date).all()
            
            return [
                {
                    "id": str(c.id),
                    "patient_id": str(c.patient_id),
                    "consent_type": c.consent_type.value,
                    "expiry_date": c.expiry_date.isoformat(),
                    "days_until_expiry": (c.expiry_date - datetime.utcnow()).days
                }
                for c in consents
            ]
            
        except SQLAlchemyError as e:
            logger.error("get_expiring_consents_failed", error=str(e))
            return []
    
    def generate_consent_form(
        self,
        category: ConsentCategory,
        patient_data: Dict[str, Any]
    ) -> str:
        """
        Generate a consent form from template
        
        Args:
            category: Consent category
            patient_data: Patient-specific data to fill in
            
        Returns:
            Generated consent form
        """
        template = self.DEFAULT_TEMPLATES.get(category)
        
        if not template:
            raise ValueError(f"No template for category: {category}")
        
        # Get current date
        patient_data["consent_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        patient_data["witness_date"] = patient_data.get("witness_date", patient_data["consent_date"])
        
        # Calculate expiration date
        if "expiration_date" not in patient_data:
            expiry_days = template.get("expiration_days", 365)
            patient_data["expiration_date"] = (
                datetime.utcnow() + timedelta(days=expiry_days)
            ).strftime("%Y-%m-%d")
        
        # Fill in template
        content = template["content"]
        for key, value in patient_data.items():
            content = content.replace(f"{{{key}}}", str(value))
        
        return content
    
    def _is_consent_active(self, consent: ConsentRecord) -> bool:
        """Check if consent is active"""
        if not consent.consented:
            return False
        
        if consent.expiry_date and consent.expiry_date < datetime.utcnow():
            return False
        
        return True
    
    def _get_consent_status(self, consent: ConsentRecord) -> ConsentStatus:
        """Get consent status"""
        if not consent.consented:
            return ConsentStatus.REVOKED
        
        if consent.expiry_date and consent.expiry_date < datetime.utcnow():
            return ConsentStatus.EXPIRED
        
        return ConsentStatus.ACTIVE


# Convenience functions

_consent_manager = None


def get_consent_manager(db_session: Optional[Session] = None) -> ConsentManager:
    """Get consent manager instance"""
    global _consent_manager
    if db_session:
        return ConsentManager(db_session)
    if not _consent_manager:
        _consent_manager = ConsentManager()
    return _consent_manager


def check_patient_consent(patient_id: UUID, consent_type: ConsentType) -> bool:
    """
    Convenience function to check patient consent
    
    Args:
        patient_id: Patient UUID
        consent_type: Type of consent
        
    Returns:
        True if valid consent exists
    """
    return get_consent_manager().check_consent(patient_id, consent_type)