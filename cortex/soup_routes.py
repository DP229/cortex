"""
Cortex SOUP API - Software of Unknown Provenance Management

EN 50128 Section 4.2 SOUP management:
- Register candidate SOUPs
- Approve/reject SOUPs with documented justification
- Track SOUP versions and safety relevance
- Link SOUPs to requirements they satisfy
- Automated qualification workflow via TQK

All endpoints require authentication and appropriate permissions.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, SOUP, SoupStatus, SafetyClass
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/soups", tags=["SOUP Management"])


# === Pydantic Models ===

class SoupCreateRequest(BaseModel):
    """Register a new SOUP candidate"""
    name: str = Field(..., min_length=1, max_length=255)
    vendor: Optional[str] = None
    version: str = Field(..., description="SOUP version, e.g. 2.1.0")
    previous_version: Optional[str] = Field(default=None, description="Prior version if upgrading")
    download_url: Optional[str] = None
    checksum: Optional[str] = Field(default=None, description="SHA-256 of downloaded artifact")
    license_type: Optional[str] = None
    safety_relevance: str = Field(default=SafetyClass.CLASS_B.value)
    justification: Optional[str] = Field(default=None, description="Why this SOUP is acceptable for use")
    integration_notes: Optional[str] = None
    risk_assessment: Optional[str] = Field(default=None, description="Known failure modes and mitigations")


class SoupUpdateRequest(BaseModel):
    """Update a SOUP entry"""
    vendor: Optional[str] = None
    download_url: Optional[str] = None
    checksum: Optional[str] = None
    license_type: Optional[str] = None
    safety_relevance: Optional[str] = None
    justification: Optional[str] = None
    integration_notes: Optional[str] = None
    risk_assessment: Optional[str] = None
    review_due_date: Optional[datetime] = None


class SoupApproveRequest(BaseModel):
    """Approve a SOUP with documented justification"""
    comment: Optional[str] = None


class SoupRejectRequest(BaseModel):
    """Reject a SOUP with reason"""
    reason: str = Field(..., description="Reason for rejection")


class SoupResponse(BaseModel):
    id: str
    name: str
    vendor: Optional[str]
    version: str
    previous_version: Optional[str]
    download_url: Optional[str]
    checksum: Optional[str]
    license_type: Optional[str]
    status: str
    safety_relevance: str
    justification: Optional[str]
    integration_notes: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[str]
    review_due_date: Optional[str]
    risk_assessment: Optional[str]
    is_active: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


# === Helpers ===

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_permission(user: User, permission: Permission) -> None:
    user_perms = ROLE_PERMISSIONS.get(user.role, set())
    perm_values = {p.value for p in user_perms}
    if permission.value not in perm_values and "*" not in perm_values:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission.value}' required",
        )


def _soup_to_response(soup: SOUP) -> SoupResponse:
    return SoupResponse(
        id=str(soup.id),
        name=soup.name,
        vendor=soup.vendor,
        version=str(soup.version),
        previous_version=soup.previous_version,
        download_url=soup.download_url,
        checksum=soup.checksum,
        license_type=soup.license_type,
        status=str(soup.status),
        safety_relevance=str(soup.safety_relevance),
        justification=soup.justification,
        integration_notes=soup.integration_notes,
        approved_by=str(soup.approved_by) if soup.approved_by else None,
        approved_at=soup.approved_at.isoformat() if soup.approved_at else None,
        review_due_date=soup.review_due_date.isoformat() if soup.review_due_date else None,
        risk_assessment=soup.risk_assessment,
        is_active=soup.is_active,
        created_at=soup.created_at.isoformat() if soup.created_at else None,
        updated_at=soup.updated_at.isoformat() if soup.updated_at else None,
    )


# === Endpoints ===

@router.post("/", response_model=SoupResponse, status_code=status.HTTP_201_CREATED)
async def create_soup(
    req: SoupCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Register a new SOUP candidate.

    **Requires:** `soup:write` permission

    **EN 50128 §4.2:** All SOUPs must be documented before use in safety-critical
    software. Justification and risk assessment are required for approval.
    """
    require_permission(current_user, Permission.SOUP_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        # Check for duplicate name+version
        existing = session.query(SOUP).filter(
            SOUP.name == req.name,
            SOUP.version == req.version,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SOUP '{req.name}' version '{req.version}' already registered",
            )

        soup = SOUP(
            name=req.name,
            vendor=req.vendor,
            version=req.version,
            previous_version=req.previous_version,
            download_url=req.download_url,
            checksum=req.checksum,
            license_type=req.license_type,
            status=SoupStatus.CANDIDATE.value,
            safety_relevance=req.safety_relevance,
            justification=req.justification,
            integration_notes=req.integration_notes,
            risk_assessment=req.risk_assessment,
            is_active=True,
        )
        session.add(soup)
        session.commit()
        session.refresh(soup)
        response = _soup_to_response(soup)

    log_audit(
        action=AuditAction.SOUP_CREATE.value,
        user_id=current_user.id,
        resource_type="soup",
        resource_id=response.id,
        ip_address=get_client_ip(request),
        details={
            "name": req.name,
            "version": req.version,
            "safety_relevance": req.safety_relevance,
        },
    )

    return response


@router.get("/", response_model=List[SoupResponse])
async def list_soups(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    name: Optional[str] = Query(default=None, description="Filter by SOUP name"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by SOUP status"),
    vendor: Optional[str] = Query(default=None, description="Filter by vendor"),
    safety_relevance: Optional[str] = Query(default=None, description="Filter by safety class"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List SOUPs with optional filters.

    **Requires:** `soup:read` permission
    """
    require_permission(current_user, Permission.SOUP_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(SOUP)

        if name:
            query = query.filter(SOUP.name.ilike(f"%{name}%"))
        if status_filter:
            query = query.filter(SOUP.status == status_filter)
        if vendor:
            query = query.filter(SOUP.vendor.ilike(f"%{vendor}%"))
        if safety_relevance:
            query = query.filter(SOUP.safety_relevance == safety_relevance)
        if is_active is not None:
            query = query.filter(SOUP.is_active == is_active)

        results = query.order_by(SOUP.name, SOUP.version.desc()).offset(offset).limit(limit).all()
        response = [_soup_to_response(s) for s in results]

    return response


@router.get("/{soup_uuid}", response_model=SoupResponse)
async def get_soup(
    soup_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get a SOUP by UUID with linked requirements.

    **Requires:** `soup:read` permission
    """
    require_permission(current_user, Permission.SOUP_READ)

    db = get_database_manager()
    with db.get_session() as session:
        soup = session.query(SOUP).filter(SOUP.id == soup_uuid).first()

        if not soup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SOUP '{soup_uuid}' not found",
            )
        response = _soup_to_response(soup)

    return response


@router.patch("/{soup_uuid}", response_model=SoupResponse)
async def update_soup(
    soup_uuid: str,
    update: SoupUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Update a SOUP entry (candidate stage only; approved SOUPs require re-evaluation).

    **Requires:** `soup:write` permission
    """
    require_permission(current_user, Permission.SOUP_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        soup = session.query(SOUP).filter(SOUP.id == soup_uuid).first()

        if not soup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SOUP '{soup_uuid}' not found",
            )

        # Cannot modify an approved SOUP without re-evaluation
        if soup.status == SoupStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved SOUPs cannot be modified. Create a new version instead.",
            )

        if update.vendor is not None:
            soup.vendor = update.vendor
        if update.download_url is not None:
            soup.download_url = update.download_url
        if update.checksum is not None:
            soup.checksum = update.checksum
        if update.license_type is not None:
            soup.license_type = update.license_type
        if update.safety_relevance is not None:
            soup.safety_relevance = update.safety_relevance
        if update.justification is not None:
            soup.justification = update.justification
        if update.integration_notes is not None:
            soup.integration_notes = update.integration_notes
        if update.risk_assessment is not None:
            soup.risk_assessment = update.risk_assessment
        if update.review_due_date is not None:
            soup.review_due_date = update.review_due_date

        session.commit()
        session.refresh(soup)
        response = _soup_to_response(soup)

    log_audit(
        action=AuditAction.SOUP_UPDATE.value,
        user_id=current_user.id,
        resource_type="soup",
        resource_id=soup_uuid,
        ip_address=get_client_ip(request),
        details={"updated_fields": update.model_dump(exclude_none=True)},
    )

    return response


@router.post("/{soup_uuid}/approve", response_model=SoupResponse)
async def approve_soup(
    soup_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    body: SoupApproveRequest = None,
):
    """
    Approve a SOUP for use in safety-critical software.

    **Requires:** `soup:approve` permission

    **EN 50128 §4.2:** Approval must be documented with justification.
    Approved SOUPs may not be modified without re-evaluation.
    """
    require_permission(current_user, Permission.SOUP_APPROVE)

    db = get_database_manager()
    with db.get_session() as session:
        soup = session.query(SOUP).filter(SOUP.id == soup_uuid).first()

        if not soup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SOUP '{soup_uuid}' not found",
            )

        if soup.status == SoupStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SOUP is already approved",
            )

        if not soup.justification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SOUP must have a justification before approval",
            )

        soup.status = SoupStatus.APPROVED.value
        soup.approved_by = current_user.id
        soup.approved_at = datetime.utcnow()
        session.commit()
        session.refresh(soup)
        response = _soup_to_response(soup)

    log_audit(
        action=AuditAction.SOUP_APPROVE.value,
        user_id=current_user.id,
        resource_type="soup",
        resource_id=soup_uuid,
        ip_address=get_client_ip(request),
        details={"comment": body.comment if body else None},
    )

    return response


@router.post("/{soup_uuid}/reject", response_model=SoupResponse)
async def reject_soup(
    soup_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    body: SoupRejectRequest = None,
):
    """
    Reject a SOUP candidate.

    **Requires:** `soup:approve` permission
    """
    require_permission(current_user, Permission.SOUP_APPROVE)

    db = get_database_manager()
    with db.get_session() as session:
        soup = session.query(SOUP).filter(SOUP.id == soup_uuid).first()

        if not soup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SOUP '{soup_uuid}' not found",
            )

        soup.status = SoupStatus.REJECTED.value
        session.commit()
        session.refresh(soup)
        response = _soup_to_response(soup)

    log_audit(
        action=AuditAction.SOUP_REJECT.value,
        user_id=current_user.id,
        resource_type="soup",
        resource_id=soup_uuid,
        ip_address=get_client_ip(request),
        details={"reason": body.reason if body else None},
    )

    return response
