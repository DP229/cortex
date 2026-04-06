"""
Tests for Document Management

Tests:
- Document upload
- Document download
- Document update
- Document deletion
- Version control
- Consent verification
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from sqlalchemy.orm import Session

from cortex.documents import (
    DocumentManager, DocumentType, DocumentStatus,
    get_document_manager
)
from cortex.models import Document, DocumentVersion


class TestDocumentManager:
    """Test DocumentManager class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def doc_manager(self, mock_db, tmp_path):
        """Create document manager with mock database"""
        return DocumentManager(db_session=mock_db, storage_path=str(tmp_path))
    
    @pytest.fixture
    def sample_file(self):
        """Create sample file"""
        content = b"Sample document content for testing"
        return BytesIO(content)
    
    def test_upload_document(self, doc_manager, mock_db, sample_file):
        """Test uploading a document"""
        patient_id = uuid4()
        uploaded_by = uuid4()
        
        mock_document = Mock()
        mock_document.id = uuid4()
        mock_document.current_version = 1
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_document.id))
        
        result = doc_manager.upload_document(
            patient_id=patient_id,
            file_data=sample_file,
            filename="test.pdf",
            document_type=DocumentType.MEDICAL_RECORD,
            title="Test Document",
            description="Test description",
            uploaded_by=uploaded_by
        )
        
        assert result is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    def test_upload_invalid_file_type(self, doc_manager, sample_file):
        """Test uploading invalid file type"""
        patient_id = uuid4()
        uploaded_by = uuid4()
        
        with pytest.raises(ValueError, match="File type not allowed"):
            doc_manager.upload_document(
                patient_id=patient_id,
                file_data=sample_file,
                filename="test.exe",  # Invalid extension
                document_type=DocumentType.MEDICAL_RECORD,
                title="Test Document",
                uploaded_by=uploaded_by
            )
    
    def test_download_document(self, doc_manager, mock_db, tmp_path, sample_file):
        """Test downloading a document"""
        document_id = uuid4()
        user_id = uuid4()
        patient_id = uuid4()
        
        # Create mock document
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.patient_id = patient_id
        mock_document.original_filename = "test.pdf"
        mock_document.file_type = "application/pdf"
        mock_document.current_version = 1
        mock_document.status = DocumentStatus.ACTIVE.value
        
        # Create mock version
        mock_version = Mock()
        mock_version.version_number = 1
        mock_version.checksum = "test_checksum"
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_document,  # Document query
            mock_version    # Version query
        ]
        
        # Create encrypted file
        from cortex.security.encryption import EncryptionManager
        encryption = EncryptionManager()
        content = b"Test content"
        encrypted = encryption.encrypt_bytes(content)
        
        # Write encrypted file
        doc_path = tmp_path / str(document_id) / "v1"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_bytes(encrypted)
        
        # Mock checksum generation
        doc_manager._generate_checksum = Mock(return_value=mock_version.checksum)
        
        result = doc_manager.download_document(document_id, user_id)
        
        assert result is not None
        assert result[0] == content  # Decrypted content
        assert result[1] == "test.pdf"
        assert result[2] == "application/pdf"
    
    def test_download_nonexistent_document(self, doc_manager, mock_db):
        """Test downloading non-existent document"""
        document_id = uuid4()
        user_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = doc_manager.download_document(document_id, user_id)
        
        assert result is None
    
    def test_get_document_metadata(self, doc_manager, mock_db):
        """Test getting document metadata"""
        document_id = uuid4()
        patient_id = uuid4()
        uploaded_by = uuid4()
        
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.patient_id = patient_id
        mock_document.document_type = DocumentType.MEDICAL_RECORD.value
        mock_document.title = "Test Document"
        mock_document.description = "Test description"
        mock_document.original_filename = "test.pdf"
        mock_document.file_type = "application/pdf"
        mock_document.file_size = 1024
        mock_document.checksum = "abc123"
        mock_document.current_version = 1
        mock_document.status = DocumentStatus.ACTIVE.value
        mock_document.uploaded_by = uploaded_by
        mock_document.created_at = datetime.utcnow()
        mock_document.updated_at = datetime.utcnow()
        mock_document.retention_until = None
        mock_document.tags = []
        mock_document.consent_id = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_document
        
        result = doc_manager.get_document_metadata(document_id)
        
        assert result is not None
        assert result["document_type"] == "medical_record"
        assert result["title"] == "Test Document"
        assert result["file_size"] == 1024
    
    def test_update_document(self, doc_manager, mock_db, tmp_path, sample_file):
        """Test updating a document (versioning)"""
        document_id = uuid4()
        patient_id = uuid4()
        updated_by = uuid4()
        
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.patient_id = patient_id
        mock_document.current_version = 1
        mock_document.status = DocumentStatus.ACTIVE.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_document
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Create encrypted file
        from cortex.security.encryption import EncryptionManager
        encryption = EncryptionManager()
        content = b"New version content"
        encrypted = encryption.encrypt_bytes(content)
        
        # Write encrypted file
        doc_path = tmp_path / str(document_id) / "v2"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = doc_manager.update_document(
            document_id=document_id,
            file_data=sample_file,
            filename="updated.pdf",
            updated_by=updated_by,
            notes="Updated version"
        )
        
        assert result is not None
        assert mock_document.current_version == 2
    
    def test_delete_document(self, doc_manager, mock_db):
        """Test soft deleting a document"""
        document_id = uuid4()
        patient_id = uuid4()
        deleted_by = uuid4()
        
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.patient_id = patient_id
        mock_document.status = DocumentStatus.ACTIVE.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_document
        mock_db.commit = Mock()
        
        result = doc_manager.delete_document(
            document_id=document_id,
            deleted_by=deleted_by,
            reason="Patient requested deletion"
        )
        
        assert result is True
        assert mock_document.status == DocumentStatus.DELETED.value
        mock_db.commit.assert_called_once()
    
    def test_get_patient_documents(self, doc_manager, mock_db):
        """Test getting all documents for a patient"""
        patient_id = uuid4()
        
        mock_doc1 = Mock()
        mock_doc1.id = uuid4()
        mock_doc1.document_type = DocumentType.MEDICAL_RECORD.value
        mock_doc1.title = "Medical Record 1"
        mock_doc1.file_type = "application/pdf"
        mock_doc1.file_size = 1024
        mock_doc1.current_version = 1
        mock_doc1.status = DocumentStatus.ACTIVE.value
        mock_doc1.created_at = datetime.utcnow()
        mock_doc1.updated_at = None
        
        mock_doc2 = Mock()
        mock_doc2.id = uuid4()
        mock_doc2.document_type = DocumentType.LAB_RESULT.value
        mock_doc2.title = "Lab Result 1"
        mock_doc2.file_type = "application/pdf"
        mock_doc2.file_size = 512
        mock_doc2.current_version = 1
        mock_doc2.status = DocumentStatus.ACTIVE.value
        mock_doc2.created_at = datetime.utcnow()
        mock_doc2.updated_at = None
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_doc1, mock_doc2
        ]
        
        results = doc_manager.get_patient_documents(patient_id)
        
        assert len(results) == 2
        assert results[0]["document_type"] == "medical_record"
        assert results[1]["document_type"] == "lab_result"
    
    def test_get_document_versions(self, doc_manager, mock_db):
        """Test getting version history"""
        document_id = uuid4()
        
        mock_version1 = Mock()
        mock_version1.version_number = 2
        mock_version1.file_type = "application/pdf"
        mock_version1.file_size = 2048
        mock_version1.checksum = "hash2"
        mock_version1.uploaded_by = uuid4()
        mock_version1.created_at = datetime.utcnow()
        mock_version1.notes = "Version 2"
        
        mock_version2 = Mock()
        mock_version2.version_number = 1
        mock_version2.file_type = "application/pdf"
        mock_version2.file_size = 1024
        mock_version2.checksum = "hash1"
        mock_version2.uploaded_by = uuid4()
        mock_version2.created_at = datetime.utcnow()
        mock_version2.notes = "Initial version"
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_version1, mock_version2
        ]
        
        results = doc_manager.get_document_versions(document_id)
        
        assert len(results) == 2
        assert results[0]["version"] == 2
        assert results[1]["version"] == 1


