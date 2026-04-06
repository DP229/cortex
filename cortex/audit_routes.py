"""
Cortex Audit API Endpoints

FastAPI endpoints for audit logging compliance:
- Query audit logs
- PHI access reports
- Compliance reports
- Breach management

All endpoints require authentication and are logged for HIPAA compliance.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel
import structlog

from cortex.security.auth import get_current_active_user
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, UserRole
from cortex.audit import (
    AuditLogger, AuditAction, BreachManager,
    IncidentType, IncidentSeverity
)

logger = structlog.get_logger()

router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])


# === Pydantic Models ===

class AuditLogResponse(BaseModel):
    """Audit log entry response"""
    id: str
    action: str
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    patient_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: str
    details: Optional[dict] = None


class PHIAccessSummaryResponse(BaseModel):
    """PHI access summary response"""
    period: dict
    total_phi_accesses: int
    unique_patients_accessed: int
    unique_users_accessing: int
    action_breakdown: dict
    top_users_by_access_count: List[tuple]


class ComplianceReportResponse(BaseModel):
    """Compliance report response"""
    report_metadata: dict
    authentication_summary: dict
    phi_access_summary: dict
    security_events: dict
    compliance_checklist: dict


class IncidentCreateRequest(BaseModel):
    """Security incident creation request"""
    title: str
    severity: str
    incident_type: str
    patient_ids: Optional[List[str]] = None
    details: Optional[dict] = None
    
    def get_severity(self) -> IncidentSeverity:
        return IncidentSeverity(self.severity)
    
    def get_type(self) -> IncidentType:
        return IncidentType(self.incident_type)


class BreachEscalateRequest(BaseModel):
    """Breach escalation request"""
    incident_id: str
    affected_patients: List[str]
    description: str


class NotificationRequest(BaseModel):
    """Patient notification request"""
    breach_id: str
    patient_id: str
    notification_method: str
    notes: Optional[str] = None


# === Helper Functions ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_permissions(user: User) -> List[Permission]:
    """Get permissions for a user based on their role"""
    return ROLE_PERMISSIONS.get(user.role, [])


# === Audit Query Endpoints ===

@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    patient_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000)
):
    """
    Query audit logs
    
    **Requires:** `audit_read` permission
    
    **Query Parameters:**
    - user_id: Filter by user ID
    - action: Filter by action type
    - patient_id: Filter by patient ID
    - start_date: Start of date range
    - end_date: End of date range
    - limit: Maximum results (default 100, max 1000)
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        audit_logger = AuditLogger()
        
        logs = []
        
        if user_id:
            user_uuid = UUID(user_id)
            logs = audit_logger.get_user_history(
                user_id=user_uuid,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        elif patient_id:
            patient_uuid = UUID(patient_id)
            logs = audit_logger.get_patient_history(
                patient_id=patient_uuid,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        else:
            # Get all logs (need to implement in AuditLogger)
            from cortex.database import get_database_manager
            db = get_database_manager()
            from cortex.models import AuditLog
            
            with db.get_session() as session:
                query = session.query(AuditLog)
                
                if start_date:
                    query = query.filter(AuditLog.timestamp >= start_date)
                
                if end_date:
                    query = query.filter(AuditLog.timestamp <= end_date)
                
                if action:
                    query = query.filter(AuditLog.action == action)
                
                query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
                
                results = query.all()
                
                logs = [
                    {
                        "id": str(log.id),
                        "action": log.action,
                        "user_id": str(log.user_id) if log.user_id else None,
                        "resource_type": log.resource_type,
                        "resource_id": str(log.resource_id) if log.resource_id else None,
                        "patient_id": str(log.patient_id) if log.patient_id else None,
                        "ip_address": str(log.ip_address) if log.ip_address else None,
                        "timestamp": log.timestamp.isoformat(),
                        "details": log.details
                    }
                    for log in results
                ]
        
        return [AuditLogResponse(**log) for log in logs]
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error("get_audit_logs_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/user/{user_id}/history", response_model=List[AuditLogResponse])
async def get_user_audit_history(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=500)
):
    """
    Get audit history for a specific user
    
    **Requires:** `audit_read` permission OR viewing own history
    """
    user_uuid = UUID(user_id)
    
    user_permissions = get_user_permissions(current_user)
    
    # Allow users to view their own history
    if current_user.id != user_uuid:
        if Permission.AUDIT_READ not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission 'audit_read' required"
            )
    
    try:
        audit_logger = AuditLogger()
        
        history = audit_logger.get_user_history(
            user_id=user_uuid,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return [AuditLogResponse(**log) for log in history]
        
    except Exception as e:
        logger.error("get_user_history_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user history"
        )


@router.get("/patient/{patient_id}/history", response_model=List[AuditLogResponse])
async def get_patient_audit_history(
    patient_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get PHI access history for a patient
    
    **Requires:** `phi_access` permission
    
    **HIPAA:** All access is logged for 6-year retention
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.PHI_ACCESS not in user_permissions:
        from cortex.audit import log_phi_access
        log_phi_access(
            user_id=current_user.id,
            patient_id=UUID(patient_id),
            action=AuditAction.PHI_ACCESS,
            resource_type="audit_log",
            ip_address=get_client_ip(request),
            details={"reason": "unauthorized_access_attempt"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'phi_access' required"
        )
    
    try:
        audit_logger = AuditLogger()
        patient_uuid = UUID(patient_id)
        
        history = audit_logger.get_patient_history(patient_id=patient_uuid)
        
        # Log PHI access
        from cortex.audit import log_phi_access
        log_phi_access(
            user_id=current_user.id,
            patient_id=patient_uuid,
            action=AuditAction.PHI_ACCESS,
            resource_type="audit_log",
            ip_address=get_client_ip(request),
            details={"reason": "patient_history_view"}
        )
        
        return [AuditLogResponse(**log) for log in history]
        
    except Exception as e:
        logger.error("get_patient_history_error", error=str(e), patient_id=patient_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient history"
        )


# === Compliance Reports ===

@router.get("/reports/phi-access", response_model=PHIAccessSummaryResponse)
async def get_phi_access_summary(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Get PHI access summary for compliance reporting
    
    **Requires:** `audit_read` permission
    
    **HIPAA:** Use for periodic compliance audits
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        audit_logger = AuditLogger()
        
        summary = audit_logger.get_phi_access_summary(
            start_date=start_date,
            end_date=end_date
        )
        
        return PHIAccessSummaryResponse(**summary)
        
    except Exception as e:
        logger.error("phi_access_summary_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PHI access summary"
        )


@router.get("/reports/compliance", response_model=ComplianceReportResponse)
async def get_compliance_report(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    Generate HIPAA compliance report
    
    **Requires:** `audit_read` permission
    
    **HIPAA:** Required for periodic compliance audits
    Includes:
    - Authentication summary
    - PHI access summary
    - Security events
    - Compliance checklist
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        audit_logger = AuditLogger()
        
        report = audit_logger.generate_compliance_report(
            start_date=start_date,
            end_date=end_date
        )
        
        return ComplianceReportResponse(**report)
        
    except Exception as e:
        logger.error("compliance_report_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report"
        )


# === Breach Management ===

@router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_security_incident(
    request: IncidentCreateRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a security incident report
    
    **Requires:** `incident_create` permission
    
    **HIPAA:** All potential breaches must be reported and investigated
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.INCIDENT_CREATE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'incident_create' required"
        )
    
    try:
        breach_manager = BreachManager()
        
        patient_uuids = None
        if request.patient_ids:
            patient_uuids = [UUID(pid) for pid in request.patient_ids]
        
        incident_id = breach_manager.create_incident(
            title=request.title,
            severity=request.get_severity(),
            incident_type=request.get_type(),
            patient_ids=patient_uuids,
            details=request.details,
            user_id=current_user.id
        )
        
        if not incident_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create incident"
            )
        
        return {
            "incident_id": str(incident_id),
            "message": "Security incident created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error("create_incident_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create security incident"
        )


@router.post("/breaches/escalate", status_code=status.HTTP_201_CREATED)
async def escalate_to_breach(
    request: BreachEscalateRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Escalate security incident to confirmed breach
    
    **Requires:** `incident_manage` permission
    
    **HIPAA:** Confirmed breaches require:
    - Notification to affected individuals within 60 days
    - Notification to HHS if >500 individuals affected
    - Documentation of breach and remediation
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.INCIDENT_MANAGE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'incident_manage' required"
        )
    
    try:
        breach_manager = BreachManager()
        
        incident_uuid = UUID(request.incident_id)
        patient_uuids = [UUID(pid) for pid in request.affected_patients]
        
        breach_id = breach_manager.escalate_to_breach(
            incident_id=incident_uuid,
            affected_patients=patient_uuids,
            description=request.description,
            assigned_to=current_user.id
        )
        
        if not breach_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to escalate to breach"
            )
        
        return {
            "breach_id": str(breach_id),
            "message": "Incident escalated to breach",
            "notification_deadline": (datetime.utcnow() + timedelta(days=60)).isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error("escalate_breach_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate to breach"
        )


@router.post("/breaches/notify")
async def record_breach_notification(
    request: NotificationRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Record patient notification for breach
    
    **Requires:** `incident_manage` permission
    
    **HIPAA:** All breach notifications must be documented
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.INCIDENT_MANAGE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'incident_manage' required"
        )
    
    try:
        breach_manager = BreachManager()
        
        breach_uuid = UUID(request.breach_id)
        patient_uuid = UUID(request.patient_id)
        
        success = breach_manager.record_notification(
            breach_id=breach_uuid,
            patient_id=patient_uuid,
            notification_method=request.notification_method,
            notification_date=datetime.utcnow(),
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record notification"
            )
        
        return {
            "message": "Notification recorded successfully",
            "breach_id": request.breach_id,
            "patient_id": request.patient_id
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error("record_notification_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record notification"
        )


@router.get("/breaches/active")
async def get_active_breaches(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all active breach notifications
    
    **Requires:** `audit_read` permission
    """
    user_permissions = get_user_permissions(current_user)
    
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        breach_manager = BreachManager()
        
        breaches = breach_manager.get_active_breaches()
        
        return {
            "breaches": breaches,
            "count": len(breaches)
        }
        
    except Exception as e:
        logger.error("get_active_breaches_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active breaches"
        )