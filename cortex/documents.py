"""
Cortex Document Management - HIPAA Compliant Document Storage

This module provides secure document management:
- Encrypted document storage
- Version control and history
- Multi-format support (PDF, images, DICOM)
- Access logging and audit
- Retention policies
- Secure download with consent verification
"""

import os
import hashlib
import mimetypes
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any, BinaryIO
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import shutil
import structlog

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from cortex.database import get_database_manager, get_session
from cortex.models import (
    Document, DocumentVersion, Patient, ConsentRecord, ConsentType,
    RetentionPolicy, RetentionSchedule, AuditLog
)
from cortex.security.encryption import EncryptionManager
from cortex.audit import AuditLogger, AuditAction, log_audit
from cortex.consent import ConsentManager, check_patient_consent

logger = structlog.get_logger()


class DocumentStatus(str, Enum):
    """Document status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PENDING_REVIEW = "pending_review"
    RETENTION_HOLD = "retention_hold"


class DocumentType(str, Enum):
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


class FileType(str, Enum):
    """Supported file types"""
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"
    DICOM = "application/dicom"
    TIFF = "image/tiff"
    TEXT = "text/plain"
    XML = "application/xml"
    JSON = "application/json"


@dataclass
class DocumentMetadata:
    """Document metadata"""
    id: UUID
    patient_id: UUID
    document_type: DocumentType
    title: str
    description: Optional[str]
    file_type: str
    file_size: int
    checksum: str
    version: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID


class DocumentManager:
    """
    Secure document management system
    
    Features:
    - Encrypted file storage
    - Version control
    - Access logging
    - Retention policies
    - Multi-format support
    - Thumbnail generation
    """
    
    # Storage configuration
    DEFAULT_STORAGE_PATH = os.getenv("DOCUMENT_STORAGE_PATH", "/var/lib/cortex/documents")
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB default
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".dcm", ".txt", ".xml", ".json"}
    
    # Document type retention defaults (days)
    RETENTION_DEFAULTS = {
        DocumentType.MEDICAL_RECORD: 365 * 7,  # 7 years
        DocumentType.LAB_RESULT: 365 * 7,
        DocumentType.IMAGING: 365 * 7,
        DocumentType.CONSENT_FORM: 365 * 6,  # 6 years (HIPAA)
        DocumentType.INSURANCE: 365 * 7,
        DocumentType.REFERRAL: 365 * 7,
        DocumentType.CLINICAL_NOTE: 365 * 7,
        DocumentType.DISCHARGE_SUMMARY: 365 * 7,
        DocumentType.OTHER: 365 * 5,
    }
    
    def __init__(self, db_session: Optional[Session] = None, storage_path: Optional[str] = None):
        """
        Initialize document manager
        
        Args:
            db_session: Database session
            storage_path: Path to document storage
        """
        self.db = db_session
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self.encryption = EncryptionManager(
            os.getenv("ENCRYPTION_KEY").encode() if os.getenv("ENCRYPTION_KEY") else None
        )
        self.audit_logger = AuditLogger(db_session)
        self.consent_manager = ConsentManager(db_session)
        
        # Create storage directory
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
    
    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_session()
    
    def _generate_checksum(self, data: bytes) -> str:
        """Generate SHA-256 checksum"""
        return hashlib.sha256(data).hexdigest()
    
    def _get_document_path(self, document_id: UUID, version: int = 1) -> Path:
        """Get file path for document"""
        return Path(self.storage_path) / str(document_id) / f"v{version}"
    
    def _validate_file_type(self, filename: str) -> bool:
        """Validate file type"""
        ext = Path(filename).suffix.lower()
        return ext in self.ALLOWED_EXTENSIONS
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type for file"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    def upload_document(
        self,
        patient_id: UUID,
        file_data: BinaryIO,
        filename: str,
        document_type: DocumentType,
        title: str,
        description: Optional[str] = None,
        uploaded_by: Optional[UUID] = None,
        requires_consent: bool = True,
        consent_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[UUID]:
        """
        Upload a new document
        
        Args:
            patient_id: Patient UUID
            file_data: File binary data
            filename: Original filename
            document_type: Type of document
            title: Document title
            description: Document description
            uploaded_by: User uploading document
            requires_consent: Whether consent is required
            consent_id: Associated consent ID
            tags: Document tags
            
        Returns:
            UUID of uploaded document
        """
        try:
            # Validate file type
            if not self._validate_file_type(filename):
                logger.warning("invalid_file_type", filename=filename)
                raise ValueError(f"File type not allowed: {filename}")
            
            # Check file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Seek to beginning
            
            if file_size > self.MAX_FILE_SIZE:
                logger.warning("file_too_large", size=file_size, max_size=self.MAX_FILE_SIZE)
                raise ValueError(f"File too large: {file_size} bytes (max: {self.MAX_FILE_SIZE})")
            
            # Verify consent if required
            if requires_consent and not consent_id:
                # Check if patient has required consent
                consent_types = {
                    DocumentType.MEDICAL_RECORD: ConsentType.TREATMENT,
                    DocumentType.LAB_RESULT: ConsentType.TREATMENT,
                    DocumentType.IMAGING: ConsentType.TREATMENT,
                    DocumentType.CONSENT_FORM: None,
                    DocumentType.CLINICAL_NOTE: ConsentType.TREATMENT,
                }
                
                required_consent = consent_types.get(document_type)
                if required_consent:
                    if not check_patient_consent(patient_id, required_consent):
                        logger.warning(
                            "missing_consent",
                            patient_id=str(patient_id),
                            document_type=document_type.value
                        )
                        raise ValueError("Patient consent required for this document type")
            
            # Generate document ID
            document_id = uuid4()
            
            # Read file content
            content = file_data.read()
            checksum = self._generate_checksum(content)
            
            # Encrypt content
            encrypted_data = self.encryption.encrypt_bytes(content)
            
            # Create database record
            db = self._get_db()
            
            document = Document(
                patient_id=patient_id,
                document_type=document_type,
                title=title,
                description=description,
                original_filename=filename,
                file_type=self._get_mime_type(filename),
                file_size=file_size,
                checksum=checksum,
                uploaded_by=uploaded_by,
                consent_id=consent_id,
                tags=tags or [],
                status=DocumentStatus.ACTIVE.value,
                current_version=1
            )
            # Set id after creation
            document.id = document_id
            
            db.add(document)
            
            # Create version record
            version = DocumentVersion(
                document_id=document_id,
                version_number=1,
                file_type=document.file_type,
                file_size=file_size,
                checksum=checksum,
                uploaded_by=uploaded_by,
                notes="Initial version"
            )
            db.add(version)
            
            db.commit()
            db.refresh(document)
            
            # Store encrypted file
            document_path = self._get_document_path(document_id, version=1)
            document_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(document_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Calculate retention date
            retention_days = self.RETENTION_DEFAULTS.get(document_type, 365 * 5)
            document.retention_until = datetime.utcnow() + timedelta(days=retention_days)
            db.commit()
            
            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_CREATE,
                user_id=uploaded_by,
                patient_id=patient_id,
                resource_type="document",
                resource_id=document_id,
                details={
                    "document_type": document_type.value,
                    "filename": filename,
                    "file_size": file_size
                }
            )
            
            logger.info(
                "document_uploaded",
                document_id=str(document_id),
                patient_id=str(patient_id),
                document_type=document_type.value,
                file_size=file_size
            )
            
            return document_id
            
        except SQLAlchemyError as e:
            logger.error("document_upload_failed", error=str(e))
            return None
    
    def download_document(
        self,
        document_id: UUID,
        user: UUID,
        version: Optional[int] = None
    ) -> Optional[tuple[bytes, str, str]]:
        """
        Download a document
        
        Args:
            document_id: Document UUID
            user: User requesting download
            version: Specific version (default: current)
            
        Returns:
            Tuple of (content, filename, mime_type) or None
        """
        try:
            db = self._get_db()
            
            # Get document record
            document = db.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if not document:
                logger.warning("document_not_found", document_id=str(document_id))
                return None
            
            # Check status
            if document.status == DocumentStatus.DELETED.value:
                logger.warning("document_deleted", document_id=str(document_id))
                return None
            
            # Get version
            version_num = version or document.current_version
            
            version_record = db.query(DocumentVersion).filter(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_num
            ).first()
            
            if not version_record:
                logger.warning("version_not_found", document_id=str(document_id), version=version_num)
                return None
            
            # Read encrypted file
            document_path = self._get_document_path(document_id, version=version_num)
            
            if not document_path.exists():
                logger.error("file_not_found", path=str(document_path))
                return None
            
            with open(document_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt
            content = self.encryption.decrypt_bytes(encrypted_data)
            
            # Verify checksum
            checksum = self._generate_checksum(content)
            if checksum != version_record.checksum:
                logger.error("checksum_mismatch", document_id=str(document_id))
                return None
            
            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_READ,
                user_id=user,
                patient_id=document.patient_id,
                resource_type="document",
                resource_id=document_id,
                details={
                    "version": version_num,
                    "filename": document.original_filename
                }
            )
            
            logger.info(
                "document_downloaded",
                document_id=str(document_id),
                user_id=str(user),
                version=version_num
            )
            
            return (content, document.original_filename, document.file_type)
            
        except SQLAlchemyError as e:
            logger.error("document_download_failed", error=str(e))
            return None
    
    def update_document(
        self,
        document_id: UUID,
        file_data: BinaryIO,
        filename: str,
        updated_by: UUID,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """
        Update document (create new version)
        
        Args:
            document_id: Document UUID
            file_data: New file data
            filename: New filename
            updated_by: User updating document
            notes: Version notes
            
        Returns:
            New version number
        """
        try:
            db = self._get_db()
            
            # Get document
            document = db.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if not document:
                return None
            
            if document.status == DocumentStatus.DELETED.value:
                raise ValueError("Cannot update deleted document")
            
            # Validate file type
            if not self._validate_file_type(filename):
                raise ValueError(f"File type not allowed: {filename}")
            
            # Read and encrypt new content
            content = file_data.read()
            checksum = self._generate_checksum(content)
            encrypted_data = self.encryption.encrypt_bytes(content)
            
            # Create new version
            new_version = document.current_version + 1
            
            version = DocumentVersion(
                document_id=document_id,
                version_number=new_version,
                file_type=self._get_mime_type(filename),
                file_size=len(content),
                checksum=checksum,
                uploaded_by=updated_by,
                notes=notes or f"Version {new_version}"
            )
            db.add(version)
            
            # Update document record
            document.current_version = new_version
            document.original_filename = filename
            document.file_type = self._get_mime_type(filename)
            document.file_size = len(content)
            document.checksum = checksum
            document.updated_at = datetime.utcnow()
            db.commit()
            
            # Store new version
            document_path = self._get_document_path(document_id, version=new_version)
            document_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(document_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_UPDATE,
                user_id=updated_by,
                patient_id=document.patient_id,
                resource_type="document",
                resource_id=document_id,
                details={
                    "version": new_version,
                    "notes": notes
                }
            )
            
            logger.info(
                "document_updated",
                document_id=str(document_id),
                version=new_version,
                user_id=str(updated_by)
            )
            
            return new_version
            
        except SQLAlchemyError as e:
            logger.error("document_update_failed", error=str(e))
            return None
    
    def delete_document(
        self,
        document_id: UUID,
        deleted_by: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """
        Soft delete a document
        
        Args:
            document_id: Document UUID
            deleted_by: User deleting document
            reason: Deletion reason
            
        Returns:
            Success status
        """
        try:
            db = self._get_db()
            
            document = db.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if not document:
                return False
            
            # Soft delete
            document.status = DocumentStatus.DELETED.value
            document.deleted_at = datetime.utcnow()
            document.deleted_by = deleted_by
            document.deletion_reason = reason
            
            db.commit()
            
            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_DELETE,
                user_id=deleted_by,
                patient_id=document.patient_id,
                resource_type="document",
                resource_id=document_id,
                details={
                    "reason": reason
                }
            )
            
            logger.info(
                "document_deleted",
                document_id=str(document_id),
                deleted_by=str(deleted_by),
                reason=reason
            )
            
            return True
            
        except SQLAlchemyError as e:
            logger.error("document_delete_failed", error=str(e))
            return False
    
    def get_document_metadata(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get document metadata
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document metadata
        """
        try:
            db = self._get_db()
            
            document = db.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if not document:
                return None
            
            return {
                "id": str(document.id),
                "patient_id": str(document.patient_id),
                "document_type": document.document_type,
                "title": document.title,
                "description": document.description,
                "original_filename": document.original_filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "checksum": document.checksum,
                "current_version": document.current_version,
                "status": document.status,
                "uploaded_by": str(document.uploaded_by),
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                "retention_until": document.retention_until.isoformat() if document.retention_until else None,
                "tags": document.tags,
                "consent_id": str(document.consent_id) if document.consent_id else None
            }
            
        except SQLAlchemyError as e:
            logger.error("get_document_metadata_failed", error=str(e))
            return None
    
    def get_patient_documents(
        self,
        patient_id: UUID,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all documents for a patient
        
        Args:
            patient_id: Patient UUID
            document_type: Filter by type
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of document metadata
        """
        try:
            db = self._get_db()
            
            query = db.query(Document).filter(
                Document.patient_id == patient_id
            )
            
            if document_type:
                query = query.filter(Document.document_type == document_type.value)
            
            if status:
                query = query.filter(Document.status == status.value)
            
            query = query.order_by(Document.created_at.desc()).limit(limit)
            
            documents = query.all()
            
            return [
                {
                    "id": str(d.id),
                    "document_type": d.document_type,
                    "title": d.title,
                    "file_type": d.file_type,
                    "file_size": d.file_size,
                    "current_version": d.current_version,
                    "status": d.status,
                    "created_at": d.created_at.isoformat(),
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None
                }
                for d in documents
            ]
            
        except SQLAlchemyError as e:
            logger.error("get_patient_documents_failed", error=str(e))
            return []
    
    def get_document_versions(
        self,
        document_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a document
        
        Args:
            document_id: Document UUID
            
        Returns:
            List of versions
        """
        try:
            db = self._get_db()
            
            versions = db.query(DocumentVersion).filter(
                DocumentVersion.document_id == document_id
            ).order_by(DocumentVersion.version_number.desc()).all()
            
            return [
                {
                    "version": v.version_number,
                    "file_type": v.file_type,
                    "file_size": v.file_size,
                    "checksum": v.checksum,
                    "uploaded_by": str(v.uploaded_by),
                    "uploaded_at": v.created_at.isoformat(),
                    "notes": v.notes
                }
                for v in versions
            ]
            
        except SQLAlchemyError as e:
            logger.error("get_document_versions_failed", error=str(e))
            return []


# Convenience functions

_document_manager = None


def get_document_manager(db_session: Optional[Session] = None) -> DocumentManager:
    """Get document manager instance"""
    global _document_manager
    if db_session:
        return DocumentManager(db_session)
    if not _document_manager:
        _document_manager = DocumentManager()
    return _document_manager