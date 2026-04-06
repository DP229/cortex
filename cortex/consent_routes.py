"""
Cortex Consent API Endpoints

FastAPI endpoints for consent management:
- Create consent records
- Query consents
- Revoke consents
- Verify authorization
- Manage consent templates
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, validator
import structlog

from cortex.security.auth import get_current_active_user
from cortex.security.rbac import Permission, get_user_permissions
from cortex.models import User, UserRole, ConsentType
from cortex.consent import (
    ConsentManager, ConsentCategory, ConsentStatus,
    get_consent_manager
)
from cortex.audit import log_audit, AuditAction

logger = structlog.get_logger()

router = APIRouter(prefix="/consent", tags=["Consent Management"])


# === Helper Functions ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# === Pydantic Models ===

class ConsentCreateRequest(BaseModel):
    """Consent creation request"""
    patient_id: str
    consent_type: str
    consented: bool
    consent_form: Optional[str] = None
    expiry_days: Optional[int] = None
    notes: Optional[str] = None
    
    @validator('consent_type')
    def validate_consent_type(cls, v):
        valid_types = ["treatment", "research", "disclosure", "agent_processing", "marketing"]
        if v not in valid_types:
            raise ValueError(f'consent_type must be one of: {valid_types}')
        return v


class ConsentResponse(BaseModel):
    """Consent record response"""
    id: str
    patient_id: str
    consent_type: str
    consented: bool
    consent_date: str
    expiry_date: Optional[str] = None
    consent_form: Optional[str] = None
    obtained_by: str
    notes: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True


class RevokeConsentRequest(BaseModel):
    """Consent revocation request"""
    reason: Optional[str] = None


class AuthorizationVerifyRequest(BaseModel):
    """Authorization verification request"""
    patient_id: str
    consent_types: List[str]


class ConsentTemplateRequest(BaseModel):
    """Consent template request"""
    category: str
    patient_data: dict
    
    @validator('category')
    def validate_category(cls, v):
        valid_categories = [
            "treatment", "research", "disclosure", 
            "data_sharing", "agent_processing", "electronic_communication"
        ]
        if v not in valid_categories:
            raise ValueError(f'category must be one of: {valid_categories}')
        return v


class ExpiringConsentsResponse(BaseModel):
    """Expiring consents response"""
    consents: List[dict]
    total: int


# === Endpoints ===

@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    request: Request,
    req: ConsentCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new consent record
    
    **Requires:** `consent_create` permission
    
    **HIPAA:** Consent must be documented for all PHI access
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.CONSENT_CREATE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'consent_create' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        # Convert consent type
        consent_type = ConsentType(req.consent_type)
        
        # Create consent
        patient_uuid = UUID(req.patient_id)
        
        consent_id = consent_manager.create_consent(
            patient_id=patient_uuid,
            consent_type=consent_type,
            consented=req.consented,
            obtained_by=current_user.id,
            consent_form=req.consent_form,
            expiry_days=req.expiry_days,
            notes=req.notes
        )
        
        if not consent_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create consent"
            )
        
        # Get consent record
        consent_data = consent_manager.get_consent(consent_id)
        
        # Audit log
        log_audit(
            action=AuditAction.CONSENT_GRANTED if req.consented else AuditAction.CONSENT_REVOKED,
            user_id=current_user.id,
            patient_id=patient_uuid,
            resource_type="consent",
            resource_id=consent_id,
            ip_address=get_client_ip(request),
            details={
                "consent_type": req.consent_type,
                "consented": req.consented
            }
        )
        
        return ConsentResponse(**consent_data)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("create_consent_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create consent"
        )


@router.get("/{consent_id}", response_model=ConsentResponse)
async def get_consent(
    consent_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get consent record by ID
    
    **Requires:** `consent_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.CONSENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'consent_read' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        consent_uuid = UUID(consent_id)
        consent_data = consent_manager.get_consent(consent_uuid)
        
        if not consent_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consent not found"
            )
        
        # Audit log
        log_audit(
            action=AuditAction.CONSENT_VIEWED,
            user_id=current_user.id,
            patient_id=UUID(consent_data["patient_id"]),
            resource_type="consent",
            resource_id=consent_uuid,
            ip_address=get_client_ip(request)
        )
        
        return ConsentResponse(**consent_data)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_consent_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consent"
        )


@router.get("/patient/{patient_id}", response_model=List[ConsentResponse])
async def get_patient_consents(
    patient_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    active_only: bool = True
):
    """
    Get all consents for a patient
    
    **Requires:** `phi_access` permission
    
    **HIPAA:** Logs all PHI access
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PHI_ACCESS not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'phi_access' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        patient_uuid = UUID(patient_id)
        consents = consent_manager.get_patient_consents(
            patient_id=patient_uuid,
            active_only=active_only
        )
        
        # Audit log
        log_audit(
            action=AuditAction.PHI_ACCESS,
            user_id=current_user.id,
            patient_id=patient_uuid,
            resource_type="consent",
            ip_address=get_client_ip(request),
            details={
                "action": "list_consents",
                "active_only": active_only
            }
        )
        
        return [ConsentResponse(**c) for c in consents]
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("get_patient_consents_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consents"
        )


