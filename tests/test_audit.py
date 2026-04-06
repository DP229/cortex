"""
Tests for Audit Logging System

Tests:
- Audit event logging
- PHI access tracking
- User history retrieval
- Patient history retrieval
- Compliance reporting
- Breach management
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from cortex.audit import (
    AuditLogger, AuditAction, AuditEntry,
    BreachManager, log_audit, log_phi_access
)
from cortex.models import (
    AuditLog, SecurityIncident, BreachNotification,
    IncidentType, IncidentSeverity, IncidentStatus
)


class TestAuditLogger:
    """Test AuditLogger class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def audit_logger(self, mock_db):
        """Create audit logger with mock database"""
        return AuditLogger(db_session=mock_db)
    
    def test_log_basic_audit(self, audit_logger, mock_db):
        """Test logging basic audit event"""
        user_id = uuid4()
        mock_audit = Mock()
        mock_audit.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_audit.id))
        
        entry = AuditEntry(
            action=AuditAction.LOGIN,
            user_id=user_id,
            ip_address="192.168.1.1"
        )
        
        result = audit_logger.log(entry)
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_log_phi_access(self, audit_logger, mock_db):
        """Test logging PHI access event"""
        user_id = uuid4()
        patient_id = uuid4()
        
        mock_audit = Mock()
        mock_audit.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_audit.id))
        
        result = audit_logger.log_phi_access(
            user_id=user_id,
            patient_id=patient_id,
            action=AuditAction.PHI_ACCESS,
            resource_type="patient",
            resource_id=patient_id,
            ip_address="192.168.1.1"
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
    
    def test_log_authentication(self, audit_logger, mock_db):
        """Test logging authentication event"""
        user_id = uuid4()
        
        mock_audit = Mock()
        mock_audit.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_audit.id))
        
        result = audit_logger.log_authentication(
            user_id=user_id,
            action=AuditAction.LOGIN,
            ip_address="192.168.1.1",
            details={"method": "password"}
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
    
    def test_get_user_history(self, audit_logger, mock_db):
        """Test retrieving user history"""
        user_id = uuid4()
        
        mock_log1 = Mock()
        mock_log1.id = uuid4()
        mock_log1.action = "login"
        mock_log1.resource_type = None
        mock_log1.resource_id = None
        mock_log1.patient_id = None
        mock_log1.ip_address = "192.168.1.1"
        mock_log1.timestamp = datetime.utcnow()
        mock_log1.details = None
        
        mock_log2 = Mock()
        mock_log2.id = uuid4()
        mock_log2.action = "patient_read"
        mock_log2.resource_type = "patient"
        mock_log2.resource_id = uuid4()
        mock_log2.patient_id = uuid4()
        mock_log2.ip_address = "192.168.1.1"
        mock_log2.timestamp = datetime.utcnow()
        mock_log2.details = {"reason": "treatment"}
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_order = Mock()
        mock_limit = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.all.return_value = [mock_log1, mock_log2]
        
        history = audit_logger.get_user_history(user_id)
        
        assert len(history) == 2
        assert history[0]["action"] == "login"
        assert history[1]["action"] == "patient_read"
    
    def test_get_patient_history(self, audit_logger, mock_db):
        """Test retrieving patient history"""
        patient_id = uuid4()
        
        mock_log = Mock()
        mock_log.id = uuid4()
        mock_log.action = "phi_access"
        mock_log.user_id = uuid4()
        mock_log.resource_type = "patient"
        mock_log.resource_id = patient_id
        mock_log.ip_address = "192.168.1.1"
        mock_log.timestamp = datetime.utcnow()
        mock_log.details = None
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        
        history = audit_logger.get_patient_history(patient_id)
        
        assert len(history) == 1
        assert history[0]["action"] == "phi_access"
    
    def test_get_phi_access_summary(self, audit_logger, mock_db):
        """Test PHI access summary"""
        patient_id1 = uuid4()
        patient_id2 = uuid4()
        user_id = uuid4()
        
        mock_log1 = Mock()
        mock_log1.action = "patient_read"
        mock_log1.patient_id = patient_id1
        mock_log1.user_id = user_id
        
        mock_log2 = Mock()
        mock_log2.action = "phi_access"
        mock_log2.patient_id = patient_id2
        mock_log2.user_id = user_id
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_log1, mock_log2]
        
        summary = audit_logger.get_phi_access_summary()
        
        assert "total_phi_accesses" in summary
        assert "unique_patients_accessed" in summary
        assert "unique_users_accessing" in summary
    
    def test_generate_compliance_report(self, audit_logger, mock_db):
        """Test compliance report generation"""
        mock_log = Mock()
        mock_log.action = "login"
        mock_log.user_id = uuid4()
        mock_log.patient_id = None
        mock_log.timestamp = datetime.utcnow()
        mock_log.details = None
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        
        report = audit_logger.generate_compliance_report()
        
        assert "report_metadata" in report
        assert "authentication_summary" in report
        assert "phi_access_summary" in report
        assert "security_events" in report
        assert "compliance_checklist" in report
        assert report["compliance_checklist"]["audit_logging_enabled"] is True


