"""
Cortex Document Management - Railway Safety Compliance

EN 50128 Class B compliant document management:
- Encrypted document storage
- Version control with integrity verification (SHA-256)
- Multi-format support (PDF, XML, JSON, images)
- Access logging and Merkle-verifiable audit trail
- Retention policies (10-year EN 50128 minimum)
- Railway asset traceability
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
    Document, DocumentVersion, RailwayAsset,
    RetentionPolicy, RetentionSchedule, AuditLog,
    DocumentStatus, DocumentType,
)
from cortex.security.encryption import EncryptionManager
from cortex.audit import AuditLogger, AuditAction, log_audit

logger = structlog.get_logger()


class FileType(str, Enum):
    """Supported file types for railway compliance"""
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"
    TIFF = "image/tiff"
    TEXT = "text/plain"
    XML = "application/xml"
    JSON = "application/json"
    YAML = "application/x-yaml"
    CSV = "text/csv"


@dataclass
class DocumentMetadata:
    """Document metadata"""
    id: UUID
    asset_id: Optional[UUID]
    document_type: str
    title: str
    description: Optional[str]
    file_type: str
    file_size: int
    checksum: str
    version: int
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID


class DocumentManager:
    """
    Railway compliance document management system.

    Features:
    - Encrypted file storage
    - Version control with SHA-256 integrity
    - Retention policy enforcement (EN 50128: 10-year minimum)
    - Railway asset traceability
    - Audit logging
    """

    DEFAULT_STORAGE_PATH = os.getenv("CORTEX_DOCUMENT_STORAGE", "/var/lib/cortex/documents")
    MAX_FILE_SIZE = int(os.getenv("CORTEX_MAX_DOCUMENT_SIZE", "100")) * 1024 * 1024  # 100 MB default
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".txt", ".xml", ".json", ".yaml", ".csv"}

    # Retention defaults in days (EN 50128: minimum 10 years = 3650 days)
    RETENTION_DEFAULTS = {
        DocumentType.SAFETY_PLAN: 3650,
        DocumentType.SOFTWARE_REQUIREMENTS: 3650,
        DocumentType.SOFTWARE_ARCHITECTURE: 3650,
        DocumentType.SOFTWARE_DESIGN: 3650,
        DocumentType.VERIFICATION_REPORT: 3650,
        DocumentType.VALIDATION_PLAN: 3650,
        DocumentType.VALIDATION_REPORT: 3650,
        DocumentType.SAFETY_CASE: 3650,
        DocumentType.HAZARD_ANALYSIS: 3650,
        DocumentType.RISK_ASSESSMENT: 3650,
        DocumentType.CONFIGURATION_MANIFEST: 3650,
        DocumentType.DRP_PACKAGE: 3650,
        DocumentType.SOUP_DOCUMENTATION: 3650,
        DocumentType.MAINTENANCE_LOG: 3650,
        DocumentType.INCIDENT_REPORT: 3650,
        DocumentType.OTHER: 3650,
    }

    def __init__(self, db_session: Optional[Session] = None, storage_path: Optional[str] = None):
        self.db = db_session
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        # Encryption manager loads key from env var — will be fixed in Phase 1A
        self.encryption = EncryptionManager(
            os.getenv("CORTEX_ENCRYPTION_KEY", "").encode() if os.getenv("CORTEX_ENCRYPTION_KEY") else os.getenv("ENCRYPTION_KEY", "").encode()
        )
        self.audit_logger = AuditLogger(db_session)

        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_session()

    def _generate_checksum(self, data: bytes) -> str:
        """Generate SHA-256 checksum for integrity verification"""
        return hashlib.sha256(data).hexdigest()

    def _get_document_path(self, document_id: UUID, version: int = 1) -> Path:
        """Get file path for document version"""
        return Path(self.storage_path) / str(document_id) / f"v{version}"

    def _validate_file_type(self, filename: str) -> bool:
        """Validate file type by extension"""
        ext = Path(filename).suffix.lower()
        return ext in self.ALLOWED_EXTENSIONS

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type for file"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    def _get_retention_days(self, document_type: DocumentType) -> int:
        """Get retention period for document type"""
        return self.RETENTION_DEFAULTS.get(document_type, 3650)

    def upload_document(
        self,
        file_data: BinaryIO,
        filename: str,
        document_type: DocumentType,
        title: str,
        description: Optional[str] = None,
        asset_id: Optional[UUID] = None,
        uploaded_by: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[UUID]:
        """
        Upload a new railway compliance document.

        Args:
            file_data: File binary data
            filename: Original filename
            document_type: Type of compliance document
            title: Document title
            description: Document description
            asset_id: Associated railway asset UUID
            uploaded_by: User uploading document
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
            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)

            if file_size > self.MAX_FILE_SIZE:
                logger.warning("file_too_large", size=file_size, max_size=self.MAX_FILE_SIZE)
                raise ValueError(f"File too large: {file_size} bytes (max: {self.MAX_FILE_SIZE})")

            # Generate document ID
            document_id = uuid4()

            # Read file content
            content = file_data.read()
            checksum = self._generate_checksum(content)

            # Encrypt content
            encrypted_data = self.encryption.encrypt_bytes(content)

            # Get database session
            db = self._get_db()

            # Create database record
            document = Document(
                id=str(document_id),
                asset_id=str(asset_id) if asset_id else None,
                document_type=document_type.value,
                title=title,
                description=description,
                original_filename=filename,
                file_type=self._get_mime_type(filename),
                file_size=file_size,
                checksum=checksum,
                uploaded_by=str(uploaded_by) if uploaded_by else None,
                tags=tags or [],
                status=DocumentStatus.ACTIVE.value,
                current_version=1,
                retention_until=datetime.utcnow() + timedelta(days=self._get_retention_days(document_type)),
            )

            db.add(document)

            # Create version record
            version_record = DocumentVersion(
                document_id=str(document_id),
                version_number=1,
                file_type=document.file_type,
                file_size=file_size,
                checksum=checksum,
                uploaded_by=str(uploaded_by) if uploaded_by else None,
                notes="Initial version",
            )
            db.add(version_record)

            # Commit DB transaction BEFORE writing file
            db.commit()
            db.refresh(document)

            # Store encrypted file (after DB commit to avoid inconsistent state)
            document_path = self._get_document_path(document_id, version=1)
            document_path.parent.mkdir(parents=True, exist_ok=True)

            with open(document_path, 'wb') as f:
                f.write(encrypted_data)

            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_CREATE,
                user_id=uploaded_by,
                asset_id=asset_id,
                resource_type="document",
                resource_id=document_id,
                details={
                    "document_type": document_type.value,
                    "filename": filename,
                    "file_size": file_size,
                    "checksum": checksum,
                }
            )

            logger.info(
                "document_uploaded",
                document_id=str(document_id),
                document_type=document_type.value,
                file_size=file_size,
            )

            return document_id

        except SQLAlchemyError as e:
            logger.error("document_upload_failed", error=str(e))
            return None

    def download_document(
        self,
        document_id: UUID,
        user: UUID,
        version: Optional[int] = None,
    ) -> Optional[tuple[bytes, str, str]]:
        """
        Download a document with integrity verification.

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
                Document.id == str(document_id)
            ).first()

            if not document:
                logger.warning("document_not_found", document_id=str(document_id))
                return None

            if document.status == DocumentStatus.DELETED.value:
                logger.warning("document_deleted", document_id=str(document_id))
                return None

            # Get version
            version_num = version or document.current_version

            version_record = db.query(DocumentVersion).filter(
                DocumentVersion.document_id == str(document_id),
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

            # Verify checksum — fail-safe: integrity mismatch must be logged
            computed_checksum = self._generate_checksum(content)
            if computed_checksum != version_record.checksum:
                logger.error(
                    "checksum_mismatch",
                    document_id=str(document_id),
                    expected=version_record.checksum,
                    computed=computed_checksum,
                )
                # Fail-safe: do not return corrupted content
                return None

            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_READ,
                user_id=user,
                asset_id=UUID(document.asset_id) if document.asset_id else None,
                resource_type="document",
                resource_id=document_id,
                details={
                    "version": version_num,
                    "filename": document.original_filename,
                    "checksum_verified": True,
                }
            )

            logger.info(
                "document_downloaded",
                document_id=str(document_id),
                user_id=str(user),
                version=version_num,
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
        notes: Optional[str] = None,
    ) -> Optional[int]:
        """
        Update document (creates new version).

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

            document = db.query(Document).filter(
                Document.id == str(document_id)
            ).first()

            if not document:
                return None

            if document.status == DocumentStatus.DELETED.value:
                raise ValueError("Cannot update deleted document")

            if not self._validate_file_type(filename):
                raise ValueError(f"File type not allowed: {filename}")

            # Read and encrypt new content
            content = file_data.read()
            checksum = self._generate_checksum(content)
            encrypted_data = self.encryption.encrypt_bytes(content)

            # Create new version
            new_version = document.current_version + 1

            version_record = DocumentVersion(
                document_id=str(document_id),
                version_number=new_version,
                file_type=self._get_mime_type(filename),
                file_size=len(content),
                checksum=checksum,
                uploaded_by=str(updated_by),
                notes=notes or f"Version {new_version}",
            )
            db.add(version_record)

            # Update document record
            document.current_version = new_version
            document.original_filename = filename
            document.file_type = self._get_mime_type(filename)
            document.file_size = len(content)
            document.checksum = checksum
            document.updated_at = datetime.utcnow()

            db.commit()

            # Store new version file
            document_path = self._get_document_path(document_id, version=new_version)
            document_path.parent.mkdir(parents=True, exist_ok=True)

            with open(document_path, 'wb') as f:
                f.write(encrypted_data)

            # Audit log
            log_audit(
                action=AuditAction.DOCUMENT_UPDATE,
                user_id=updated_by,
                asset_id=UUID(document.asset_id) if document.asset_id else None,
                resource_type="document",
                resource_id=document_id,
                details={
                    "version": new_version,
                    "filename": filename,
                    "checksum": checksum,
                }
            )

            logger.info(
                "document_updated",
                document_id=str(document_id),
                version=new_version,
            )

            return new_version

        except SQLAlchemyError as e:
            logger.error("document_update_failed", error=str(e))
            return None

    def delete_document(
        self,
        document_id: UUID,
        deleted_by: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Soft-delete a document (retention hold — EN 50128).

        Documents are not physically deleted; they are marked as deleted
        and placed under retention hold per the retention policy.

        Args:
            document_id: Document UUID
            deleted_by: User deleting document
            reason: Deletion reason

        Returns:
            True if successful
        """
        try:
            db = self._get_db()

            document = db.query(Document).filter(
                Document.id == str(document_id)
            ).first()

            if not document:
                return False

            if document.status == DocumentStatus.DELETED.value:
                return True  # Already deleted

            document.status = DocumentStatus.DELETED.value
            document.deleted_at = datetime.utcnow()
            document.deleted_by = str(deleted_by)
            document.deletion_reason = reason

            db.commit()

            log_audit(
                action=AuditAction.DOCUMENT_DELETE,
                user_id=deleted_by,
                asset_id=UUID(document.asset_id) if document.asset_id else None,
                resource_type="document",
                resource_id=document_id,
                details={"reason": reason}
            )

            logger.info("document_deleted", document_id=str(document_id))
            return True

        except SQLAlchemyError as e:
            logger.error("document_delete_failed", error=str(e))
            return False

    def list_documents(
        self,
        asset_id: Optional[UUID] = None,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Document], int]:
        """
        List documents with filtering and pagination.

        Returns:
            Tuple of (documents list, total count)
        """
        db = self._get_db()

        query = db.query(Document)

        if asset_id:
            query = query.filter(Document.asset_id == str(asset_id))
        if document_type:
            query = query.filter(Document.document_type == document_type.value)
        if status:
            query = query.filter(Document.status == status.value)
        else:
            query = query.filter(Document.status != DocumentStatus.DELETED.value)

        total = query.count()
        documents = query.order_by(Document.updated_at.desc()).offset(offset).limit(limit).all()

        return documents, total

    def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID"""
        db = self._get_db()
        return db.query(Document).filter(Document.id == str(document_id)).first()