class TestDocumentTypes:
    """Test document types"""
    
    def test_document_types(self):
        """Test document type enum"""
        assert DocumentType.MEDICAL_RECORD.value == "medical_record"
        assert DocumentType.LAB_RESULT.value == "lab_result"
        assert DocumentType.IMAGING.value == "imaging"
        assert DocumentType.CONSENT_FORM.value == "consent_form"
        assert DocumentType.CLINICAL_NOTE.value == "clinical_note"
    
    def test_document_document_statuses(self):
        """Test document status enum"""
        assert DocumentStatus.ACTIVE.value == "active"
        assert DocumentStatus.ARCHIVED.value == "archived"
        assert DocumentStatus.DELETED.value == "deleted"
        assert DocumentStatus.PENDING_REVIEW.value == "pending_review"
        assert DocumentStatus.RETENTION_HOLD.value == "retention_hold"


class TestRetentionPolicies:
    """Test document retention policies"""
    
    def test_retention_defaults(self):
        """Test default retention policies"""
        assert DocumentManager.RETENTION_DEFAULTS[DocumentType.MEDICAL_RECORD] == 365 * 7
        assert DocumentManager.RETENTION_DEFAULTS[DocumentType.LAB_RESULT] == 365 * 7
        assert DocumentManager.RETENTION_DEFAULTS[DocumentType.CONSENT_FORM] == 365 * 6
        assert DocumentManager.RETENTION_DEFAULTS[DocumentType.OTHER] == 365 * 5
    
    def test_file_validation(self):
        """Test file extension validation"""
        manager = DocumentManager()
        
        # Valid extensions
        assert manager._validate_file_type("test.pdf") is True
        assert manager._validate_file_type("test.jpg") is True
        assert manager._validate_file_type("test.png") is True
        assert manager._validate_file_type("test.dcm") is True
        
        # Invalid extensions
        assert manager._validate_file_type("test.exe") is False
        assert manager._validate_file_type("test.sh") is False
        assert manager._validate_file_type("test.bat") is False


class TestChecksum:
    """Test checksum generation"""
    
    def test_checksum_generation(self):
        """Test SHA-256 checksum"""
        manager = DocumentManager()
        
        content = b"Test content"
        checksum = manager._generate_checksum(content)
        
        # SHA-256 produces 64 character hex string
        assert len(checksum) == 64
        assert all(c in '0123456789abcdef' for c in checksum)
        
        # Same content should produce same checksum
        checksum2 = manager._generate_checksum(content)
        assert checksum == checksum2
        
        # Different content should produce different checksum
        different_content = b"Different content"
        checksum3 = manager._generate_checksum(different_content)
        assert checksum != checksum3


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('cortex.documents.get_document_manager')
    def test_get_document_manager(self, mock_get_manager):
        """Test get_document_manager function"""
        manager = DocumentManager()
        mock_get_manager.return_value = manager
        
        result = get_document_manager()
        
        assert result is not None
        mock_get_manager.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])