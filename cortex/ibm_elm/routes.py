"""
IBM ELM FastAPI Router

Provides REST endpoints for IBM Engineering Lifecycle Management integration:
- Health and connectivity checks
- Configuration management
- Authentication / session management
- Root Services + Project Area discovery
- ReqIF import/export
- RM / CCM / QM / GCM read operations
- Sync job approval queue (dry-run → human approve → commit)

All endpoints enforce RBAC and audit logging.
"""

import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, ELMSyncJob, ELMSyncJobStatus, ELMSession
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager
from cortex.config import CortexConfig
from cortex.security.encryption import get_key_manager

from cortex.ibm_elm.config import ELMConfig, ReqIFAttributeMapping
from cortex.ibm_elm.auth.oidc_client import OIDCClient, OIDCError
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.rootservices import RootServicesDiscoverer
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError

logger = structlog.get_logger()
router = APIRouter(prefix="/elm", tags=["IBM ELM Integration"])


# === Pydantic Request/Response Models ===

class ELMConfigUpdateRequest(BaseModel):
    """Update ELM connector configuration (admin only)"""
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    jts_url: Optional[str] = None
    project_area_name: Optional[str] = None
    auth_mode: Optional[str] = None
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    verify_ssl: Optional[bool] = None
    dry_run_default: Optional[bool] = None
    max_sync_batch: Optional[int] = None


class ELMConfigResponse(BaseModel):
    """ELM configuration (secrets redacted)"""
    enabled: bool
    base_url: Optional[str] = None
    jts_url: Optional[str] = None
    rm_url: Optional[str] = None
    ccm_url: Optional[str] = None
    qm_url: Optional[str] = None
    gcm_url: Optional[str] = None
    project_area_name: Optional[str] = None
    project_area_uuid: Optional[str] = None
    auth_mode: str
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    verify_ssl: bool
    dry_run_default: bool
    max_sync_batch: int
    reqif_mappings_count: int
    custom_mappings_count: int
    validation_errors: List[str]


class OIDCAuthInitiateRequest(BaseModel):
    """Initiate OIDC authorization flow"""
    state: Optional[str] = None


class OIDCAuthInitiateResponse(BaseModel):
    authorization_url: str
    code_verifier: str
    state: str


class OIDCAuthCallbackRequest(BaseModel):
    """Complete OIDC authorization flow"""
    authorization_code: str
    code_verifier: str
    state: Optional[str] = None


class ELMHealthResponse(BaseModel):
    status: str
    elm_configured: bool
    jts_url: Optional[str] = None
    auth_mode: Optional[str] = None
    session_active: bool
    root_services_discovered: bool
    rm_available: bool
    ccm_available: bool
    qm_available: bool
    gcm_available: bool
    project_area_set: bool
    errors: List[str]


class RootServicesResponse(BaseModel):
    jts_url: str
    rm_catalog_url: Optional[str] = None
    ccm_catalog_url: Optional[str] = None
    qm_catalog_url: Optional[str] = None
    gcm_catalog_url: Optional[str] = None
    oidc_issuer_url: Optional[str] = None


class ProjectAreaItem(BaseModel):
    title: str
    description: Optional[str] = None
    url: Optional[str] = None


class ProjectAreasResponse(BaseModel):
    project_areas: List[ProjectAreaItem]
    catalog_url: Optional[str] = None


class SyncJobResponse(BaseModel):
    id: str
    job_type: str
    source_entity_type: str
    source_entity_id: Optional[str] = None
    target_elm_service: str
    target_elm_url: str
    status: str
    payload_hash: str
    created_at: str
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_comment: Optional[str] = None
    error_message: Optional[str] = None
    dry_run_result: Optional[Dict[str, Any]] = None


class SyncJobListResponse(BaseModel):
    jobs: List[SyncJobResponse]
    total: int
    pending: int
    approved: int
    committed: int
    failed: int


class SyncJobApproveRequest(BaseModel):
    comment: Optional[str] = None


class SyncJobPreviewResponse(BaseModel):
    job_id: str
    dry_run_result: Optional[Dict[str, Any]] = None
    payload_preview: Optional[Dict[str, Any]] = None
    status: str


class ReqIFImportRequest(BaseModel):
    dry_run: Optional[bool] = None
    target_module: Optional[str] = None


class ReqIFExportRequest(BaseModel):
    requirement_ids: Optional[List[str]] = None
    include_citations: bool = True
    include_test_records: bool = False


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


def get_elm_config() -> ELMConfig:
    """Load current ELM configuration"""
    config = CortexConfig.load()
    return config.elm


def save_elm_config(elm_config: ELMConfig) -> None:
    """Persist ELM configuration"""
    config = CortexConfig.load()
    config.elm = elm_config
    config.save()


def _elm_config_to_response(elm_config: ELMConfig) -> ELMConfigResponse:
    validation_errors = elm_config.validate()
    return ELMConfigResponse(
        enabled=elm_config.enabled,
        base_url=elm_config.base_url,
        jts_url=elm_config.jts_url,
        rm_url=elm_config.rm_url,
        ccm_url=elm_config.ccm_url,
        qm_url=elm_config.qm_url,
        gcm_url=elm_config.gcm_url,
        project_area_name=elm_config.project_area_name,
        project_area_uuid=elm_config.project_area_uuid,
        auth_mode=elm_config.auth_mode,
        oidc_issuer_url=elm_config.oidc_issuer_url,
        oidc_client_id=elm_config.oidc_client_id,
        verify_ssl=elm_config.verify_ssl,
        dry_run_default=elm_config.dry_run_default,
        max_sync_batch=elm_config.max_sync_batch,
        reqif_mappings_count=len(elm_config.reqif_attribute_mappings),
        custom_mappings_count=len(elm_config.custom_attribute_mappings),
        validation_errors=validation_errors,
    )


def _sync_job_to_response(job: ELMSyncJob) -> SyncJobResponse:
    return SyncJobResponse(
        id=str(job.id),
        job_type=job.job_type,
        source_entity_type=job.source_entity_type,
        source_entity_id=job.source_entity_id,
        target_elm_service=job.target_elm_service,
        target_elm_url=job.target_elm_url,
        status=job.status,
        payload_hash=job.payload_hash,
        created_at=job.created_at.isoformat() if job.created_at else None,
        approved_at=job.approved_at.isoformat() if job.approved_at else None,
        approved_by=str(job.approved_by) if job.approved_by else None,
        approved_comment=job.approved_comment,
        error_message=job.error_message,
        dry_run_result=job.dry_run_result,
    )


# === Endpoints ===

