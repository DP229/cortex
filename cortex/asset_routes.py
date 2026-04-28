"""
Cortex Asset API - Railway Infrastructure Asset Management

EN 50128 Class B railway asset management:
- Create, read, update railway infrastructure assets
- Hierarchical asset relationships (parent/child)
- Safety class and SIL level assignment
- Link assets to requirements and documents

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
from cortex.models import User, RailwayAsset, AssetType, SafetyClass, SILLevel
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/assets", tags=["Railway Asset Management"])


# === Pydantic Models ===

class AssetCreateRequest(BaseModel):
    """Create a railway infrastructure asset"""
    asset_id: str = Field(..., description="Unique asset identifier, e.g. SIG-001, TRK-North-A")
    asset_type: str = Field(..., description="Asset type from AssetType enum")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, description="GPS coordinates or line/station designation")
    safety_class: str = Field(default=SafetyClass.CLASS_B.value)
    sil_level: str = Field(default=SILLevel.SIL2.value)
    parent_asset_id: Optional[str] = Field(default=None, description="Parent asset UUID for hierarchy")
    metadata: Optional[dict] = None


class AssetUpdateRequest(BaseModel):
    """Update an existing asset"""
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    safety_class: Optional[str] = None
    sil_level: Optional[str] = None
    parent_asset_id: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class AssetResponse(BaseModel):
    id: str
    asset_id: str
    asset_type: str
    name: str
    description: Optional[str]
    location: Optional[str]
    safety_class: str
    sil_level: str
    parent_asset_id: Optional[str]
    is_active: bool
    metadata: Optional[dict]
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class AssetTreeResponse(BaseModel):
    """Asset with its full sub-asset tree"""
    asset: AssetResponse
    sub_assets: List[AssetResponse]


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


def _asset_to_response(asset: RailwayAsset) -> AssetResponse:
    return AssetResponse(
        id=str(asset.id),
        asset_id=str(asset.asset_id),
        asset_type=str(asset.asset_type),
        name=asset.name,
        description=asset.description,
        location=asset.location,
        safety_class=str(asset.safety_class),
        sil_level=str(asset.sil_level),
        parent_asset_id=str(asset.parent_asset_id) if asset.parent_asset_id else None,
        is_active=asset.is_active,
        metadata=asset.metadata_,
        created_at=asset.created_at.isoformat() if asset.created_at else None,
        updated_at=asset.updated_at.isoformat() if asset.updated_at else None,
    )


# === Endpoints ===

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    req: AssetCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Create a new railway infrastructure asset.

    **Requires:** `asset:create` permission

    **EN 50128:** Assets must be classified by safety class and SIL level
    for traceability throughout the software lifecycle.
    """
    require_permission(current_user, Permission.ASSET_CREATE)

    db = get_database_manager()
    with db.get_session() as session:
        # Check for duplicate asset_id
        existing = session.query(RailwayAsset).filter(
            RailwayAsset.asset_id == req.asset_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Asset '{req.asset_id}' already exists",
            )

        # Validate parent if provided
        if req.parent_asset_id:
            parent = session.query(RailwayAsset).filter(
                RailwayAsset.id == req.parent_asset_id
            ).first()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent asset '{req.parent_asset_id}' not found",
                )

        asset = RailwayAsset(
            asset_id=req.asset_id,
            asset_type=req.asset_type,
            name=req.name,
            description=req.description,
            location=req.location,
            safety_class=req.safety_class,
            sil_level=req.sil_level,
            parent_asset_id=req.parent_asset_id,
            metadata_=req.metadata,
            is_active=True,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)

    log_audit(
        action=AuditAction.ASSET_CREATE.value,
        user_id=current_user.id,
        resource_type="asset",
        resource_id=str(asset.id),
        ip_address=get_client_ip(request),
        details={
            "asset_id": req.asset_id,
            "asset_type": req.asset_type,
            "safety_class": req.safety_class,
        },
    )

    return _asset_to_response(asset)


