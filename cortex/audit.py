"""
Cortex Audit Logging - HIPAA-Compliant Audit Trail

This module provides comprehensive audit logging for HIPAA compliance:
- All PHI access tracked
- User actions logged
- System events recorded
- 6-year retention
- Compliance reporting
- Breach notification support
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
import json

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from cortex.database import get_session
from cortex.models import (
    AuditLog, User, Patient, SecurityIncident, BreachNotification,
    IncidentType, IncidentSeverity, IncidentStatus
)

logger = structlog.get_logger()


class AuditAction(str, Enum):
    """Audit log action types"""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    
    # Patient/PHI Access
    PATIENT_CREATE = "patient_create"
    PATIENT_READ = "patient_read"
    PATIENT_UPDATE = "patient_update"
    PATIENT_DELETE = "patient_delete"
    PHI_ACCESS = "phi_access"
    PHI_EXPORT = "phi_export"
    
    # Document Operations
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_READ = "document_read"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_DELETE = "document_delete"
    
    # Agent Operations
    AGENT_QUERY = "agent_query"
    AGENT_RESPONSE = "agent_response"
    AGENT_ERROR = "agent_error"
    
    # Consent Management
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    CONSENT_VIEWED = "consent_viewed"
    
    # Administrative
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DEACTIVATE = "user_deactivate"
    ROLE_CHANGE = "role_change"
    
    # Security
    SECURITY_INCIDENT = "security_incident"
    BREACH_DETECTED = "breach_detected"
    BREACH_REPORTED = "breach_reported"


@dataclass
class AuditEntry:
    """Audit log entry data"""
    action: AuditAction
    user_id: Optional[UUID] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AuditLogger:
    """HIPAA-compliant audit logging service"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
    
    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_session()
    
    def log(self, entry: AuditEntry) -> Optional[UUID]:
        """
        Log an audit event
        
        Args:
            entry: Audit entry to log
            
        Returns:
            UUID of created audit log entry, or None on failure
        """
        try:
            db = self._get_db()
            
            audit_log = AuditLog(
                user_id=entry.user_id,
                action=entry.action.value,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                patient_id=entry.patient_id,
                ip_address=entry.ip_address,
                user_agent=entry.user_agent,
                details=entry.details,
                timestamp=datetime.utcnow()
            )
            
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            logger.info(
                "audit_logged",
                action=entry.action.value,
                user_id=str(entry.user_id) if entry.user_id else None,
                patient_id=str(entry.patient_id) if entry.patient_id else None,
                audit_id=str(audit_log.id)
            )
            
            return audit_log.id
            
        except SQLAlchemyError as e:
            logger.error("audit_log_failed", error=str(e), action=entry.action.value)
            return None
    
    def log_phi_access(
        self,
        user_id: UUID,
        patient_id: UUID,
        action: AuditAction,
        resource_type: str = "patient",
        resource_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Log PHI access event
        
        Args:
            user_id: User accessing PHI
            patient_id: Patient whose PHI was accessed
            action: Type of access
            resource_type: Type of resource accessed
            resource_id: Specific resource ID
            details: Additional details
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            UUID of audit log entry
        """
        entry = AuditEntry(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )
        
        return self.log(entry)
    
    def log_authentication(
        self,
        user_id: Optional[UUID],
        action: AuditAction,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[UUID]:
        """
        Log authentication event
        
        Args:
            user_id: User ID (if authenticated)
            action: Authentication action
            ip_address: Client IP
            user_agent: Client user agent
            details: Additional details
            
        Returns:
            UUID of audit log entry
        """
        entry = AuditEntry(
            action=action,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )
        
        return self.log(entry)
    
    def get_user_history(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit history for a user
        
        Args:
            user_id: User ID
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum number of results
            
        Returns:
            List of audit entries
        """
        db = self._get_db()
        
        query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
        
        results = query.all()
        
        return [
            {
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "patient_id": str(log.patient_id) if log.patient_id else None,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "timestamp": log.timestamp.isoformat(),
                "details": log.details
            }
            for log in results
        ]
    
    def get_patient_history(
        self,
        patient_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit history for a patient (PHI access)
        
        Args:
            patient_id: Patient ID
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum number of results
            
        Returns:
            List of audit entries
        """
        db = self._get_db()
        
        query = db.query(AuditLog).filter(AuditLog.patient_id == patient_id)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
        
        results = query.all()
        
        return [
            {
                "id": str(log.id),
                "action": log.action,
                "user_id": str(log.user_id) if log.user_id else None,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "timestamp": log.timestamp.isoformat(),
                "details": log.details
            }
            for log in results
        ]
    
    def get_phi_access_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get summary of PHI access for compliance reporting
        
        Args:
            start_date: Start of reporting period
            end_date: End of reporting period
            
        Returns:
            Summary statistics
        """
        db = self._get_db()
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get all PHI-related actions
        phi_actions = [
            AuditAction.PATIENT_READ.value,
            AuditAction.PATIENT_CREATE.value,
            AuditAction.PATIENT_UPDATE.value,
            AuditAction.PHI_ACCESS.value,
            AuditAction.PHI_EXPORT.value,
        ]
        
        query = db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date,
            AuditLog.action.in_(phi_actions)
        )
        
        results = query.all()
        
        # Calculate statistics
        total_accesses = len(results)
        unique_patients = len(set(log.patient_id for log in results if log.patient_id))
        unique_users = len(set(log.user_id for log in results if log.user_id))
        
        # Group by action type
        action_counts = {}
        for log in results:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
        
        # Group by user
        user_access_counts = {}
        for log in results:
            if log.user_id:
                user_access_counts[str(log.user_id)] = user_access_counts.get(str(log.user_id), 0) + 1
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_phi_accesses": total_accesses,
            "unique_patients_accessed": unique_patients,
            "unique_users_accessing": unique_users,
            "action_breakdown": action_counts,
            "top_users_by_access_count": sorted(
                user_access_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def generate_compliance_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate HIPAA compliance report
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Compliance report data
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        
        if not end_date:
            end_date = datetime.utcnow()
        
        db = self._get_db()
        
        # Get all audit logs in period
        all_logs = db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).all()
        
        # Authentication events
        auth_events = [log for log in all_logs if log.action in [
            AuditAction.LOGIN.value,
            AuditAction.LOGOUT.value,
            AuditAction.LOGIN_FAILED.value,
            AuditAction.ACCOUNT_LOCKED.value
        ]]
        
        # PHI access events
        phi_events = [log for log in all_logs if log.patient_id is not None]
        
        # Security events
        security_events = [log for log in all_logs if log.action in [
            AuditAction.SECURITY_INCIDENT.value,
            AuditAction.BREACH_DETECTED.value,
            AuditAction.BREACH_REPORTED.value
        ]]
        
        # Calculate failed logins
        failed_logins = len([log for log in auth_events if log.action == AuditAction.LOGIN_FAILED.value])
        
        # Calculate unique active users
        active_users = len(set(log.user_id for log in all_logs if log.user_id))
        
        report = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_events": len(all_logs)
            },
            "authentication_summary": {
                "total_login_attempts": len([log for log in auth_events if log.action == AuditAction.LOGIN.value]),
                "failed_login_attempts": failed_logins,
                "account_lockouts": len([log for log in auth_events if log.action == AuditAction.ACCOUNT_LOCKED.value]),
                "unique_active_users": active_users
            },
            "phi_access_summary": {
                "total_phi_access_events": len(phi_events),
                "unique_patients_accessed": len(set(log.patient_id for log in phi_events)),
                "breakdown_by_action": self._count_by_action(phi_events)
            },
            "security_events": {
                "total_incidents": len(security_events),
                "incidents": [
                    {
                        "action": log.action,
                        "timestamp": log.timestamp.isoformat(),
                        "details": log.details
                    }
                    for log in security_events
                ]
            },
            "compliance_checklist": {
                "audit_logging_enabled": True,
                "phi_tracking_enabled": True,
                "authentication_logging": True,
                "retention_policy_days": 2190,  # 6 years
                "data_encryption": "AES-256-GCM",
                "password_hashing": "Argon2id",
                "session_timeout_minutes": 15
            }
        }
        
        return report
    
    def _count_by_action(self, logs: List[AuditLog]) -> Dict[str, int]:
        """Count logs by action type"""
        counts = {}
        for log in logs:
            counts[log.action] = counts.get(log.action, 0) + 1
        return counts