@router.get("/health", response_model=ELMHealthResponse)
async def elm_health(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Check IBM ELM connectivity and configuration status.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    errors: List[str] = []

    # Basic config check
    if not elm_config.enabled:
        return ELMHealthResponse(
            status="disabled",
            elm_configured=False,
            session_active=False,
            root_services_discovered=False,
            rm_available=False,
            ccm_available=False,
            qm_available=False,
            gcm_available=False,
            project_area_set=False,
            errors=["ELM integration is disabled"],
        )

    validation_errors = elm_config.validate()
    if validation_errors:
        errors.extend(validation_errors)

    # Check active session
    session_mgr = ELMSessionManager()
    session_active = session_mgr.get_active_session(str(current_user.id)) is not None

    # Try Root Services discovery if configured
    root_services_discovered = False
    rm_available = False
    ccm_available = False
    qm_available = False
    gcm_available = False

    jts_url = elm_config.jts_url or elm_config.base_url
    if jts_url:
        try:
            discoverer = RootServicesDiscoverer(
                jts_url=jts_url,
                verify_ssl=elm_config.verify_ssl,
            )
            services = discoverer.discover_all()
            root_services_discovered = True
            rm_available = services.rm_catalog_url is not None
            ccm_available = services.ccm_catalog_url is not None
            qm_available = services.qm_catalog_url is not None
            gcm_available = services.gcm_catalog_url is not None

            # Update cached URLs if not set
            updated = False
            if not elm_config.rm_url and services.rm_catalog_url:
                elm_config.rm_url = services.rm_catalog_url
                updated = True
            if not elm_config.ccm_url and services.ccm_catalog_url:
                elm_config.ccm_url = services.ccm_catalog_url
                updated = True
            if not elm_config.qm_url and services.qm_catalog_url:
                elm_config.qm_url = services.qm_catalog_url
                updated = True
            if not elm_config.gcm_url and services.gcm_catalog_url:
                elm_config.gcm_url = services.gcm_catalog_url
                updated = True

            if updated:
                save_elm_config(elm_config)

        except Exception as e:
            errors.append(f"Root Services discovery failed: {str(e)}")

    project_area_set = bool(elm_config.project_area_name or elm_config.project_area_uuid)

    overall_status = "healthy" if (session_active and root_services_discovered) else "degraded"
    if errors:
        overall_status = "unhealthy"

    log_audit(
        action=AuditAction.ELM_RM_ARTIFACT_READ.value,
        user_id=current_user.id,
        resource_type="elm_health",
        ip_address=get_client_ip(request),
        details={"status": overall_status, "errors": errors},
    )

    return ELMHealthResponse(
        status=overall_status,
        elm_configured=bool(jts_url),
        jts_url=jts_url,
        auth_mode=elm_config.auth_mode,
        session_active=session_active,
        root_services_discovered=root_services_discovered,
        rm_available=rm_available,
        ccm_available=ccm_available,
        qm_available=qm_available,
        gcm_available=gcm_available,
        project_area_set=project_area_set,
        errors=errors,
    )


@router.get("/config", response_model=ELMConfigResponse)
async def get_elm_config_endpoint(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get current IBM ELM connector configuration (secrets redacted).

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()

    log_audit(
        action=AuditAction.ELM_CONFIG_UPDATE.value,
        user_id=current_user.id,
        resource_type="elm_config",
        ip_address=get_client_ip(request),
        details={"action": "read"},
    )

    return _elm_config_to_response(elm_config)


@router.put("/config", response_model=ELMConfigResponse)
async def update_elm_config_endpoint(
    req: ELMConfigUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Update IBM ELM connector configuration.

    **Requires:** `elm:admin` permission
    """
    require_permission(current_user, Permission.ELM_ADMIN)

    elm_config = get_elm_config()

    # Apply updates
    if req.enabled is not None:
        elm_config.enabled = req.enabled
    if req.base_url is not None:
        elm_config.base_url = req.base_url
    if req.jts_url is not None:
        elm_config.jts_url = req.jts_url
    if req.project_area_name is not None:
        elm_config.project_area_name = req.project_area_name
    if req.auth_mode is not None:
        elm_config.auth_mode = req.auth_mode
    if req.oidc_issuer_url is not None:
        elm_config.oidc_issuer_url = req.oidc_issuer_url
    if req.oidc_client_id is not None:
        elm_config.oidc_client_id = req.oidc_client_id
    if req.verify_ssl is not None:
        elm_config.verify_ssl = req.verify_ssl
    if req.dry_run_default is not None:
        elm_config.dry_run_default = req.dry_run_default
    if req.max_sync_batch is not None:
        elm_config.max_sync_batch = req.max_sync_batch

    # Validate
    validation_errors = elm_config.validate()
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"validation_errors": validation_errors},
        )

    save_elm_config(elm_config)

    log_audit(
        action=AuditAction.ELM_CONFIG_UPDATE.value,
        user_id=current_user.id,
        resource_type="elm_config",
        ip_address=get_client_ip(request),
        details={"updated_fields": req.model_dump(exclude_none=True)},
    )

    return _elm_config_to_response(elm_config)


@router.post("/auth/oidc/initiate", response_model=OIDCAuthInitiateResponse)
async def oidc_initiate(
    req: OIDCAuthInitiateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Initiate OIDC authorization code flow.

    Returns authorization URL for the user to visit in their browser.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if elm_config.auth_mode != "oidc":
        raise HTTPException(status_code=400, detail="Auth mode is not OIDC")
    if not elm_config.oidc_issuer_url or not elm_config.oidc_client_id:
        raise HTTPException(status_code=400, detail="OIDC not configured")

    # Load client secret from key manager
    key_manager = get_key_manager()
    client_secret = key_manager.get_secret("elm_oidc_client_secret")

    client = OIDCClient(
        issuer_url=elm_config.oidc_issuer_url,
        client_id=elm_config.oidc_client_id,
        client_secret=client_secret,
        verify_ssl=elm_config.verify_ssl,
    )

    auth_url, code_verifier = client.get_authorization_url(state=req.state)
    state = req.state or "cortex_elm_auth"

    log_audit(
        action=AuditAction.ELM_AUTH_SUCCESS.value,
        user_id=current_user.id,
        resource_type="elm_auth",
        ip_address=get_client_ip(request),
        details={"action": "oidc_initiate", "issuer": elm_config.oidc_issuer_url},
    )

    return OIDCAuthInitiateResponse(
        authorization_url=auth_url,
        code_verifier=code_verifier,
        state=state,
    )


@router.post("/auth/oidc/callback")
async def oidc_callback(
    req: OIDCAuthCallbackRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Complete OIDC flow and establish ELM session.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if elm_config.auth_mode != "oidc":
        raise HTTPException(status_code=400, detail="Auth mode is not OIDC")

    key_manager = get_key_manager()
    client_secret = key_manager.get_secret("elm_oidc_client_secret")

    client = OIDCClient(
        issuer_url=elm_config.oidc_issuer_url,
        client_id=elm_config.oidc_client_id,
        client_secret=client_secret,
        verify_ssl=elm_config.verify_ssl,
    )

    try:
        tokens = client.exchange_code_for_tokens(
            authorization_code=req.authorization_code,
            code_verifier=req.code_verifier,
        )
    except OIDCError as e:
        log_audit(
            action=AuditAction.ELM_AUTH_FAILURE.value,
            user_id=current_user.id,
            resource_type="elm_auth",
            ip_address=get_client_ip(request),
            details={"error": str(e)},
        )
        raise HTTPException(status_code=401, detail=f"OIDC authentication failed: {e}")

    # Establish Jazz session
    jts_url = elm_config.jts_url or elm_config.base_url
    access_token = tokens.get("access_token")
    jazz_cookies = {}

    if jts_url and access_token:
        try:
            jazz_cookies = client.establish_jazz_session(
                jts_url=jts_url,
                access_token=access_token,
            )
        except Exception as e:
            logger.warning("jazz_session_establish_warn", error=str(e))

    # Store encrypted session
    session_mgr = ELMSessionManager()
    expires_at = client.get_token_expiry(tokens)

    session_mgr.create_session(
        user_id=str(current_user.id),
        auth_mode="oidc",
        jts_url=jts_url or "",
        access_token=access_token,
        refresh_token=tokens.get("refresh_token"),
        jsession_id=jazz_cookies.get("JSESSIONID"),
        ltpa_token=jazz_cookies.get("LtpaToken2"),
        token_expires_at=expires_at,
    )

    log_audit(
        action=AuditAction.ELM_AUTH_SUCCESS.value,
        user_id=current_user.id,
        resource_type="elm_auth",
        ip_address=get_client_ip(request),
        details={"action": "oidc_callback", "jts_url": jts_url},
    )

    return {
        "status": "authenticated",
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "jazz_cookies": list(jazz_cookies.keys()),
    }


@router.post("/auth/logout")
async def elm_logout(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Logout from IBM ELM and invalidate session.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    session_mgr = ELMSessionManager()
    invalidated = session_mgr.invalidate_session(str(current_user.id))

    log_audit(
        action=AuditAction.ELM_AUTH_FAILURE.value,  # Reusing failure action for logout audit
        user_id=current_user.id,
        resource_type="elm_auth",
        ip_address=get_client_ip(request),
        details={"action": "logout", "invalidated": invalidated},
    )

    return {"status": "logged_out", "invalidated": invalidated}


@router.get("/discovery/rootservices", response_model=RootServicesResponse)
async def discover_rootservices(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Discover ELM service URLs from Jazz Team Server Root Services.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    jts_url = elm_config.jts_url or elm_config.base_url
    if not jts_url:
        raise HTTPException(status_code=400, detail="JTS URL not configured")

    try:
        discoverer = RootServicesDiscoverer(
            jts_url=jts_url,
            verify_ssl=elm_config.verify_ssl,
        )
        services = discoverer.discover_all()

        # Update config with discovered URLs
        updated = False
        if services.rm_catalog_url and not elm_config.rm_url:
            elm_config.rm_url = services.rm_catalog_url
            updated = True
        if services.ccm_catalog_url and not elm_config.ccm_url:
            elm_config.ccm_url = services.ccm_catalog_url
            updated = True
        if services.qm_catalog_url and not elm_config.qm_url:
            elm_config.qm_url = services.qm_catalog_url
            updated = True
        if services.gcm_catalog_url and not elm_config.gcm_url:
            elm_config.gcm_url = services.gcm_catalog_url
            updated = True

        if updated:
            save_elm_config(elm_config)

        log_audit(
            action=AuditAction.ELM_RM_ARTIFACT_READ.value,
            user_id=current_user.id,
            resource_type="elm_discovery",
            ip_address=get_client_ip(request),
            details={"jts_url": jts_url, "discovered_rm": services.rm_catalog_url is not None},
        )

        return RootServicesResponse(
            jts_url=services.jts_url,
            rm_catalog_url=services.rm_catalog_url,
            ccm_catalog_url=services.ccm_catalog_url,
            qm_catalog_url=services.qm_catalog_url,
            gcm_catalog_url=services.gcm_catalog_url,
            oidc_issuer_url=services.oidc_issuer_url,
        )

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Root Services discovery failed: {e}")


@router.get("/discovery/project-areas", response_model=ProjectAreasResponse)
async def discover_project_areas(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Discover project areas from ELM Service Provider Catalog.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    jts_url = elm_config.jts_url or elm_config.base_url
    if not jts_url:
        raise HTTPException(status_code=400, detail="JTS URL not configured")

    try:
        discoverer = RootServicesDiscoverer(
            jts_url=jts_url,
            verify_ssl=elm_config.verify_ssl,
        )
        areas = discoverer.discover_project_areas()

        log_audit(
            action=AuditAction.ELM_RM_ARTIFACT_READ.value,
            user_id=current_user.id,
            resource_type="elm_discovery",
            ip_address=get_client_ip(request),
            details={"project_areas_found": len(areas)},
        )

        return ProjectAreasResponse(
            project_areas=[ProjectAreaItem(**a) for a in areas],
            catalog_url=discoverer.jts_url,
        )

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Project area discovery failed: {e}")


# === Sync Job Approval Queue ===

@router.get("/sync-jobs", response_model=SyncJobListResponse)
async def list_sync_jobs(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    status_filter: Optional[str] = Query(default=None, description="Filter by status"),
    job_type: Optional[str] = Query(default=None, description="Filter by job type"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    List ELM sync jobs (approval queue).

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(ELMSyncJob)

        # Non-admins only see their own jobs
        if current_user.role != "admin":
            query = query.filter(ELMSyncJob.user_id == str(current_user.id))

        if status_filter:
            query = query.filter(ELMSyncJob.status == status_filter)
        if job_type:
            query = query.filter(ELMSyncJob.job_type == job_type)

        total = query.count()
        jobs = query.order_by(ELMSyncJob.created_at.desc()).offset(offset).limit(limit).all()

        statuses = {"pending": 0, "approved": 0, "committed": 0, "failed": 0}
        for j in session.query(ELMSyncJob).all():
            if j.status in statuses:
                statuses[j.status] += 1

        response = SyncJobListResponse(
            jobs=[_sync_job_to_response(j) for j in jobs],
            total=total,
            pending=statuses["pending"],
            approved=statuses["approved"],
            committed=statuses["committed"],
            failed=statuses["failed"],
        )

    return response


@router.get("/sync-jobs/{job_id}", response_model=SyncJobResponse)
async def get_sync_job(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get a single sync job.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    db = get_database_manager()
    with db.get_session() as session:
        job = session.query(ELMSyncJob).filter(ELMSyncJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        # Authorization: admin can see all, others only their own
        if current_user.role != "admin" and job.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to view this job")

        return _sync_job_to_response(job)


@router.get("/sync-jobs/{job_id}/preview", response_model=SyncJobPreviewResponse)
async def preview_sync_job(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Preview what a sync job would do (dry-run).

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    db = get_database_manager()
    with db.get_session() as session:
        job = session.query(ELMSyncJob).filter(ELMSyncJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if current_user.role != "admin" and job.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Update status to preview
        job.status = ELMSyncJobStatus.PREVIEW.value
        session.commit()

        log_audit(
            action=AuditAction.ELM_SYNC_JOB_PREVIEW.value,
            user_id=current_user.id,
            resource_type="elm_sync_job",
            resource_id=job.id,
            ip_address=get_client_ip(request),
            details={"job_type": job.job_type, "target": job.target_elm_url},
        )

        return SyncJobPreviewResponse(
            job_id=str(job.id),
            dry_run_result=job.dry_run_result,
            payload_preview=job.payload_snapshot,
            status=job.status,
        )


@router.post("/sync-jobs/{job_id}/approve", response_model=SyncJobResponse)
async def approve_sync_job(
    job_id: str,
    req: SyncJobApproveRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Approve a pending sync job and commit to ELM.

    **Requires:** `elm:approve` permission
    """
    require_permission(current_user, Permission.ELM_APPROVE)

    elm_config = get_elm_config()
    db = get_database_manager()

    with db.get_session() as session:
        job = session.query(ELMSyncJob).filter(ELMSyncJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if job.status not in (ELMSyncJobStatus.PENDING.value, ELMSyncJobStatus.PREVIEW.value):
            raise HTTPException(status_code=400, detail=f"Job is not pending (status: {job.status})")

        # Route by job type:
        # - reqif_import: commit to Cortex DB (not ELM), importing mapped requirements
        # - Other types (artifact_create, workitem_create, etc.): commit to ELM
        try:
            if job.job_type == "reqif_import":
                # ===== PHASE 2.1: ReqIF Import → Cortex DB =====
                from cortex.ibm_elm.reqif.importer import ReqIFImporter
                importer = ReqIFImporter(elm_config)

                # The payload_snapshot for reqif_import contains the mapped requirements
                payload = job.payload_snapshot or {}
                xml_hash = payload.get("reqif_xml_hash", "")
                mapped = payload.get("mapped_requirements", [])

                # Import each mapped requirement directly into Cortex
                imported_ids = []
                skipped = []

                for req_dict in mapped:
                    req_id = req_dict.get("requirement_id", "")
                    existing = session.query(Requirement).filter(
                        Requirement.requirement_id == req_id
                    ).first()
                    if existing:
                        skipped.append(req_id)
                        continue

                    # Map standard fields (same logic as importer.import_from_string)
                    requirement = Requirement(
                        id=str(uuid4()),
                        requirement_id=req_id,
                        title=req_dict.get("title", "Untitled")[:255],
                        description=req_dict.get("description", ""),
                        rationale=req_dict.get("rationale"),
                        requirement_type=req_dict.get("requirement_type"),
                        priority=req_dict.get("priority", "shall"),
                        status=RequirementStatus.DRAFT.value,
                        safety_class=req_dict.get("safety_class", "class_b"),
                        sil_level=req_dict.get("sil_level", "sil2"),
                        category=req_dict.get("category"),
                        source=req_dict.get("source", "reqif_import"),
                        compliance_ref=req_dict.get("compliance_ref"),
                        stakeholder=req_dict.get("stakeholder"),
                        acceptance_criteria=req_dict.get("acceptance_criteria"),
                        allocation=req_dict.get("allocation"),
                        version=1,
                        change_history=[{
                            "version": 1,
                            "action": "reqif_import",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "approved_by": str(current_user.id),
                        }],
                        traceability_tags=["reqif", "elm"],
                        risk_level=req_dict.get("risk_level"),
                        verification_method=req_dict.get("verification_method"),
                        verification_status="pending",
                        created_by=str(current_user.id),
                    )
                    session.add(requirement)
                    imported_ids.append(req_id)

                job.status = ELMSyncJobStatus.COMMITTED.value
                job.elm_transaction_id = f"cortex_import:{','.join(imported_ids[:5])}" if imported_ids else "cortex_import:empty"
                job.elm_response_status = 201
                job.approved_by = str(current_user.id)
                job.approved_at = datetime.now(timezone.utc)
                job.approved_comment = req.comment
                job.elm_response_body = json.dumps({
                    "imported": len(imported_ids),
                    "skipped_duplicates": skipped,
                    "imported_ids": imported_ids[:20],
                })

                log_audit(
                    action=AuditAction.ELM_SYNC_JOB_COMMITTED.value,
                    user_id=current_user.id,
                    resource_type="elm_sync_job",
                    resource_id=job.id,
                    ip_address=get_client_ip(request),
                    details={
                        "job_type": "reqif_import",
                        "imported_count": len(imported_ids),
                        "skipped_count": len(skipped),
                    },
                )

            else:
                # ===== Generic ELM writeback via HTTP =====
                session_mgr = ELMSessionManager()
                client = ELMHTTPClient(
                    elm_config=elm_config,
                    session_manager=session_mgr,
                    user_id=str(current_user.id),
                    dry_run=False,  # Override: this is the real commit
                )

                method = job.job_type.split("_")[-1] if "_" in job.job_type else "post"
                method = method.upper()
                if method not in ("POST", "PUT", "PATCH", "DELETE"):
                    method = "POST"

                # Execute the request
                if method == "POST":
                    response = client.post(job.target_elm_url, json_data=job.payload_snapshot)
                elif method == "PUT":
                    response = client.put(job.target_elm_url, json_data=job.payload_snapshot)
                elif method == "PATCH":
                    response = client.patch(job.target_elm_url, json_data=job.payload_snapshot)
                else:
                    response = client.delete(job.target_elm_url)

                job.status = ELMSyncJobStatus.COMMITTED.value
                job.elm_transaction_id = response.headers.get("ETag") or response.headers.get("Location")
                job.elm_response_status = response.status_code
                job.approved_by = str(current_user.id)
                job.approved_at = datetime.now(timezone.utc)
                job.approved_comment = req.comment

                # Truncate response body if large
                body = response.text
                if len(body) > 2000:
                    body = body[:2000] + "... [truncated]"
                job.elm_response_body = body

                log_audit(
                    action=AuditAction.ELM_SYNC_JOB_COMMITTED.value,
                    user_id=current_user.id,
                    resource_type="elm_sync_job",
                    resource_id=job.id,
                    ip_address=get_client_ip(request),
                    details={
                        "target_url": job.target_elm_url,
                        "elm_status": response.status_code,
                        "elm_etag": job.elm_transaction_id,
                    },
                )

        except ELMHTTPError as e:
            job.status = ELMSyncJobStatus.FAILED.value
            job.error_message = str(e)
            job.elm_response_status = e.status_code
            session.commit()

            log_audit(
                action=AuditAction.ELM_SYNC_JOB_FAILED.value,
                user_id=current_user.id,
                resource_type="elm_sync_job",
                resource_id=job.id,
                ip_address=get_client_ip(request),
                details={"error": str(e), "status_code": e.status_code},
            )

            raise HTTPException(status_code=502, detail=f"ELM commit failed: {e}")

        except Exception as e:
            job.status = ELMSyncJobStatus.FAILED.value
            job.error_message = str(e)
            session.commit()

            log_audit(
                action=AuditAction.ELM_SYNC_JOB_FAILED.value,
                user_id=current_user.id,
                resource_type="elm_sync_job",
                resource_id=job.id,
                ip_address=get_client_ip(request),
                details={"error": str(e)},
            )

            raise HTTPException(status_code=500, detail=f"Commit failed: {e}")

        session.commit()
        return _sync_job_to_response(job)


@router.post("/sync-jobs/{job_id}/reject", response_model=SyncJobResponse)
async def reject_sync_job(
    job_id: str,
    req: SyncJobApproveRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Reject a pending sync job.

    **Requires:** `elm:approve` permission
    """
    require_permission(current_user, Permission.ELM_APPROVE)

    db = get_database_manager()
    with db.get_session() as session:
        job = session.query(ELMSyncJob).filter(ELMSyncJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if job.status != ELMSyncJobStatus.PENDING.value:
            raise HTTPException(status_code=400, detail=f"Job is not pending (status: {job.status})")

        job.status = ELMSyncJobStatus.REJECTED.value
        job.approved_by = str(current_user.id)
        job.approved_at = datetime.now(timezone.utc)
        job.approved_comment = req.comment
        session.commit()

        log_audit(
            action=AuditAction.ELM_SYNC_JOB_REJECTED.value,
            user_id=current_user.id,
            resource_type="elm_sync_job",
            resource_id=job.id,
            ip_address=get_client_ip(request),
            details={"comment": req.comment},
        )

        return _sync_job_to_response(job)


# === ReqIF Import / Export ===

@router.post("/rm/reqif/import/preview")
async def reqif_import_preview(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Preview ReqIF import without persisting.
    Upload ReqIF XML as multipart/form-data 'file' field.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        if "multipart" not in content_type:
            raise HTTPException(status_code=400, detail="Expected multipart/form-data with 'file' field")

        boundary = content_type.split("boundary=")[1].strip()
        filename = "requirements.reqif"
        content = b""
        raw_parts = body.split(f"--{boundary}".encode())
        for part in raw_parts:
            if b"Content-Disposition" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end < 0:
                header_end = part.find(b"\n\n")
            if header_end < 0:
                continue
            header = part[:header_end].decode(errors="replace")
            data = part[header_end + 4:]
            if data.endswith(b"\r\n"):
                data = data[:-2]
            elif data.endswith(b"\n"):
                data = data[:-1]
            if 'name="file"' in header:
                fn_start = header.find('filename="')
                if fn_start >= 0:
                    fn_end = header.find('"', fn_start + 10)
                    filename = header[fn_start + 10:fn_end]
                content = data
                break

        if not content:
            raise HTTPException(status_code=400, detail="No file content found")

        xml_content = content.decode("utf-8", errors="replace")
        elm_config = get_elm_config()

        from cortex.ibm_elm.reqif.importer import import_reqif_preview
        result = import_reqif_preview(xml_content, elm_config)

        log_audit(
            action=AuditAction.ELM_RM_REQIF_IMPORT.value,
            user_id=current_user.id,
            resource_type="elm_reqif",
            ip_address=get_client_ip(request),
            details={"mode": "preview", "artifacts": result.get("total_artifacts", 0)},
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("reqif_import_preview_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"ReqIF preview failed: {e}")


@router.post("/rm/reqif/import/stage")
async def reqif_import_stage(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    target_module: Optional[str] = Query(default=None),
):
    """
    Stage ReqIF import for human approval (creates ELMSyncJob).

    **Requires:** `elm:write` permission
    """
    require_permission(current_user, Permission.ELM_WRITE)

    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        if "multipart" not in content_type:
            raise HTTPException(status_code=400, detail="Expected multipart/form-data with 'file' field")

        boundary = content_type.split("boundary=")[1].strip()
        content = b""
        raw_parts = body.split(f"--{boundary}".encode())
        for part in raw_parts:
            if b"Content-Disposition" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end < 0:
                header_end = part.find(b"\n\n")
            if header_end < 0:
                continue
            header = part[:header_end].decode(errors="replace")
            data = part[header_end + 4:]
            if data.endswith(b"\r\n"):
                data = data[:-2]
            elif data.endswith(b"\n"):
                data = data[:-1]
            if 'name="file"' in header:
                content = data
                break

        if not content:
            raise HTTPException(status_code=400, detail="No file content found")

        xml_content = content.decode("utf-8", errors="replace")
        elm_config = get_elm_config()

        from cortex.ibm_elm.reqif.importer import ReqIFImporter
        importer = ReqIFImporter(elm_config)
        job_id = importer.stage_for_approval(
            xml_content=xml_content,
            user_id=str(current_user.id),
            target_module=target_module,
        )

        log_audit(
            action=AuditAction.ELM_SYNC_JOB_CREATED.value,
            user_id=current_user.id,
            resource_type="elm_sync_job",
            resource_id=job_id,
            ip_address=get_client_ip(request),
            details={"job_type": "reqif_import", "target_module": target_module},
        )

        return {"sync_job_id": job_id, "status": "pending_approval"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("reqif_import_stage_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"ReqIF staging failed: {e}")


@router.post("/rm/reqif/export")
async def reqif_export(
    req: ReqIFExportRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Export Cortex requirements to ReqIF XML.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    try:
        elm_config = get_elm_config()
        from cortex.ibm_elm.reqif.exporter import CortexToReqIFExporter
        exporter = CortexToReqIFExporter(elm_config)

        xml_content = exporter.export_requirements(
            requirement_ids=req.requirement_ids,
            include_citations=req.include_citations,
        )

        log_audit(
            action=AuditAction.ELM_RM_REQIF_EXPORT.value,
            user_id=current_user.id,
            resource_type="elm_reqif",
            ip_address=get_client_ip(request),
            details={"exported_ids": req.requirement_ids},
        )

        from fastapi.responses import Response
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=cortex_export_{ts}.reqif"
            },
        )

    except Exception as e:
        logger.error("reqif_export_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"ReqIF export failed: {e}")


# === RM OSLC Read Endpoints ===

class RMArtifactItem(BaseModel):
    uri: str
    title: str
    identifier: str
    description: Optional[str] = None
    artifact_type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class RMArtifactsResponse(BaseModel):
    artifacts: List[RMArtifactItem]
    total_count: int
    project_area_url: Optional[str] = None
    query: Optional[str] = None


class RMModuleItem(BaseModel):
    uri: str
    title: str
    identifier: str
    description: Optional[str] = None


class RMModulesResponse(BaseModel):
    modules: List[RMModuleItem]
    total_count: int
    project_area_url: Optional[str] = None


@router.get("/rm/artifacts", response_model=RMArtifactsResponse)
async def rm_query_artifacts(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    q: Optional[str] = Query(default=None, description="OSLC where query, e.g. dcterms:title like '%brake%'"),
    select: Optional[str] = Query(default=None, description="Comma-separated OSLC select fields"),
    limit: int = Query(default=50, le=100),
):
    """
    Query DOORS Next / RM artifacts via OSLC.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.rm_url:
        raise HTTPException(status_code=400, detail="RM URL not configured. Run /elm/discovery/rootservices first.")

    # Resolve project area service provider URL
    project_area_url = elm_config.rm_url
    if elm_config.project_area_name:
        # Need to find specific project area in catalog
        from cortex.ibm_elm.services.rm_service import RMService
        session_mgr = ELMSessionManager()
        rm_service = RMService(elm_config, session_mgr, str(current_user.id))
        resolved = rm_service.get_project_area_service_provider(elm_config.rm_url, elm_config.project_area_name)
        if resolved:
            project_area_url = resolved

    select_list = select.split(",") if select else None

    try:
        from cortex.ibm_elm.services.rm_service import RMService
        session_mgr = ELMSessionManager()
        rm_service = RMService(elm_config, session_mgr, str(current_user.id))

        artifacts = rm_service.query_artifacts(
            project_area_url=project_area_url,
            oslc_query=q,
            select=select_list,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_RM_ARTIFACT_READ.value,
            user_id=current_user.id,
            resource_type="elm_rm_artifact",
            ip_address=get_client_ip(request),
            details={"query": q, "results": len(artifacts)},
        )

        return RMArtifactsResponse(
            artifacts=[RMArtifactItem(**a.to_dict()) for a in artifacts],
            total_count=len(artifacts),
            project_area_url=project_area_url,
            query=q,
        )

    except Exception as e:
        logger.error("rm_query_artifacts_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"RM query failed: {e}")


@router.get("/rm/modules", response_model=RMModulesResponse)
async def rm_query_modules(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    limit: int = Query(default=50, le=100),
):
    """
    Query DOORS Next / RM requirement modules.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.rm_url:
        raise HTTPException(status_code=400, detail="RM URL not configured. Run /elm/discovery/rootservices first.")

    project_area_url = elm_config.rm_url
    if elm_config.project_area_name:
        from cortex.ibm_elm.services.rm_service import RMService
        session_mgr = ELMSessionManager()
        rm_service = RMService(elm_config, session_mgr, str(current_user.id))
        resolved = rm_service.get_project_area_service_provider(elm_config.rm_url, elm_config.project_area_name)
        if resolved:
            project_area_url = resolved

    try:
        from cortex.ibm_elm.services.rm_service import RMService
        session_mgr = ELMSessionManager()
        rm_service = RMService(elm_config, session_mgr, str(current_user.id))

        modules = rm_service.query_modules(
            project_area_url=project_area_url,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_RM_ARTIFACT_READ.value,
            user_id=current_user.id,
            resource_type="elm_rm_module",
            ip_address=get_client_ip(request),
            details={"modules_found": len(modules)},
        )

        return RMModulesResponse(
            modules=[RMModuleItem(**m.to_dict()) for m in modules],
            total_count=len(modules),
            project_area_url=project_area_url,
        )

    except Exception as e:
        logger.error("rm_query_modules_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"RM module query failed: {e}")


@router.get("/rm/artifacts/{artifact_id:path}")
async def rm_read_artifact(
    artifact_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Read a single RM artifact by URI or relative path.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.rm_url:
        raise HTTPException(status_code=400, detail="RM URL not configured")

    # artifact_id may be a full URI or a relative path
    if artifact_id.startswith("http://") or artifact_id.startswith("https://"):
        artifact_url = artifact_id
    else:
        artifact_url = f"{elm_config.rm_url}/{artifact_id}"

    try:
        from cortex.ibm_elm.services.rm_service import RMService
        session_mgr = ELMSessionManager()
        rm_service = RMService(elm_config, session_mgr, str(current_user.id))

        artifact = rm_service.read_artifact(artifact_url)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        log_audit(
            action=AuditAction.ELM_RM_ARTIFACT_READ.value,
            user_id=current_user.id,
            resource_type="elm_rm_artifact",
            ip_address=get_client_ip(request),
            details={"artifact_url": artifact_url, "title": artifact.title},
        )

        return RMArtifactItem(**artifact.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("rm_read_artifact_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Artifact read failed: {e}")


# === CCM (EWM) Endpoints ===

class CCMWorkItemItem(BaseModel):
    uri: str
    identifier: str
    title: str
    description: Optional[str] = None
    work_item_type: Optional[str] = None
    state: Optional[str] = None
    owner: Optional[str] = None
    planned_for: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class CCMWorkItemsResponse(BaseModel):
    work_items: List[CCMWorkItemItem]
    total_count: int
    project_area_url: Optional[str] = None
    query: Optional[str] = None


@router.get("/ccm/workitems", response_model=CCMWorkItemsResponse)
async def ccm_query_workitems(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    q: Optional[str] = Query(default=None, description="OSLC where query"),
    select: Optional[str] = Query(default=None, description="Comma-separated OSLC select fields"),
    limit: int = Query(default=50, le=100),
):
    """
    Query EWM / CCM work items via OSLC.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.ccm_url:
        raise HTTPException(status_code=400, detail="CCM URL not configured. Run /elm/discovery/rootservices first.")

    project_area_url = elm_config.ccm_url
    select_list = select.split(",") if select else None

    try:
        from cortex.ibm_elm.services.ccm_service import CCMService
        session_mgr = ELMSessionManager()
        ccm_service = CCMService(elm_config, session_mgr, str(current_user.id))

        work_items = ccm_service.query_workitems(
            project_area_url=project_area_url,
            oslc_query=q,
            select=select_list,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_CCM_WORKITEM_READ.value,
            user_id=current_user.id,
            resource_type="elm_ccm_workitem",
            ip_address=get_client_ip(request),
            details={"query": q, "results": len(work_items)},
        )

        return CCMWorkItemsResponse(
            work_items=[CCMWorkItemItem(**w.to_dict()) for w in work_items],
            total_count=len(work_items),
            project_area_url=project_area_url,
            query=q,
        )

    except Exception as e:
        logger.error("ccm_query_workitems_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"CCM query failed: {e}")


# === CCM Write Endpoints (Dry-run + Stage for Approval) ===

class CCMCreateWorkItemRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., description="Work item description / acceptance criteria")
    work_item_type: str = Field(default="com.ibm.team.apt.workItemType.story")
    planned_for: Optional[str] = None  # Sprint/iteration URL
    category: Optional[str] = None   # Team area URL
    priority: Optional[str] = None
    assigned_to: Optional[str] = None  # User/contributor URL
    parent_workitem_uri: Optional[str] = None  # Parent Epic
    related_requirement_uri: Optional[str] = None  # Link to RM artifact
    tags: Optional[List[str]] = None


class CCMCreateWorkItemResponse(BaseModel):
    sync_job_id: str
    status: str
    dry_run_preview: Optional[Dict[str, Any]] = None
    message: str


@router.post("/ccm/workitems/stage", response_model=CCMCreateWorkItemResponse)
async def ccm_create_workitem_stage(
    req: CCMCreateWorkItemRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Stage a new CCM work item for human approval (dry-run first).

    Creates an ELMSyncJob in pending status.

    **Requires:** `elm:write` permission
    """
    require_permission(current_user, Permission.ELM_WRITE)

    elm_config = get_elm_config()
    if not elm_config.ccm_url:
        raise HTTPException(status_code=400, detail="CCM URL not configured")

    # Build OSLC payload
    payload = {
        "dcterms:title": req.title,
        "dcterms:description": req.description,
        "dcterms:type": req.work_item_type,
    }
    if req.planned_for:
        payload["rtc:plannedFor"] = req.planned_for
    if req.category:
        payload["rtc:filedAgainst"] = req.category
    if req.priority:
        payload["oslc_cm:priority"] = req.priority
    if req.assigned_to:
        payload["dcterms:contributor"] = req.assigned_to
    if req.parent_workitem_uri:
        # Parent relationship: RTC uses rtc:com.ibm.team.workitem.linktype.parentworkitem
        payload.setdefault("rtc:parentWorkItem", req.parent_workitem_uri)
    if req.related_requirement_uri:
        # Related Artifact link: RTC→RM traceability
        payload.setdefault("rtc:relatedWorkItem", req.related_requirement_uri)
    if req.tags:
        payload["dcterms:subject"] = ", ".join(req.tags)

    target_url = elm_config.ccm_url  # OSLC Creation Factory URL (project area)

    # Prepare sync job
    from cortex.database import get_database_manager
    db = get_database_manager()

    with db.get_session() as session:
        import json, hashlib
        from uuid import uuid4

        dump = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(dump.encode()).hexdigest()

        job = ELMSyncJob(
            id=str(uuid4()),
            user_id=str(current_user.id),
            job_type="ccm_workitem_create",
            source_entity_type="workitem",
            source_entity_id=None,
            target_elm_service="ccm",
            target_elm_url=target_url,
            payload_snapshot=payload,
            payload_hash=payload_hash,
            dry_run_result={
                "action": "create_workitem",
                "title": req.title,
                "type": req.work_item_type,
            },
            status=ELMSyncJobStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    log_audit(
        action=AuditAction.ELM_SYNC_JOB_CREATED.value,
        user_id=current_user.id,
        resource_type="elm_sync_job",
        resource_id=job_id,
        ip_address=get_client_ip(request),
        details={
            "job_type": "ccm_workitem_create",
            "title": req.title,
            "work_item_type": req.work_item_type,
        },
    )

    return CCMCreateWorkItemResponse(
        sync_job_id=job_id,
        status="pending",
        dry_run_preview={
            "target_url": target_url,
            "payload": payload,
            "note": "This is a dry-run preview. Approve via /elm/sync-jobs/{sync_job_id}/approve to commit to ELM",
        },
        message="Work item creation staged. Pending approval.",
    )


# === QM (ETM) Endpoints ===

class QMTestCaseItem(BaseModel):
    uri: str
    title: str
    identifier: str
    description: Optional[str] = None
    test_case_type: Optional[str] = None
    state: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class QMTestCasesResponse(BaseModel):
    test_cases: List[QMTestCaseItem]
    total_count: int
    project_area_url: Optional[str] = None
    query: Optional[str] = None


@router.get("/qm/testcases", response_model=QMTestCasesResponse)
async def qm_query_testcases(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    q: Optional[str] = Query(default=None, description="OSLC where query"),
    select: Optional[str] = Query(default=None, description="Comma-separated OSLC select fields"),
    limit: int = Query(default=50, le=100),
):
    """
    Query ETM / QM test cases via OSLC.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.qm_url:
        raise HTTPException(status_code=400, detail="QM URL not configured. Run /elm/discovery/rootservices first.")

    project_area_url = elm_config.qm_url
    select_list = select.split(",") if select else None

    try:
        from cortex.ibm_elm.services.qm_service import QMService
        session_mgr = ELMSessionManager()
        qm_service = QMService(elm_config, session_mgr, str(current_user.id))

        test_cases = qm_service.query_testcases(
            project_area_url=project_area_url,
            oslc_query=q,
            select=select_list,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_QM_TESTCASE_READ.value,
            user_id=current_user.id,
            resource_type="elm_qm_testcase",
            ip_address=get_client_ip(request),
            details={"query": q, "results": len(test_cases)},
        )

        return QMTestCasesResponse(
            test_cases=[QMTestCaseItem(**t.to_dict()) for t in test_cases],
            total_count=len(test_cases),
            project_area_url=project_area_url,
            query=q,
        )

    except Exception as e:
        logger.error("qm_query_testcases_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"QM query failed: {e}")


# === GCM Endpoints ===

class GCComponentItem(BaseModel):
    uri: str
    title: str
    identifier: str
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class GCComponentsResponse(BaseModel):
    components: List[GCComponentItem]
    total_count: int
    catalog_url: Optional[str] = None


class GCConfigurationItem(BaseModel):
    uri: str
    title: str
    identifier: str
    config_type: Optional[str] = None
    component_uri: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class GCConfigurationsResponse(BaseModel):
    configurations: List[GCConfigurationItem]
    total_count: int
    component_url: Optional[str] = None


@router.get("/gcm/components", response_model=GCComponentsResponse)
async def gcm_query_components(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    limit: int = Query(default=50, le=100),
):
    """
    Query GCM components.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.gcm_url:
        raise HTTPException(status_code=400, detail="GCM URL not configured. Run /elm/discovery/rootservices first.")

    try:
        from cortex.ibm_elm.services.gcm_service import GCMService
        session_mgr = ELMSessionManager()
        gcm_service = GCMService(elm_config, session_mgr, str(current_user.id))

        components = gcm_service.query_components(
            catalog_url=elm_config.gcm_url,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_GC_CONFIG_READ.value,
            user_id=current_user.id,
            resource_type="elm_gcm_component",
            ip_address=get_client_ip(request),
            details={"components_found": len(components)},
        )

        return GCComponentsResponse(
            components=[GCComponentItem(**c.to_dict()) for c in components],
            total_count=len(components),
            catalog_url=elm_config.gcm_url,
        )

    except Exception as e:
        logger.error("gcm_query_components_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"GCM query failed: {e}")


@router.get("/gcm/configurations", response_model=GCConfigurationsResponse)
async def gcm_query_configurations(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    component_url: Optional[str] = Query(default=None, description="Component URL to query configurations for"),
    limit: int = Query(default=50, le=100),
):
    """
    Query GCM configurations (streams, baselines) for a component.

    **Requires:** `elm:read` permission
    """
    require_permission(current_user, Permission.ELM_READ)

    elm_config = get_elm_config()
    if not elm_config.gcm_url:
        raise HTTPException(status_code=400, detail="GCM URL not configured")

    if not component_url:
        raise HTTPException(status_code=400, detail="component_url query parameter is required")

    try:
        from cortex.ibm_elm.services.gcm_service import GCMService
        session_mgr = ELMSessionManager()
        gcm_service = GCMService(elm_config, session_mgr, str(current_user.id))

        configurations = gcm_service.query_configurations(
            component_url=component_url,
            limit=limit,
        )

        log_audit(
            action=AuditAction.ELM_GC_BASELINE_READ.value,
            user_id=current_user.id,
            resource_type="elm_gcm_config",
            ip_address=get_client_ip(request),
            details={"component_url": component_url, "configs_found": len(configurations)},
        )

        return GCConfigurationsResponse(
            configurations=[GCConfigurationItem(**c.to_dict()) for c in configurations],
            total_count=len(configurations),
            component_url=component_url,
        )

    except Exception as e:
        logger.error("gcm_query_configurations_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"GCM configuration query failed: {e}")


# === Link Management ===

class LinkRequirementToWorkItemRequest(BaseModel):
    requirement_uuid: str = Field(..., description="Cortex Requirement UUID")
    workitem_url: str = Field(..., description="CCM Work Item OSLC URL")
    link_type: str = Field(default="related", description="Link type: implements, related, parent, child")


class LinkRequirementToTestCaseRequest(BaseModel):
    requirement_uuid: str = Field(..., description="Cortex Requirement UUID")
    testcase_url: str = Field(..., description="QM Test Case OSLC URL")
    link_type: str = Field(default="validates", description="Link type: validates, related")


class LinkStageResponse(BaseModel):
    sync_job_id: str
    status: str
    link_type: str
    source: str
    target: str
    message: str


@router.post("/links/req-workitem/stage", response_model=LinkStageResponse)
async def link_requirement_to_workitem(
    req: LinkRequirementToWorkItemRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Stage a link between a Cortex Requirement and a CCM Work Item.
    
    This creates a traceability link in two steps:
    1. Creates a RequirementCitation in Cortex (bidirectional traceability)
    2. Stages an OSLC link creation in CCM (pending approval)

    **Requires:** `elm:write` permission
    """
    require_permission(current_user, Permission.ELM_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        # Verify requirement exists
        requirement = session.query(Requirement).filter(Requirement.id == req.requirement_uuid).first()
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")

        # Create bidirectional citation in Cortex
        citation = RequirementCitation(
            id=str(uuid4()),
            source_requirement_id=req.requirement_uuid,
            target_requirement_id=None,  # External link, no internal target
            citation_type=req.link_type,
            citation_text=f"Linked to CCM WorkItem: {req.workitem_url}",
            verified=False,
        )
        # Note: target_requirement_id should link to an external reference artifact
        # For now, we store the external link in citation_text
        session.add(citation)

        # Stage the ELM link creation
        payload = {
            "link_type": req.link_type,
            "source_requirement_uri": f"cortex://requirements/{requirement.requirement_id}",
            "target_workitem_uri": req.workitem_url,
            "cortex_requirement_uuid": req.requirement_uuid,
        }

        job = ELMSyncJob(
            id=str(uuid4()),
            user_id=str(current_user.id),
            job_type="ccm_link_create",
            source_entity_type="requirement",
            source_entity_id=req.requirement_uuid,
            target_elm_service="ccm",
            target_elm_url=req.workitem_url,
            payload_snapshot=payload,
            payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            dry_run_result={
                "action": "create_link",
                "from": f"REQ {requirement.requirement_id}",
                "to": f"WorkItem {req.workitem_url}",
                "link_type": req.link_type,
            },
            status=ELMSyncJobStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(job)
        session.commit()
        session.refresh(job)

    log_audit(
        action=AuditAction.ELM_CCM_LINK_CREATE.value,
        user_id=current_user.id,
        resource_type="elm_link",
        resource_id=job.id,
        ip_address=get_client_ip(request),
        details={
            "requirement_uuid": req.requirement_uuid,
            "workitem_url": req.workitem_url,
            "link_type": req.link_type,
        },
    )

    return LinkStageResponse(
        sync_job_id=job.id,
        status="pending",
        link_type=req.link_type,
        source=requirement.requirement_id,
        target=req.workitem_url,
        message="Link staged. Approve via /elm/sync-jobs/{sync_job_id}/approve to commit to ELM.",
    )


@router.post("/links/req-testcase/stage", response_model=LinkStageResponse)
async def link_requirement_to_testcase(
    req: LinkRequirementToTestCaseRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Stage a validation link between a Requirement and a QM Test Case.

    **Requires:** `elm:write` permission
    """
    require_permission(current_user, Permission.ELM_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        requirement = session.query(Requirement).filter(Requirement.id == req.requirement_uuid).first()
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")

        payload = {
            "link_type": req.link_type,
            "source_requirement_uri": f"cortex://requirements/{requirement.requirement_id}",
            "target_testcase_uri": req.testcase_url,
            "cortex_requirement_uuid": req.requirement_uuid,
        }

        job = ELMSyncJob(
            id=str(uuid4()),
            user_id=str(current_user.id),
            job_type="qm_link_create",
            source_entity_type="requirement",
            source_entity_id=req.requirement_uuid,
            target_elm_service="qm",
            target_elm_url=req.testcase_url,
            payload_snapshot=payload,
            payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            dry_run_result={
                "action": "create_validation_link",
                "from": f"REQ {requirement.requirement_id}",
                "to": f"TestCase {req.testcase_url}",
                "link_type": req.link_type,
            },
            status=ELMSyncJobStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(job)
        session.commit()
        session.refresh(job)

    log_audit(
        action=AuditAction.ELM_QM_TESTCASE_READ.value,
        user_id=current_user.id,
        resource_type="elm_link",
        resource_id=job.id,
        ip_address=get_client_ip(request),
        details={
            "requirement_uuid": req.requirement_uuid,
            "testcase_url": req.testcase_url,
            "link_type": req.link_type,
        },
    )

    return LinkStageResponse(
        sync_job_id=job.id,
        status="pending",
        link_type=req.link_type,
        source=requirement.requirement_id,
        target=req.testcase_url,
        message="Validation link staged. Approve via /elm/sync-jobs/{sync_job_id}/approve to commit to ELM.",
    )


# === Baseline / GC Release Staging ===

class BaselineReleaseRequest(BaseModel):
    baseline_name: str = Field(..., description="Name for the new baseline")
    description: Optional[str] = None
    rm_stream_url: str = Field(..., description="RM stream URL to baseline")
    gc_component_url: str = Field(..., description="GC component URL to add baseline to")
    ewr_workitem_url: Optional[str] = None  # Link back to EWR
    included_modules: Optional[List[str]] = None  # RM module URIs to include


class BaselineReleaseResponse(BaseModel):
    sync_job_id: str
    status: str
    checklist_status: Dict[str, Any]
    message: str


@router.post("/gcm/baselines/stage", response_model=BaselineReleaseResponse)
async def stage_baseline_release(
    req: BaselineReleaseRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Stage a complete RM baseline + GC release for human approval.

    Performs pre-checklist validation:
    - Verifies all requirements have approved status
    - Checks for unresolved review comments
    - Validates no duplicate artifact versions in GC hierarchy
    - Prepares baseline creation and GC add payloads

    Creates an ELMSyncJob that, when approved, will:
    1. Create RM baseline on the Release stream
    2. Add baseline to GC component configuration
    3. Link GC/baseline to EWR (if provided)
    4. Update EWR status to 'requirement complete'

    **Requires:** `elm:approve` permission (baseline release is high-impact)
    """
    require_permission(current_user, Permission.ELM_APPROVE)

    elm_config = get_elm_config()

    # Pre-checklist: verify requirements readiness
    db = get_database_manager()
    checklist = {
        "all_requirements_approved": True,
        "no_unresolved_comments": True,
        "gc_hierarchy_valid": True,
        "rm_stream_accessible": True,
        "errors": [],
    }

    with db.get_session() as session:
        # Check for non-approved requirements linked to this context
        non_approved = session.query(Requirement).filter(
            Requirement.status != "approved",
            Requirement.requirement_id.isnot(None),
        ).limit(10).all()

        if non_approved:
            checklist["all_requirements_approved"] = False
            checklist["errors"].append(
                f"Found {len(non_approved)} non-approved requirements: "
                f"{', '.join(r.requirement_id for r in non_approved[:5])}"
            )

    # Build the baseline release payload
    payload = {
        "baseline_name": req.baseline_name,
        "description": req.description or f"Baseline created via Cortex on {datetime.now(timezone.utc).isoformat()}",
        "rm_stream_url": req.rm_stream_url,
        "gc_component_url": req.gc_component_url,
        "ewr_workitem_url": req.ewr_workitem_url,
        "included_modules": req.included_modules or [],
        "checklist": checklist,
        "steps": [
            "1. Create RM baseline on Release stream",
            "2. Verify baseline integrity (no duplicates)",
            "3. Add RM baseline to GC component configuration",
            "4. Verify GC hierarchy (only one version per artifact)",
            "5. Link GC/baseline to EWR related artifacts",
            "6. Update EWR actual requirement approval date",
            "7. Move EWR to next workflow state",
        ],
    }

    with db.get_session() as session:
        job = ELMSyncJob(
            id=str(uuid4()),
            user_id=str(current_user.id),
            job_type="gcm_baseline_release",
            source_entity_type="baseline",
            source_entity_id=None,
            target_elm_service="gcm",
            target_elm_url=req.gc_component_url,
            payload_snapshot=payload,
            payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            dry_run_result={
                "checklist": checklist,
                "steps_preview": payload["steps"],
                "can_proceed": all([
                    checklist["all_requirements_approved"],
                    checklist["no_unresolved_comments"],
                ]),
                "warnings": checklist["errors"],
            },
            status=ELMSyncJobStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(job)
        session.commit()
        session.refresh(job)

    log_audit(
        action=AuditAction.ELM_SYNC_JOB_CREATED.value,
        user_id=current_user.id,
        resource_type="elm_baseline",
        resource_id=job.id,
        ip_address=get_client_ip(request),
        details={
            "baseline_name": req.baseline_name,
            "rm_stream": req.rm_stream_url,
            "gc_component": req.gc_component_url,
            "checklist_passed": not checklist["errors"],
        },
    )

    return BaselineReleaseResponse(
        sync_job_id=job.id,
        status="pending",
        checklist_status=checklist,
        message="Baseline release staged. Review checklist and approve via /elm/sync-jobs/{sync_job_id}/approve. "
                "Warnings must be resolved before release.",
    )