@router.get("/", response_model=List[AssetResponse])
async def list_assets(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    asset_id: Optional[str] = Query(default=None, description="Filter by asset ID prefix"),
    asset_type: Optional[str] = Query(default=None, description="Filter by asset type"),
    safety_class: Optional[str] = Query(default=None, description="Filter by safety class"),
    sil_level: Optional[str] = Query(default=None, description="Filter by SIL level"),
    parent_asset_id: Optional[str] = Query(default=None, description="Filter by parent asset UUID"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List railway assets with optional filters.

    **Requires:** `asset:read` permission
    """
    require_permission(current_user, Permission.ASSET_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(RailwayAsset)

        if asset_id:
            query = query.filter(RailwayAsset.asset_id.ilike(f"{asset_id}%"))
        if asset_type:
            query = query.filter(RailwayAsset.asset_type == asset_type)
        if safety_class:
            query = query.filter(RailwayAsset.safety_class == safety_class)
        if sil_level:
            query = query.filter(RailwayAsset.sil_level == sil_level)
        if parent_asset_id:
            query = query.filter(RailwayAsset.parent_asset_id == parent_asset_id)
        if is_active is not None:
            query = query.filter(RailwayAsset.is_active == is_active)

        results = query.order_by(RailwayAsset.asset_id).offset(offset).limit(limit).all()

    return [_asset_to_response(a) for a in results]


@router.get("/{asset_uuid}", response_model=AssetTreeResponse)
async def get_asset(
    asset_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get an asset with its full sub-asset tree.

    **Requires:** `asset:read` permission
    """
    require_permission(current_user, Permission.ASSET_READ)

    db = get_database_manager()
    with db.get_session() as session:
        asset = session.query(RailwayAsset).filter(
            RailwayAsset.id == asset_uuid
        ).first()

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset '{asset_uuid}' not found",
            )

        # Get all sub-assets recursively
        sub_assets = session.query(RailwayAsset).filter(
            RailwayAsset.parent_asset_id == asset_uuid
        ).all()

    return AssetTreeResponse(
        asset=_asset_to_response(asset),
        sub_assets=[_asset_to_response(a) for a in sub_assets],
    )


@router.patch("/{asset_uuid}", response_model=AssetResponse)
async def update_asset(
    asset_uuid: str,
    update: AssetUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Update a railway asset.

    **Requires:** `asset:write` permission
    """
    require_permission(current_user, Permission.ASSET_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        asset = session.query(RailwayAsset).filter(
            RailwayAsset.id == asset_uuid
        ).first()

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset '{asset_uuid}' not found",
            )

        if update.name is not None:
            asset.name = update.name
        if update.description is not None:
            asset.description = update.description
        if update.location is not None:
            asset.location = update.location
        if update.safety_class is not None:
            asset.safety_class = update.safety_class
        if update.sil_level is not None:
            asset.sil_level = update.sil_level
        if update.parent_asset_id is not None:
            # Prevent circular reference
            if update.parent_asset_id == asset_uuid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Asset cannot be its own parent",
                )
            asset.parent_asset_id = update.parent_asset_id
        if update.is_active is not None:
            asset.is_active = update.is_active
        if update.metadata is not None:
            asset.metadata_ = update.metadata

        session.commit()
        session.refresh(asset)

    log_audit(
        action=AuditAction.ASSET_UPDATE.value,
        user_id=current_user.id,
        resource_type="asset",
        resource_id=asset_uuid,
        ip_address=get_client_ip(request),
        details={"updated_fields": update.model_dump(exclude_none=True)},
    )

    return _asset_to_response(asset)


@router.delete("/{asset_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Soft-delete a railway asset (marks as inactive).

    **Requires:** `asset:delete` permission

    **EN 50128:** Assets must not be permanently deleted — safety records
    must be retained for 10 years minimum.
    """
    require_permission(current_user, Permission.ASSET_DELETE)

    db = get_database_manager()
    with db.get_session() as session:
        asset = session.query(RailwayAsset).filter(
            RailwayAsset.id == asset_uuid
        ).first()

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset '{asset_uuid}' not found",
            )

        asset.is_active = False
        session.commit()

    log_audit(
        action=AuditAction.ASSET_DELETE.value,
        user_id=current_user.id,
        resource_type="asset",
        resource_id=asset_uuid,
        ip_address=get_client_ip(request),
        details={"asset_id": asset.asset_id},
    )
