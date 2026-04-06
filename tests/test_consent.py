"""
Tests for Consent Management

Tests:
- Consent creation
- Consent retrieval
- Consent revocation
- Authorization verification
- Consent templates
- Expiration handling
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from cortex.consent import (
    ConsentManager, ConsentStatus, ConsentCategory,
    get_consent_manager
)
from cortex.models import ConsentRecord, ConsentType, Patient, User


class TestConsentManager:
    """Test ConsentManager class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def consent_manager(self, mock_db):
        """Create consent manager with mock database"""
        return ConsentManager(db_session=mock_db)
    
    def test_create_consent(self, consent_manager, mock_db):
        """Test creating a consent record"""
        patient_id = uuid4()
        obtained_by = uuid4()
        
        mock_consent = Mock()
        mock_consent.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_consent.id))
        
        result = consent_manager.create_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT,
            consented=True,
            obtained_by=obtained_by,
            notes="Test consent"
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_rejected_consent(self, consent_manager, mock_db):
        """Test creating a rejected consent"""
        patient_id = uuid4()
        obtained_by = uuid4()
        
        mock_consent = Mock()
        mock_consent.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_consent.id))
        
        result = consent_manager.create_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT,
            consented=False,
            obtained_by=obtained_by
        )
        
        assert result is not None
    
    def test_get_consent(self, consent_manager, mock_db):
        """Test retrieving a consent record"""
        consent_id = uuid4()
        patient_id = uuid4()
        obtained_by = uuid4()
        
        mock_consent = Mock()
        mock_consent.id = consent_id
        mock_consent.patient_id = patient_id
        mock_consent.consent_type = ConsentType.TREATMENT
        mock_consent.consented = True
        mock_consent.consent_date = datetime.utcnow()
        mock_consent.expiry_date = datetime.utcnow() + timedelta(days=365)
        mock_consent.consent_form_encrypted = None
        mock_consent.obtained_by = obtained_by
        mock_consent.notes = None
        mock_consent.created_at = datetime.utcnow()
        mock_consent.updated_at = datetime.utcnow()
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_consent
        
        result = consent_manager.get_consent(consent_id)
        
        assert result is not None
        assert result["consent_type"] == "treatment"
        assert result["consented"] is True
    
    def test_get_consent_not_found(self, consent_manager, mock_db):
        """Test retrieving non-existent consent"""
        consent_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = consent_manager.get_consent(consent_id)
        
        assert result is None
    
    def test_get_patient_consents(self, consent_manager, mock_db):
        """Test retrieving all consents for a patient"""
        patient_id = uuid4()
        
        mock_consent1 = Mock()
        mock_consent1.id = uuid4()
        mock_consent1.consent_type = ConsentType.TREATMENT
        mock_consent1.consented = True
        mock_consent1.consent_date = datetime.utcnow()
        mock_consent1.expiry_date = datetime.utcnow() + timedelta(days=365)
        
        mock_consent2 = Mock()
        mock_consent2.id = uuid4()
        mock_consent2.consent_type = ConsentType.RESEARCH
        mock_consent2.consented = True
        mock_consent2.consent_date = datetime.utcnow()
        mock_consent2.expiry_date = datetime.utcnow() + timedelta(days=180)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_consent1, mock_consent2
        ]
        
        results = consent_manager.get_patient_consents(patient_id, active_only=False)
        
        assert len(results) == 2
        assert results[0]["consent_type"] == "treatment"
        assert results[1]["consent_type"] == "research"
    
    def test_revoke_consent(self, consent_manager, mock_db):
        """Test revoking a consent"""
        consent_id = uuid4()
        revoked_by = uuid4()
        patient_id = uuid4()
        
        mock_consent = Mock()
        mock_consent.id = consent_id
        mock_consent.patient_id = patient_id
        mock_consent.consented = True
        mock_consent.notes = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_consent
        mock_db.commit = Mock()
        
        result = consent_manager.revoke_consent(
            consent_id=consent_id,
            revoked_by=revoked_by,
            reason="Patient requested revocation"
        )
        
        assert result is True
        assert mock_consent.consented is False
        mock_db.commit.assert_called_once()
    
    def test_revoke_consent_not_found(self, consent_manager, mock_db):
        """Test revoking non-existent consent"""
        consent_id = uuid4()
        revoked_by = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = consent_manager.revoke_consent(
            consent_id=consent_id,
            revoked_by=revoked_by
        )
        
        assert result is False
    
    def test_check_consent_valid(self, consent_manager, mock_db):
        """Test checking valid consent"""
        patient_id = uuid4()
        
        mock_consent = Mock()
        mock_consent.consented = True
        mock_consent.expiry_date = datetime.utcnow() + timedelta(days=30)
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_consent
        
        result = consent_manager.check_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT
        )
        
        assert result is True
    
    def test_check_consent_expired(self, consent_manager, mock_db):
        """Test checking expired consent"""
        patient_id = uuid4()
        
        mock_consent = Mock()
        mock_consent.consented = True
        mock_consent.expiry_date = datetime.utcnow() - timedelta(days=1)
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_consent
        
        result = consent_manager.check_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT
        )
        
        assert result is False
    
    def test_check_consent_not_found(self, consent_manager, mock_db):
        """Test checking non-existent consent"""
        patient_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = consent_manager.check_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT
        )
        
        assert result is False
    
    def test_get_expiring_consents(self, consent_manager, mock_db):
        """Test getting expiring consents"""
        mock_consent1 = Mock()
        mock_consent1.id = uuid4()
        mock_consent1.patient_id = uuid4()
        mock_consent1.consent_type = ConsentType.TREATMENT
        mock_consent1.expiry_date = datetime.utcnow() + timedelta(days=15)
        
        mock_consent2 = Mock()
        mock_consent2.id = uuid4()
        mock_consent2.patient_id = uuid4()
        mock_consent2.consent_type = ConsentType.RESEARCH
        mock_consent2.expiry_date = datetime.utcnow() + timedelta(days=25)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_consent1, mock_consent2
        ]
        
        results = consent_manager.get_expiring_consents(days=30)
        
        assert len(results) == 2
        assert results[0]["consent_type"] == "treatment"
    
    def test_generate_consent_form(self, consent_manager):
        """Test generating consent form from template"""
        patient_data = {
            "patient_name": "John Doe",
            "ai_system_name": "Cortex AI",
            "ai_capabilities": "Clinical decision support, diagnosis assistance"
        }
        
        form = consent_manager.generate_consent_form(
            category=ConsentCategory.AGENT_PROCESSING,
            patient_data=patient_data
        )
        
        assert "John Doe" in form
        assert "Cortex AI" in form
        assert "AI AGENT PROCESSING CONSENT" in form
    
    def test_generate_consent_form_invalid_category(self, consent_manager):
        """Test generating form with invalid category"""
        with pytest.raises(ValueError):
            consent_manager.generate_consent_form(
                category="invalid_category",
                patient_data={}
            )
    
    def test_is_consent_active(self, consent_manager):
        """Test checking if consent is active"""
        # Active consent
        active_consent = Mock()
        active_consent.consented = True
        active_consent.expiry_date = datetime.utcnow() + timedelta(days=30)
        assert consent_manager._is_consent_active(active_consent) is True
        
        # Revoked consent
        revoked_consent = Mock()
        revoked_consent.consented = False
        assert consent_manager._is_consent_active(revoked_consent) is False
        
        # Expired consent
        expired_consent = Mock()
        expired_consent.consented = True
        expired_consent.expiry_date = datetime.utcnow() - timedelta(days=1)
        assert consent_manager._is_consent_active(expired_consent) is False
    
    def test_get_consent_status(self, consent_manager):
        """Test getting consent status"""
        # Active consent
        active_consent = Mock()
        active_consent.consented = True
        active_consent.expiry_date = datetime.utcnow() + timedelta(days=30)
        assert consent_manager._get_consent_status(active_consent) == ConsentStatus.ACTIVE
        
        # Revoked consent
        revoked_consent = Mock()
        revoked_consent.consented = False
        assert consent_manager._get_consent_status(revoked_consent) == ConsentStatus.REVOKED
        
        # Expired consent
        expired_consent = Mock()
        expired_consent.consented = True
        expired_consent.expiry_date = datetime.utcnow() - timedelta(days=1)
        assert consent_manager._get_consent_status(expired_consent) == ConsentStatus.EXPIRED


