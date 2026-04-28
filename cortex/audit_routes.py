"""
Cortex Audit API Endpoints - Railway Safety Compliance

EN 50128 Class B compliant audit endpoints:
- Query audit logs (user, asset, requirement)
- Generate EN 50128 compliance reports
- Railway incident management
- DRP (Decision Reproducibility Package) generation

All endpoints require authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, UserRole
from cortex.audit import (
    AuditLogger, AuditAction, RailwayIncidentManager,
    IncidentType, IncidentSeverity,
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
    asset_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: str
    details: Optional[dict] = None


class IncidentCreateRequest(BaseModel):
    """Railway safety incident creation request"""
    title: str
    severity: str
    incident_type: str
    asset_id: Optional[str] = None
    description: str
    is_safety_critical: bool = False
    is_reportable: bool = False
    details: Optional[dict] = None


class IncidentCloseRequest(BaseModel):
    """Close a railway safety incident"""
    root_cause: Optional[str] = None
    mitigation_steps: Optional[str] = None


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
    current_user: User = Depends(get_current_active_user_from_request),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    asset_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    Query audit logs with optional filters.

    **Requires:** `audit_read` permission

    **Query Parameters:**
    - user_id: Filter by user ID
    - action: Filter by action type
    - asset_id: Filter by railway asset ID
    - resource_type: Filter by resource type
    - start_date: Start of date range
    - end_date: End of date range
    - limit: Maximum results (default 100, max 1000)
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required",
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
                limit=limit,
            )
        elif asset_id:
            asset_uuid = UUID(asset_id)
            logs = audit_logger.get_asset_history(
                asset_id=asset_uuid,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        else:
            from cortex.database import get_database_manager
            from cortex.models import AuditLog

            db = get_database_manager()
            with db.get_session() as session:
                query = session.query(AuditLog)

                if start_date:
                    query = query.filter(AuditLog.timestamp >= start_date)
                if end_date:
                    query = query.filter(AuditLog.timestamp <= end_date)
                if action:
                    query = query.filter(AuditLog.action == action)
                if resource_type:
                    query = query.filter(AuditLog.resource_type == resource_type)

                query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
                results = query.all()

                logs = [
                    {
                        "id": str(log.id),
                        "action": log.action,
                        "user_id": str(log.user_id) if log.user_id else None,
                        "resource_type": log.resource_type,
                        "resource_id": str(log.resource_id) if log.resource_id else None,
                        "asset_id": str(log.asset_id) if log.asset_id else None,
                        "ip_address": str(log.ip_address) if log.ip_address else None,
                        "timestamp": log.timestamp.isoformat(),
                        "details": log.details,
                    }
                    for log in results
                ]

        return [AuditLogResponse(**log) for log in logs]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}",
        )
    except Exception as e:
        logger.error("get_audit_logs_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs",
        )


@router.get("/user/{user_id}/history", response_model=List[AuditLogResponse])
async def get_user_audit_history(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=500),
):
    """
    Get audit history for a specific user.

    **Requires:** `audit_read` permission OR viewing own history
    """
    user_uuid = UUID(user_id)
    user_permissions = get_user_permissions(current_user)

    # Allow users to view their own history
    if current_user.id != user_uuid:
        if Permission.AUDIT_READ not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission 'audit_read' required",
            )

    try:
        audit_logger = AuditLogger()
        history = audit_logger.get_user_history(
            user_id=user_uuid,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [AuditLogResponse(**log) for log in history]

    except Exception as e:
        logger.error("get_user_history_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user history",
        )


@router.get("/asset/{asset_id}/history", response_model=List[AuditLogResponse])
async def get_asset_audit_history(
    asset_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=500),
):
    """
    Get full audit history for a railway asset (EN 50128 traceability).

    **Requires:** `audit_read` permission

    **EN 50128:** Asset traceability is mandatory for Class B software.
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required",
        )

    try:
        audit_logger = AuditLogger()
        asset_uuid = UUID(asset_id)
        history = audit_logger.get_asset_history(
            asset_id=asset_uuid,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [AuditLogResponse(**log) for log in history]

    except Exception as e:
        logger.error("get_asset_history_error", error=str(e), asset_id=asset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve asset history",
        )


@router.get("/requirement/{requirement_id}/history", response_model=List[AuditLogResponse])
async def get_requirement_audit_history(
    requirement_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=500),
):
    """
    Get audit history for a requirement (EN 50128 traceability).

    **Requires:** `audit_read` permission

    **EN 50128:** Bidirectional requirement traceability is mandatory.
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required",
        )

    try:
        audit_logger = AuditLogger()
        req_uuid = UUID(requirement_id)
        history = audit_logger.get_requirement_history(
            requirement_id=req_uuid,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [AuditLogResponse(**log) for log in history]

    except Exception as e:
        logger.error("get_requirement_history_error", error=str(e), requirement_id=requirement_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve requirement history",
        )


# === Compliance Reports ===

@router.get("/reports/compliance", response_model=dict)
async def get_compliance_report(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """
    Generate EN 50128 / IEC 62443 compliance report.

    **Requires:** `audit_read` permission

    **EN 50128:** Periodic compliance audits are mandatory for Class B.
    Includes:
    - Authentication summary
    - Requirement traceability metrics
    - Document events
    - Safety incidents
    - SOUP management
    - Compliance checklist
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required",
        )

    try:
        audit_logger = AuditLogger()
        report = audit_logger.get_compliance_report(
            start_date=start_date,
            end_date=end_date,
        )
        return report

    except Exception as e:
        logger.error("compliance_report_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report",
        )


# === Railway Incident Management ===

@router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_req: IncidentCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Create a railway safety incident report.

    **Requires:** `incident_create` permission

    **EN 50128 / ISO 9001:** All safety incidents must be documented and traced.
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.INCIDENT_CREATE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'incident_create' required",
        )

    try:
        incident_manager = RailwayIncidentManager()

        incident_id = incident_manager.create_incident(
            title=incident_req.title,
            severity=incident_req.severity,
            incident_type=incident_req.incident_type,
            description=incident_req.description,
            asset_id=UUID(incident_req.asset_id) if incident_req.asset_id else None,
            details=incident_req.details,
            user_id=current_user.id,
            is_safety_critical=incident_req.is_safety_critical,
            is_reportable=incident_req.is_reportable,
            detected_by="user",
        )

        if not incident_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create incident",
            )

        return {
            "incident_id": str(incident_id),
            "message": "Railway safety incident created successfully",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}",
        )
    except Exception as e:
        logger.error("create_incident_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create safety incident",
        )


@router.post("/incidents/{incident_id}/close", status_code=status.HTTP_200_OK)
async def close_incident(
    incident_id: str,
    close_req: IncidentCloseRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Close a railway safety incident with root cause analysis.

    **Requires:** `incident_create` permission

    **EN 50128:** Incidents must be closed with documented root cause and mitigation.
    """
    user_permissions = get_user_permissions(current_user)

    if Permission.INCIDENT_CREATE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'incident_create' required",
        )

    try:
        incident_manager = RailwayIncidentManager()
        incident_uuid = UUID(incident_id)

        success = incident_manager.close_incident(
            incident_id=incident_uuid,
            user_id=current_user.id,
            root_cause=close_req.root_cause,
            mitigation_steps=close_req.mitigation_steps,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        return {"message": "Incident closed successfully", "incident_id": incident_id}

    except Exception as e:
        logger.error("close_incident_error", error=str(e), incident_id=incident_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close incident",
        )