@router.post("/{consent_id}/revoke")
async def revoke_consent(
    consent_id: str,
    request: Request,
    req: RevokeConsentRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Revoke a consent
    
    **Requires:** `consent_revoke` permission
    
    **HIPAA:** Revocation must be documented
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.CONSENT_REVOKE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'consent_revoke' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        consent_uuid = UUID(consent_id)
        
        # Revoke consent
        success = consent_manager.revoke_consent(
            consent_id=consent_uuid,
            revoked_by=current_user.id,
            reason=req.reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke consent"
            )
        
        # Get consent to log patient_id
        consent_data = consent_manager.get_consent(consent_uuid)
        patient_id = UUID(consent_data["patient_id"]) if consent_data else None
        
        # Audit log
        log_audit(
            action=AuditAction.CONSENT_REVOKED,
            user_id=current_user.id,
            patient_id=patient_id,
            resource_type="consent",
            resource_id=consent_uuid,
            ip_address=get_client_ip(request),
            details={
                "reason": req.reason
            }
        )
        
        return {
            "message": "Consent revoked successfully",
            "consent_id": consent_id
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("revoke_consent_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke consent"
        )


@router.post("/verify", response_model=dict)
async def verify_authorization(
    request: AuthorizationVerifyRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Verify authorization to access patient data
    
    **Requires:** `phi_access` permission
    
    Checks if all required consents are present and valid
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PHI_ACCESS not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'phi_access' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        # Convert consent types
        consent_types = [ConsentType(ct) for ct in request.consent_types]
        
        # Verify authorization
        patient_uuid = UUID(request.patient_id)
        
        result = consent_manager.verify_authorization(
            patient_id=patient_uuid,
            user=current_user,
            consent_types=consent_types
        )
        
        # Audit log
        log_audit(
            action=AuditAction.PHI_ACCESS,
            user_id=current_user.id,
            patient_id=patient_uuid,
            resource_type="authorization",
            ip_address=get_client_ip(req),
            details={
                "action": "verify_authorization",
                "authorized": result["authorized"],
                "missing_consents": result["missing_consents"]
            }
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("verify_authorization_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify authorization"
        )


@router.get("/expiring", response_model=ExpiringConsentsResponse)
async def get_expiring_consents(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    days: int = 30
):
    """
    Get consents expiring within specified days
    
    **Requires:** `audit_read` permission (admin function)
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        consents = consent_manager.get_expiring_consents(days=days)
        
        # Audit log
        log_audit(
            action=AuditAction.PHI_ACCESS,
            user_id=current_user.id,
            resource_type="consent",
            ip_address=get_client_ip(request),
            details={
                "action": "get_expiring_consents",
                "days": days
            }
        )
        
        return ExpiringConsentsResponse(
            consents=consents,
            total=len(consents)
        )
        
    except Exception as e:
        logger.error("get_expiring_consents_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve expiring consents"
        )


@router.post("/template/generate", response_model=dict)
async def generate_consent_template(
    request: ConsentTemplateRequest,
    req: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a consent form from template
    
    **Requires:** `consent_read` permission
    
    Fills in template with patient-specific data
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.CONSENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'consent_read' required"
        )
    
    try:
        consent_manager = get_consent_manager()
        
        # Convert category
        category = ConsentCategory(request.category)
        
        # Generate form
        form_content = consent_manager.generate_consent_form(
            category=category,
            patient_data=request.patient_data
        )
        
        return {
            "category": request.category,
            "content": form_content
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("generate_template_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate consent form"
        )


@router.get("/templates", response_model=List[dict])
async def list_consent_templates(
    current_user: User = Depends(get_current_active_user)
):
    """
    List available consent templates
    
    **Requires:** `consent_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.CONSENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'consent_read' required"
        )
    
    # Return template info (not full content)
    templates = []
    for category in ConsentCategory:
        if category in ConsentManager.DEFAULT_TEMPLATES:
            template = ConsentManager.DEFAULT_TEMPLATES[category]
            templates.append({
                "category": category.value,
                "name": template["name"],
                "description": template["description"],
                "required_fields": template["required_fields"],
                "expiration_days": template.get("expiration_days")
            })
    
    return templates