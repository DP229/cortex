"""
Tests for Audit Logging System - Railway Safety Compliance

Tests:
- Audit event logging (basic, authentication, asset access, requirement changes)
- History retrieval (user, asset, requirement)
- Compliance reporting
- Railway safety incident management (RailwayIncidentManager / BreachManager)
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import Mock, MagicMock

from sqlalchemy.orm import Session

from cortex.audit import (
    AuditLogger, AuditAction, AuditEntry,
    BreachManager, log_audit
)
from cortex.models import (
    AuditLog, RailwayIncident, IncidentType, IncidentSeverity, IncidentStatus
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
        mock_audit.id = str(uuid4())
        
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
        
    def test_log_authentication(self, audit_logger, mock_db):
        """Test logging authentication event"""
        user_id = uuid4()
        mock_audit = Mock()
        mock_audit.id = str(uuid4())
        
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
        mock_db.commit.assert_called_once()

    def test_log_asset_access(self, audit_logger, mock_db):
        """Test logging asset access event"""
        user_id = uuid4()
        asset_id = uuid4()
        mock_audit = Mock()
        mock_audit.id = str(uuid4())
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_audit.id))
        
        result = audit_logger.log_asset_access(
            user_id=user_id,
            asset_id=asset_id,
            action=AuditAction.ASSET_READ,
            ip_address="192.168.1.1"
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_requirement_change(self, audit_logger, mock_db):
        """Test logging requirement change event"""
        user_id = uuid4()
        requirement_id = uuid4()
        mock_audit = Mock()
        mock_audit.id = str(uuid4())
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_audit.id))
        
        result = audit_logger.log_requirement_change(
            user_id=user_id,
            requirement_id=requirement_id,
            action=AuditAction.REQUIREMENT_UPDATE,
            details={"changed_fields": ["description"]}
        )
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_get_user_history(self, audit_logger, mock_db):
        """Test retrieving user history"""
        user_id = uuid4()
        
        mock_log1 = Mock()
        mock_log1.id = uuid4()
        mock_log1.action = "login"
        mock_log1.resource_type = None
        mock_log1.resource_id = None
        mock_log1.ip_address = "192.168.1.1"
        mock_log1.timestamp = datetime.utcnow()
        mock_log1.details = None
        
        mock_log2 = Mock()
        mock_log2.id = uuid4()
        mock_log2.action = "requirement_read"
        mock_log2.resource_type = "requirement"
        mock_log2.resource_id = uuid4()
        mock_log2.ip_address = "192.168.1.1"
        mock_log2.timestamp = datetime.utcnow()
        mock_log2.details = {"requirement_id": "REQ-001"}
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log1, mock_log2]
        
        history = audit_logger.get_user_history(user_id)
        
        assert len(history) == 2
        assert history[0]["action"] == "login"
        assert history[1]["action"] == "requirement_read"
    
    def test_get_asset_history(self, audit_logger, mock_db):
        """Test retrieving asset history"""
        asset_id = uuid4()
        
        mock_log = Mock()
        mock_log.id = uuid4()
        mock_log.action = "asset_read"
        mock_log.user_id = uuid4()
        mock_log.resource_type = "asset"
        mock_log.resource_id = asset_id
        mock_log.ip_address = "192.168.1.1"
        mock_log.timestamp = datetime.utcnow()
        mock_log.details = None
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        
        history = audit_logger.get_asset_history(asset_id)
        
        assert len(history) == 1
        assert history[0]["action"] == "asset_read"
        
    def test_get_requirement_history(self, audit_logger, mock_db):
        """Test retrieving requirement history"""
        requirement_id = uuid4()
        
        mock_log = Mock()
        mock_log.id = uuid4()
        mock_log.action = "requirement_update"
        mock_log.user_id = uuid4()
        mock_log.resource_type = "requirement"
        mock_log.resource_id = requirement_id
        mock_log.ip_address = "192.168.1.1"
        mock_log.timestamp = datetime.utcnow()
        mock_log.details = {"changed_fields": ["description"]}
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        
        history = audit_logger.get_requirement_history(requirement_id)
        
        assert len(history) == 1
        assert history[0]["action"] == "requirement_update"

    def test_get_compliance_report(self, audit_logger, mock_db):
        """Test generating compliance report"""
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        report = audit_logger.get_compliance_report()
        
        assert report is not None
        assert "compliance_checklist" in report
        assert report["compliance_checklist"]["retention_policy_years"] == 10


class TestRailwayIncidentManager:
    """Test BreachManager (RailwayIncidentManager) class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
        
    @pytest.fixture
    def incident_manager(self, mock_db):
        """Create BreachManager instance with mock database"""
        return BreachManager(db_session=mock_db)
        
    def test_create_incident(self, incident_manager, mock_db):
        """Test creating a railway safety incident"""
        asset_id = uuid4()
        user_id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'id', str(uuid4())))
        
        # Stub the audit_logger.log inside incident_manager to avoid DB insert on logs
        incident_manager.audit_logger.log = Mock(return_value=uuid4())
        
        incident_id = incident_manager.create_incident(
            title="Brake failure simulation fail",
            severity=IncidentSeverity.HIGH.value,
            incident_type=IncidentType.TEST_FAIL.value,
            description="The test suite failed safety criteria under stress simulation.",
            asset_id=asset_id,
            user_id=user_id,
            is_safety_critical=True
        )
        
        assert incident_id is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
    def test_close_incident(self, incident_manager, mock_db):
        """Test closing a railway safety incident"""
        incident_id = uuid4()
        user_id = uuid4()
        
        mock_incident = Mock()
        mock_incident.id = str(incident_id)
        mock_incident.asset_id = str(uuid4())
        mock_incident.status = IncidentStatus.OPEN.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_incident
        mock_db.commit = Mock()
        
        incident_manager.audit_logger.log = Mock(return_value=uuid4())
        
        success = incident_manager.close_incident(
            incident_id=incident_id,
            user_id=user_id,
            root_cause="Software race condition",
            mitigation_steps="Added mutex protection around critical region"
        )
        
        assert success is True
        assert mock_incident.status == IncidentStatus.CLOSED.value
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])