class BreachManager:
    """Manage security incidents and breach notifications"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.audit_logger = AuditLogger(db_session)
    
    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_session()
    
    def create_incident(
        self,
        title: str,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        patient_ids: Optional[List[UUID]] = None,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        Create a security incident
        
        Args:
            title: Incident title
            severity: Incident severity
            incident_type: Type of incident
            patient_ids: List of affected patients
            details: Incident details
            user_id: User who reported the incident
            
        Returns:
            UUID of created incident
        """
        try:
            db = self._get_db()
            
            incident = SecurityIncident(
                title=title,
                incident_type=incident_type,
                severity=severity,
                status=IncidentStatus.INVESTIGATING,
                details=details,
                reported_by=user_id,
                report_date=datetime.utcnow()
            )
            
            if patient_ids:
                incident.affected_patients = patient_ids
            
            db.add(incident)
            db.commit()
            db.refresh(incident)
            
            # Log audit event
            self.audit_logger.log(AuditEntry(
                action=AuditAction.SECURITY_INCIDENT,
                user_id=user_id,
                details={
                    "incident_id": str(incident.id),
                    "title": title,
                    "severity": severity.value,
                    "type": incident_type.value
                }
            ))
            
            logger.warning(
                "security_incident_created",
                incident_id=str(incident.id),
                severity=severity.value,
                type=incident_type.value
            )
            
            return incident.id
            
        except SQLAlchemyError as e:
            logger.error("incident_creation_failed", error=str(e))
            return None
    
    def escalate_to_breach(
        self,
        incident_id: UUID,
        affected_patients: List[UUID],
        description: str,
        assigned_to: UUID
    ) -> Optional[UUID]:
        """
        Escalate incident to confirmed breach
        
        Args:
            incident_id: Original incident ID
            affected_patients: List of affected patient IDs
            description: Breach description
            assigned_to: User assigned to handle breach
            
        Returns:
            UUID of breach notification
        """
        try:
            db = self._get_db()
            
            # Update incident status
            incident = db.query(SecurityIncident).filter(
                SecurityIncident.id == incident_id
            ).first()
            
            if not incident:
                logger.error("incident_not_found", incident_id=str(incident_id))
                return None
            
            incident.status = IncidentStatus.CONFIRMED
            incident.affected_patients = affected_patients
            
            # Create breach notification
            breach = BreachNotification(
                incident_id=incident_id,
                breach_date=datetime.utcnow(),
                description=description,
                affected_patients=affected_patients,
                notification_status="pending"
            )
            
            db.add(breach)
            db.commit()
            db.refresh(breach)
            
            # Log audit event
            self.audit_logger.log(AuditEntry(
                action=AuditAction.BREACH_DETECTED,
                user_id=assigned_to,
                details={
                    "breach_id": str(breach.id),
                    "incident_id": str(incident_id),
                    "affected_count": len(affected_patients)
                }
            ))
            
            logger.critical(
                "breach_confirmed",
                breach_id=str(breach.id),
                affected_patients=len(affected_patients)
            )
            
            return breach.id
            
        except SQLAlchemyError as e:
            logger.error("breach_escalation_failed", error=str(e))
            return None
    
    def record_notification(
        self,
        breach_id: UUID,
        patient_id: UUID,
        notification_method: str,
        notification_date: datetime,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record patient notification for breach
        
        Args:
            breach_id: Breach notification ID
            patient_id: Patient who was notified
            notification_method: How they were notified
            notification_date: When they were notified
            notes: Additional notes
            
        Returns:
            Success status
        """
        try:
            db = self._get_db()
            
            breach = db.query(BreachNotification).filter(
                BreachNotification.id == breach_id
            ).first()
            
            if not breach:
                logger.error("breach_not_found", breach_id=str(breach_id))
                return False
            
            # Update notification status
            if not breach.notifications_sent:
                breach.notifications_sent = []
            
            breach.notifications_sent.append({
                "patient_id": str(patient_id),
                "method": notification_method,
                "date": notification_date.isoformat(),
                "notes": notes
            })
            
            db.commit()
            
            logger.info(
                "breach_notification_recorded",
                breach_id=str(breach_id),
                patient_id=str(patient_id)
            )
            
            return True
            
        except SQLAlchemyError as e:
            logger.error("notification_record_failed", error=str(e))
            return False
    
    def get_active_breaches(self) -> List[Dict[str, Any]]:
        """
        Get all active breach notifications
        
        Returns:
            List of active breaches
        """
        db = self._get_db()
        
        breaches = db.query(BreachNotification).filter(
            BreachNotification.notification_status != "completed"
        ).all()
        
        return [
            {
                "id": str(breach.id),
                "incident_id": str(breach.incident_id),
                "breach_date": breach.breach_date.isoformat(),
                "description": breach.description,
                "affected_patients": [str(pid) for pid in breach.affected_patients],
                "notification_status": breach.notification_status
            }
            for breach in breaches
        ]


# Convenience functions

_audit_logger = None

def get_audit_logger(db_session: Optional[Session] = None) -> AuditLogger:
    """Get audit logger instance"""
    global _audit_logger
    if db_session:
        return AuditLogger(db_session)
    if not _audit_logger:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_audit(
    action: AuditAction,
    user_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    patient_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Optional[UUID]:
    """
    Convenience function to log audit event
    
    Args:
        action: Audit action type
        user_id: User performing action
        resource_type: Type of resource
        resource_id: Resource ID
        patient_id: Patient ID if PHI accessed
        ip_address: Client IP
        user_agent: Client user agent
        details: Additional details
        
    Returns:
        UUID of audit log entry
    """
    entry = AuditEntry(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details
    )
    
    return get_audit_logger().log(entry)


def log_phi_access(
    user_id: UUID,
    patient_id: UUID,
    action: AuditAction,
    resource_type: str = "patient",
    resource_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[UUID]:
    """
    Convenience function to log PHI access
    
    Args:
        user_id: User accessing PHI
        patient_id: Patient whose PHI was accessed
        action: Type of access
        resource_type: Type of resource
        resource_id: Resource ID
        details: Additional details
        ip_address: Client IP
        user_agent: Client user agent
        
    Returns:
        UUID of audit log entry
    """
    return get_audit_logger().log_phi_access(
        user_id=user_id,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )