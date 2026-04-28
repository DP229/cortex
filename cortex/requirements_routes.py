"""
Cortex Requirements API - EN 50128 Railway Safety Compliance

EN 50128 Class B requirements management with bidirectional traceability:
- Create, read, update, delete software requirements
- Traceability citations between requirements (verifies, refines, conflicts)
- Link requirements to assets, SOUPs, and test records
- Verification status tracking
- Safety class and SIL level enforcement

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
from cortex.models import (
    User, Requirement, RequirementCitation,
    RequirementPriority, RequirementStatus, VerificationStatus,
    SafetyClass, SILLevel,
)
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/requirements", tags=["Requirements Management"])


# === Pydantic Models ===

class RequirementCreateRequest(BaseModel):
    """Create a new EN 50128 software requirement"""
    requirement_id: str = Field(..., description="Unique requirement ID, e.g. REQ-SIG-001")
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., description="Full requirement text")
    priority: str = Field(default=RequirementPriority.SHALL.value)
    safety_class: str = Field(default=SafetyClass.CLASS_B.value)
    sil_level: str = Field(default=SILLevel.SIL2.value)
    category: Optional[str] = Field(default=None, description="functional, safety, security, performance")
    asset_id: Optional[str] = Field(default=None, description="Linked railway asset UUID")
    soup_id: Optional[str] = Field(default=None, description="Linked SOUP UUID if derived from SOUP")
    parent_requirement_id: Optional[str] = Field(default=None, description="Parent requirement UUID for hierarchy")
    traceability_tags: Optional[List[str]] = Field(default=None, description="Upstream standard tags, e.g. EN50128, IEC62304")
    risk_level: Optional[str] = Field(default=None, description="ISO 14971 risk level: high, medium, low")
    verification_method: Optional[str] = Field(default=None, description="inspection, analysis, test")
    created_by: Optional[str] = None  # Set from current_user in handler


class RequirementUpdateRequest(BaseModel):
    """Update an existing requirement"""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    safety_class: Optional[str] = None
    sil_level: Optional[str] = None
    category: Optional[str] = None
    asset_id: Optional[str] = None
    traceability_tags: Optional[List[str]] = None
    risk_level: Optional[str] = None
    verification_method: Optional[str] = None
    verification_status: Optional[str] = None


class RequirementApproveRequest(BaseModel):
    """Approve a requirement"""
    comment: Optional[str] = None


class CitationCreateRequest(BaseModel):
    """Create a traceability citation between two requirements"""
    source_requirement_id: str = Field(..., description="Source requirement UUID")
    target_requirement_id: str = Field(..., description="Target requirement UUID")
    citation_type: str = Field(..., description="verifies, satisfies, conflicts_with, refines")
    citation_text: Optional[str] = None


class RequirementResponse(BaseModel):
    id: str
    requirement_id: str
    title: str
    description: str
    priority: str
    status: str
    safety_class: str
    sil_level: str
    category: Optional[str]
    asset_id: Optional[str]
    soup_id: Optional[str]
    parent_requirement_id: Optional[str]
    traceability_tags: Optional[List[str]]
    risk_level: Optional[str]
    verification_method: Optional[str]
    verification_status: str
    created_by: str
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class CitationResponse(BaseModel):
    id: str
    source_requirement_id: str
    target_requirement_id: str
    citation_type: str
    citation_text: Optional[str]
    verified: bool
    verified_at: Optional[str]
    verified_by: Optional[str]

    class Config:
        from_attributes = True


class RequirementTraceabilityResponse(BaseModel):
    """Full traceability view of a requirement"""
    requirement: RequirementResponse
    citations: List[CitationResponse]
    derived_requirements: List[RequirementResponse]
    test_records: List[dict]


# === Helpers ===

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_permission(user: User, permission: Permission) -> None:
    """Raise 403 if user lacks required permission"""
    user_perms = ROLE_PERMISSIONS.get(user.role, set())
    perm_values = {p.value for p in user_perms}
    if permission.value not in perm_values and "*" not in perm_values:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission.value}' required",
        )


def _requirement_to_response(req: Requirement) -> RequirementResponse:
    return RequirementResponse(
        id=str(req.id),
        requirement_id=str(req.requirement_id),
        title=req.title,
        description=req.description,
        priority=req.priority,
        status=req.status,
        safety_class=req.safety_class,
        sil_level=req.sil_level,
        category=req.category,
        asset_id=str(req.asset_id) if req.asset_id else None,
        soup_id=str(req.soup_id) if req.soup_id else None,
        parent_requirement_id=str(req.parent_requirement_id) if req.parent_requirement_id else None,
        traceability_tags=req.traceability_tags,
        risk_level=req.risk_level,
        verification_method=req.verification_method,
        verification_status=req.verification_status,
        created_by=str(req.created_by),
        created_at=req.created_at.isoformat() if req.created_at else None,
        updated_at=req.updated_at.isoformat() if req.updated_at else None,
    )


def _citation_to_response(c: RequirementCitation) -> CitationResponse:
    return CitationResponse(
        id=str(c.id),
        source_requirement_id=str(c.source_requirement_id),
        target_requirement_id=str(c.target_requirement_id),
        citation_type=c.citation_type,
        citation_text=c.citation_text,
        verified=c.verified,
        verified_at=c.verified_at.isoformat() if c.verified_at else None,
        verified_by=str(c.verified_by) if c.verified_by else None,
    )


# === Endpoints ===

@router.post("/", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_requirement(
    req: RequirementCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Create a new EN 50128 software requirement.

    **Requires:** `requirement:write` permission

    **EN 50128:** Requirements must include safety classification, SIL level,
    verification method, and traceability to upstream standards.
    """
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        # Check for duplicate requirement_id
        existing = session.query(Requirement).filter(
            Requirement.requirement_id == req.requirement_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Requirement '{req.requirement_id}' already exists",
            )

        # Validate asset_id if provided
        if req.asset_id:
            from cortex.models import RailwayAsset
            asset = session.query(RailwayAsset).filter(
                RailwayAsset.id == req.asset_id
            ).first()
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Asset '{req.asset_id}' not found",
                )

        # Validate soup_id if provided
        if req.soup_id:
            from cortex.models import SOUP
            soup = session.query(SOUP).filter(SOUP.id == req.soup_id).first()
            if not soup:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SOUP '{req.soup_id}' not found",
                )

        requirement = Requirement(
            requirement_id=req.requirement_id,
            title=req.title,
            description=req.description,
            priority=req.priority,
            status=RequirementStatus.DRAFT.value,
            safety_class=req.safety_class,
            sil_level=req.sil_level,
            category=req.category,
            asset_id=req.asset_id,
            soup_id=req.soup_id,
            parent_requirement_id=req.parent_requirement_id,
            traceability_tags=req.traceability_tags,
            risk_level=req.risk_level,
            verification_method=req.verification_method,
            verification_status=VerificationStatus.PENDING.value,
            created_by=current_user.id,
        )
        session.add(requirement)
        session.commit()
        session.refresh(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_CREATE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=str(requirement.id),
        ip_address=get_client_ip(request),
        details={
            "requirement_id": req.requirement_id,
            "safety_class": req.safety_class,
            "sil_level": req.sil_level,
        },
    )

    return _requirement_to_response(requirement)


@router.get("/", response_model=List[RequirementResponse])
async def list_requirements(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    requirement_id: Optional[str] = Query(default=None, description="Filter by requirement ID prefix"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    safety_class: Optional[str] = Query(default=None, description="Filter by safety class"),
    asset_id: Optional[str] = Query(default=None, description="Filter by asset UUID"),
    verification_status: Optional[str] = Query(default=None, description="Filter by verification status"),
    soup_id: Optional[str] = Query(default=None, description="Filter by SOUP UUID"),
    created_by: Optional[str] = Query(default=None, description="Filter by creator UUID"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List requirements with optional filters.

    **Requires:** `requirement:read` permission
    """
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(Requirement)

        if requirement_id:
            query = query.filter(Requirement.requirement_id.ilike(f"{requirement_id}%"))
        if status_filter:
            query = query.filter(Requirement.status == status_filter)
        if safety_class:
            query = query.filter(Requirement.safety_class == safety_class)
        if asset_id:
            query = query.filter(Requirement.asset_id == asset_id)
        if verification_status:
            query = query.filter(Requirement.verification_status == verification_status)
        if soup_id:
            query = query.filter(Requirement.soup_id == soup_id)
        if created_by:
            query = query.filter(Requirement.created_by == created_by)

        total = query.count()
        results = query.order_by(Requirement.created_at.desc()).offset(offset).limit(limit).all()

    return [_requirement_to_response(r) for r in results]


@router.get("/{requirement_uuid}", response_model=RequirementTraceabilityResponse)
async def get_requirement(
    requirement_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get a requirement with its full traceability graph.

    **Requires:** `requirement:read` permission

    Returns the requirement plus: upstream citations (what it cites),
    downstream citations (what cites it), derived requirements, and test records.
    """
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        requirement = session.query(Requirement).filter(
            Requirement.id == requirement_uuid
        ).first()

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_uuid}' not found",
            )

        # Citations where this requirement is the source
        upstream = session.query(RequirementCitation).filter(
            RequirementCitation.source_requirement_id == requirement_uuid
        ).all()

        # Citations where this requirement is the target
        downstream = session.query(RequirementCitation).filter(
            RequirementCitation.target_requirement_id == requirement_uuid
        ).all()

        # Derived requirements (children)
        derived = session.query(Requirement).filter(
            Requirement.parent_requirement_id == requirement_uuid
        ).all()

        # Test records
        from cortex.models import TestRecord
        test_records = session.query(TestRecord).filter(
            TestRecord.requirement_id == requirement_uuid
        ).all()

    return RequirementTraceabilityResponse(
        requirement=_requirement_to_response(requirement),
        citations=[_citation_to_response(c) for c in upstream + downstream],
        derived_requirements=[_requirement_to_response(r) for r in derived],
        test_records=[{
            "id": str(t.id),
            "test_id": t.test_id,
            "test_type": t.test_type,
            "status": t.status,
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
        } for t in test_records],
    )


@router.patch("/{requirement_uuid}", response_model=RequirementResponse)
async def update_requirement(
    requirement_uuid: str,
    update: RequirementUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Update a requirement.

    **Requires:** `requirement:write` permission

    **EN 50128:** Requirement changes must be re-verified after modification.
    """
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        requirement = session.query(Requirement).filter(
            Requirement.id == requirement_uuid
        ).first()

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_uuid}' not found",
            )

        # Apply updates
        if update.title is not None:
            requirement.title = update.title
        if update.description is not None:
            requirement.description = update.description
        if update.priority is not None:
            requirement.priority = update.priority
        if update.status is not None:
            requirement.status = update.status
        if update.safety_class is not None:
            requirement.safety_class = update.safety_class
        if update.sil_level is not None:
            requirement.sil_level = update.sil_level
        if update.category is not None:
            requirement.category = update.category
        if update.asset_id is not None:
            requirement.asset_id = update.asset_id
        if update.traceability_tags is not None:
            requirement.traceability_tags = update.traceability_tags
        if update.risk_level is not None:
            requirement.risk_level = update.risk_level
        if update.verification_method is not None:
            requirement.verification_method = update.verification_method
        if update.verification_status is not None:
            requirement.verification_status = update.verification_status
            # Reset approved_by when re-verifying
            if update.verification_status == VerificationStatus.PENDING.value:
                requirement.approved_by = None
                requirement.approved_at = None

        session.commit()
        session.refresh(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_UPDATE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=requirement_uuid,
        ip_address=get_client_ip(request),
        details={"updated_fields": update.model_dump(exclude_none=True)},
    )

    return _requirement_to_response(requirement)


@router.post("/{requirement_uuid}/approve", response_model=RequirementResponse)
async def approve_requirement(
    requirement_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    body: RequirementApproveRequest = None,
):
    """
    Approve a requirement.

    **Requires:** `requirement:approve` permission

    **EN 50128:** Approved requirements must not be modified without re-approval.
    """
    require_permission(current_user, Permission.REQUIREMENT_APPROVE)

    db = get_database_manager()
    with db.get_session() as session:
        requirement = session.query(Requirement).filter(
            Requirement.id == requirement_uuid
        ).first()

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_uuid}' not found",
            )

        requirement.status = RequirementStatus.APPROVED.value
        requirement.approved_by = current_user.id
        requirement.approved_at = datetime.utcnow()
        session.commit()
        session.refresh(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_APPROVE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=requirement_uuid,
        ip_address=get_client_ip(request),
        details={"comment": body.comment if body else None, "action": "approved"},
    )

    return _requirement_to_response(requirement)


# === Traceability Citations ===

@router.post("/citations", response_model=CitationResponse, status_code=status.HTTP_201_CREATED)
async def create_citation(
    citation_req: CitationCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Create a bidirectional traceability citation between two requirements.

    **Requires:** `requirement:write` permission

    **Citation types:**
    - `verifies` — Test/lower-level req verifies this requirement
    - `satisfies` — Parent/architectural requirement is satisfied by this
    - `conflicts_with` — This requirement conflicts with another
    - `refines` — This refines a higher-level requirement
    """
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        # Validate both requirements exist
        source = session.query(Requirement).filter(
            Requirement.id == citation_req.source_requirement_id
        ).first()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source requirement '{citation_req.source_requirement_id}' not found",
            )

        target = session.query(Requirement).filter(
            Requirement.id == citation_req.target_requirement_id
        ).first()
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target requirement '{citation_req.target_requirement_id}' not found",
            )

        # Check for duplicate
        existing = session.query(RequirementCitation).filter(
            RequirementCitation.source_requirement_id == citation_req.source_requirement_id,
            RequirementCitation.target_requirement_id == citation_req.target_requirement_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This citation already exists",
            )

        citation = RequirementCitation(
            source_requirement_id=citation_req.source_requirement_id,
            target_requirement_id=citation_req.target_requirement_id,
            citation_type=citation_req.citation_type,
            citation_text=citation_req.citation_text,
            verified=False,
        )
        session.add(citation)
        session.commit()
        session.refresh(citation)

    log_audit(
        action=AuditAction.REQUIREMENT_CITATION_ADD.value,
        user_id=current_user.id,
        resource_type="requirement_citation",
        resource_id=str(citation.id),
        ip_address=get_client_ip(request),
        details={
            "source": citation_req.source_requirement_id,
            "target": citation_req.target_requirement_id,
            "type": citation_req.citation_type,
        },
    )

    return _citation_to_response(citation)


@router.get("/citations", response_model=List[CitationResponse])
async def list_citations(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    source_id: Optional[str] = Query(default=None, description="Filter by source requirement UUID"),
    target_id: Optional[str] = Query(default=None, description="Filter by target requirement UUID"),
    citation_type: Optional[str] = Query(default=None, description="Filter by citation type"),
    verified: Optional[bool] = Query(default=None, description="Filter by verified status"),
    limit: int = Query(default=100, le=500),
):
    """
    List requirement traceability citations.

    **Requires:** `requirement:read` permission
    """
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(RequirementCitation)

        if source_id:
            query = query.filter(RequirementCitation.source_requirement_id == source_id)
        if target_id:
            query = query.filter(RequirementCitation.target_requirement_id == target_id)
        if citation_type:
            query = query.filter(RequirementCitation.citation_type == citation_type)
        if verified is not None:
            query = query.filter(RequirementCitation.verified == verified)

        results = query.limit(limit).all()

    return [_citation_to_response(c) for c in results]


@router.patch("/citations/{citation_id}/verify", response_model=CitationResponse)
async def verify_citation(
    citation_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Mark a traceability citation as verified.

    **Requires:** `requirement:approve` permission

    **EN 50128:** All critical traceability links must be verified.
    """
    require_permission(current_user, Permission.REQUIREMENT_APPROVE)

    db = get_database_manager()
    with db.get_session() as session:
        citation = session.query(RequirementCitation).filter(
            RequirementCitation.id == citation_id
        ).first()

        if not citation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citation '{citation_id}' not found",
            )

        citation.verified = True
        citation.verified_at = datetime.utcnow()
        citation.verified_by = current_user.id
        session.commit()
        session.refresh(citation)

    log_audit(
        action=AuditAction.REQUIREMENT_CITATION_VERIFY.value,
        user_id=current_user.id,
        resource_type="requirement_citation",
        resource_id=citation_id,
        ip_address=get_client_ip(request),
    )

    return _citation_to_response(citation)