class TestConsentCategories:
    """Test consent categories"""
    
    def test_consent_categories(self):
        """Test consent category enum"""
        assert ConsentCategory.TREATMENT.value == "treatment"
        assert ConsentCategory.RESEARCH.value == "research"
        assert ConsentCategory.DISCLOSURE.value == "disclosure"
        assert ConsentCategory.DATA_SHARING.value == "data_sharing"
        assert ConsentCategory.AGENT_PROCESSING.value == "agent_processing"
    
    def test_consent_statuses(self):
        """Test consent status enum"""
        assert ConsentStatus.ACTIVE.value == "active"
        assert ConsentStatus.EXPIRED.value == "expired"
        assert ConsentStatus.REVOKED.value == "revoked"
        assert ConsentStatus.PENDING.value == "pending"
        assert ConsentStatus.SUSPENDED.value == "suspended"


class TestConsentTemplates:
    """Test consent templates"""
    
    def test_default_templates_exist(self):
        """Test that default templates exist"""
        assert ConsentCategory.TREATMENT in ConsentManager.DEFAULT_TEMPLATES
        assert ConsentCategory.RESEARCH in ConsentManager.DEFAULT_TEMPLATES
        assert ConsentCategory.DATA_SHARING in ConsentManager.DEFAULT_TEMPLATES
        assert ConsentCategory.AGENT_PROCESSING in ConsentManager.DEFAULT_TEMPLATES
    
    def test_template_required_fields(self):
        """Test template required fields"""
        treatment_template = ConsentManager.DEFAULT_TEMPLATES[ConsentCategory.TREATMENT]
        assert "patient_name" in treatment_template["required_fields"]
        assert "expiration_date" in treatment_template["required_fields"]
        
        research_template = ConsentManager.DEFAULT_TEMPLATES[ConsentCategory.RESEARCH]
        assert "study_name" in research_template["required_fields"]
        assert "irb_number" in research_template["required_fields"]
    
    def test_template_expiration_days(self):
        """Test template expiration days"""
        treatment_template = ConsentManager.DEFAULT_TEMPLATES[ConsentCategory.TREATMENT]
        assert treatment_template["expiration_days"] == 365
        
        research_template = ConsentManager.DEFAULT_TEMPLATES[ConsentCategory.RESEARCH]
        assert research_template["expiration_days"] == 730
        
        data_sharing_template = ConsentManager.DEFAULT_TEMPLATES[ConsentCategory.DATA_SHARING]
        assert data_sharing_template["expiration_days"] == 180


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('cortex.consent.get_consent_manager')
    def test_get_consent_manager(self, mock_get_manager):
        """Test get_consent_manager function"""
        manager = ConsentManager()
        mock_get_manager.return_value = manager
        
        result = get_consent_manager()
        
        assert result is not None
        mock_get_manager.assert_called_once()
    
    @patch('cortex.consent.get_consent_manager')
    def test_check_patient_consent(self, mock_get_manager):
        """Test check_patient_consent function"""
        patient_id = uuid4()
        
        mock_manager = Mock()
        mock_manager.check_consent.return_value = True
        mock_get_manager.return_value = mock_manager
        
        result = get_consent_manager().check_consent(
            patient_id=patient_id,
            consent_type=ConsentType.TREATMENT
        )
        
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])