class TestBreachManager:
    """Test BreachManager class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def breach_manager(self, mock_db):
        """Create breach manager with mock database"""
        return BreachManager(db_session=mock_db)
    
    def test_create_incident(self, breach_manager, mock_db):
        """Test creating security incident"""
        user_id = uuid4()
        
        mock_incident = Mock()
        mock_incident.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_incident.id))
        
        result = breach_manager.create_incident(
            title="Unauthorized PHI access",
            severity=IncidentSeverity.HIGH,
            incident_type=IncidentType.POTENTIAL_BREACH,
            patient_ids=[uuid4()],
            user_id=user_id
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
    
    def test_escalate_to_breach(self, breach_manager, mock_db):
        """Test escalating incident to breach"""
        incident_id = uuid4()
        patient_id = uuid4()
        user_id = uuid4()
        
        mock_incident = Mock()
        mock_incident.id = incident_id
        mock_incident.status = IncidentStatus.INVESTIGATING
        
        mock_breach = Mock()
        mock_breach.id = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_incident
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_breach.id))
        
        result = breach_manager.escalate_to_breach(
            incident_id=incident_id,
            affected_patients=[patient_id],
            description="Confirmed unauthorized access to patient records",
            assigned_to=user_id
        )
        
        assert result is not None
        mock_db.add.assert_called()
    
    def test_record_notification(self, breach_manager, mock_db):
        """Test recording patient notification"""
        breach_id = uuid4()
        patient_id = uuid4()
        
        mock_breach = Mock()
        mock_breach.id = breach_id
        mock_breach.notifications_sent = []
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_breach
        
        result = breach_manager.record_notification(
            breach_id=breach_id,
            patient_id=patient_id,
            notification_method="email",
            notification_date=datetime.utcnow()
        )
        
        assert result is True
        mock_db.commit.assert_called_once()
    
    def test_get_active_breaches(self, breach_manager, mock_db):
        """Test retrieving active breaches"""
        breach_id = uuid4()
        
        mock_breach = Mock()
        mock_breach.id = breach_id
        mock_breach.incident_id = uuid4()
        mock_breach.breach_date = datetime.utcnow()
        mock_breach.description = "Test breach"
        mock_breach.affected_patients = [uuid4()]
        mock_breach.notification_status = "pending"
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_breach]
        
        breaches = breach_manager.get_active_breaches()
        
        assert len(breaches) == 1
        assert breaches[0]["id"] == str(breach_id)


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('cortex.audit.get_audit_logger')
    def test_log_audit_convenience(self, mock_get_logger):
        """Test log_audit convenience function"""
        mock_logger = Mock()
        mock_logger.log.return_value = uuid4()
        mock_get_logger.return_value = mock_logger
        
        result = log_audit(
            action=AuditAction.LOGIN,
            user_id=uuid4(),
            ip_address="192.168.1.1"
        )
        
        assert result is not None
        mock_logger.log.assert_called_once()
    
    @patch('cortex.audit.get_audit_logger')
    def test_log_phi_access_convenience(self, mock_get_logger):
        """Test log_phi_access convenience function"""
        mock_logger = Mock()
        mock_logger.log_phi_access.return_value = uuid4()
        mock_get_logger.return_value = mock_logger
        
        user_id = uuid4()
        patient_id = uuid4()
        
        result = log_phi_access(
            user_id=user_id,
            patient_id=patient_id,
            action=AuditAction.PATIENT_READ,
            ip_address="192.168.1.1"
        )
        
        assert result is not None
        mock_logger.log_phi_access.assert_called_once()


class TestAuditActions:
    """Test all audit action types"""
    
    def test_authentication_actions(self):
        """Test authentication action enums"""
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.LOGOUT.value == "logout"
        assert AuditAction.LOGIN_FAILED.value == "login_failed"
        assert AuditAction.PASSWORD_CHANGE.value == "password_change"
        assert AuditAction.ACCOUNT_LOCKED.value == "account_locked"
    
    def test_phi_actions(self):
        """Test PHI action enums"""
        assert AuditAction.PATIENT_CREATE.value == "patient_create"
        assert AuditAction.PATIENT_READ.value == "patient_read"
        assert AuditAction.PATIENT_UPDATE.value == "patient_update"
        assert AuditAction.PATIENT_DELETE.value == "patient_delete"
        assert AuditAction.PHI_ACCESS.value == "phi_access"
        assert AuditAction.PHI_EXPORT.value == "phi_export"
    
    def test_document_actions(self):
        """Test document action enums"""
        assert AuditAction.DOCUMENT_CREATE.value == "document_create"
        assert AuditAction.DOCUMENT_READ.value == "document_read"
        assert AuditAction.DOCUMENT_UPDATE.value == "document_update"
        assert AuditAction.DOCUMENT_DELETE.value == "document_delete"
    
    def test_agent_actions(self):
        """Test agent action enums"""
        assert AuditAction.AGENT_QUERY.value == "agent_query"
        assert AuditAction.AGENT_RESPONSE.value == "agent_response"
        assert AuditAction.AGENT_ERROR.value == "agent_error"
    
    def test_security_actions(self):
        """Test security action enums"""
        assert AuditAction.SECURITY_INCIDENT.value == "security_incident"
        assert AuditAction.BREACH_DETECTED.value == "breach_detected"
        assert AuditAction.BREACH_REPORTED.value == "breach_reported"


class TestAuditEntry:
    """Test AuditEntry dataclass"""
    
    def test_basic_audit_entry(self):
        """Test creating basic audit entry"""
        entry = AuditEntry(
            action=AuditAction.LOGIN,
            user_id=uuid4()
        )
        
        assert entry.action == AuditAction.LOGIN
        assert entry.resource_type is None
        assert entry.resource_id is None
    
    def test_full_audit_entry(self):
        """Test creating full audit entry"""
        user_id = uuid4()
        patient_id = uuid4()
        resource_id = uuid4()
        
        entry = AuditEntry(
            action=AuditAction.PHI_ACCESS,
            user_id=user_id,
            resource_type="patient",
            resource_id=resource_id,
            patient_id=patient_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"reason": "treatment"}
        )
        
        assert entry.action == AuditAction.PHI_ACCESS
        assert entry.user_id == user_id
        assert entry.resource_type == "patient"
        assert entry.resource_id == resource_id
        assert entry.patient_id == patient_id
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Mozilla/5.0"
        assert entry.details["reason"] == "treatment"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])