"""
Cortex Medical Coding API Endpoints

FastAPI endpoints for medical coding:
- Search ICD-10 codes
- Search CPT codes
- Code validation
- Code mapping
- Code suggestions
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, validator
import structlog

from cortex.security.auth import get_current_active_user
from cortex.security.rbac import Permission, get_user_permissions
from cortex.models import User
from cortex.medical_coding import (
    MedicalCoder, CodeType, ICD10Chapter, CPTSection,
    get_medical_coder
)
from cortex.audit import log_audit, AuditAction

logger = structlog.get_logger()

router = APIRouter(prefix="/coding", tags=["Medical Coding"])


# === Helper Functions ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# === Pydantic Models ===

class ICD10SearchResponse(BaseModel):
    """ICD-10 search response"""
    code: str
    description: str
    category: Optional[str] = None
    chapter: Optional[str] = None
    is_billable: bool
    synonyms: List[str] = []
    
    class Config:
        from_attributes = True


class CPTSearchResponse(BaseModel):
    """CPT search response"""
    code: str
    description: str
    category: Optional[str] = None
    section: Optional[str] = None
    is_active: bool
    work_rvu: Optional[int] = None
    
    class Config:
        from_attributes = True


class CodeMappingResponse(BaseModel):
    """Code mapping response"""
    icd10_code: str
    cpt_code: str
    confidence: int
    
    class Config:
        from_attributes = True


class CodeMappingRequest(BaseModel):
    """Create code mapping request"""
    icd10_code: str
    cpt_code: str
    confidence: Optional[int] = 80
    
    @validator('confidence')
    def validate_confidence(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Confidence must be between 0 and 100')
        return v


class CodeSuggestionResponse(BaseModel):
    """Code suggestion response"""
    code: str
    description: str
    relevance_score: float
    code_type: str


class StatisticsResponse(BaseModel):
    """Code statistics response"""
    icd10_total: int
    cpt_total: int
    mappings_total: int
    icd10_by_chapter: dict
    cpt_by_section: dict


# === ICD-10 Endpoints ===

@router.get("/icd10/search", response_model=List[ICD10SearchResponse])
async def search_icd10_codes(
    request: Request,
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    category: Optional[str] = Query(None, description="Filter by category"),
    chapter: Optional[str] = Query(None, description="Filter by chapter"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search ICD-10 diagnosis codes
    
    **Requires:** `patient_read` permission
    
    **Usage:** Search by code or description
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        results = coder.search_icd10(
            query=query,
            limit=limit,
            category=category,
            chapter=chapter
        )
        
        # Audit log
        log_audit(
            action=AuditAction.AGENT_QUERY,
            user_id=current_user.id,
            resource_type="icd10_code",
            ip_address=get_client_ip(request),
            details={
                "action": "search_icd10",
                "query": query,
                "results_count": len(results)
            }
        )
        
        return [ICD10SearchResponse(**r) for r in results]
        
    except Exception as e:
        logger.error("icd10_search_error", error=str(e), query=query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search ICD-10 codes"
        )


@router.get("/icd10/{code}", response_model=ICD10SearchResponse)
async def get_icd10_code(
    code: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get specific ICD-10 code
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        result = coder.get_icd10(code)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ICD-10 code '{code}' not found"
            )
        
        return ICD10SearchResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_icd10_error", error=str(e), code=code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ICD-10 code"
        )


@router.get("/icd10/{code}/hierarchy", response_model=List[ICD10SearchResponse])
async def get_icd10_hierarchy(
    code: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get ICD-10 code hierarchy (parent codes)
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        hierarchy = coder.get_icd10_hierarchy(code)
        
        return [ICD10SearchResponse(**h) for h in hierarchy]
        
    except Exception as e:
        logger.error("icd10_hierarchy_error", error=str(e), code=code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ICD-10 hierarchy"
        )


@router.get("/icd10/{code}/validate")
async def validate_icd10_code(
    code: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Validate ICD-10 code format and existence
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        is_valid = coder.validate_icd10(code)
        
        return {
            "code": code,
            "code_type": "icd10",
            "is_valid": is_valid
        }
        
    except Exception as e:
        logger.error("validate_icd10_error", error=str(e), code=code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate ICD-10 code"
        )


# === CPT Endpoints ===

@router.get("/cpt/search", response_model=List[CPTSearchResponse])
async def search_cpt_codes(
    request: Request,
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    section: Optional[str] = Query(None, description="Filter by section"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search CPT procedure codes
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        results = coder.search_cpt(
            query=query,
            limit=limit,
            section=section
        )
        
        # Audit log
        log_audit(
            action=AuditAction.AGENT_QUERY,
            user_id=current_user.id,
            resource_type="cpt_code",
            ip_address=get_client_ip(request),
            details={
                "action": "search_cpt",
                "query": query,
                "results_count": len(results)
            }
        )
        
        return [CPTSearchResponse(**r) for r in results]
        
    except Exception as e:
        logger.error("cpt_search_error", error=str(e), query=query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search CPT codes"
        )


@router.get("/cpt/{code}", response_model=CPTSearchResponse)
async def get_cpt_code(
    code: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get specific CPT code
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        result = coder.get_cpt(code)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CPT code '{code}' not found"
            )
        
        return CPTSearchResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_cpt_error", error=str(e), code=code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve CPT code"
        )


@router.get("/cpt/{code}/validate")
async def validate_cpt_code(
    code: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Validate CPT code format and existence
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        is_valid = coder.validate_cpt(code)
        
        return {
            "code": code,
            "code_type": "cpt",
            "is_valid": is_valid
        }
        
    except Exception as e:
        logger.error("validate_cpt_error", error=str(e), code=code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate CPT code"
        )


# === Code Mapping Endpoints ===

@router.get("/mapping/icd10/{icd10_code}", response_model=List[dict])
async def map_icd10_to_cpt(
    icd10_code: str,
    request: Request,
    min_confidence: int = Query(70, ge=0, le=100, description="Minimum confidence"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get CPT codes commonly used with ICD-10 code
    
    **Requires:** `patient_read` permission
    
    **Usage:** Medical billing and procedure matching
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        mappings = coder.map_icd10_to_cpt(
            icd10_code=icd10_code,
            min_confidence=min_confidence
        )
        
        return mappings
        
    except Exception as e:
        logger.error("map_icd10_error", error=str(e), icd10_code=icd10_code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to map ICD-10 to CPT codes"
        )


@router.get("/mapping/cpt/{cpt_code}", response_model=List[dict])
async def map_cpt_to_icd10(
    cpt_code: str,
    request: Request,
    min_confidence: int = Query(70, ge=0, le=100, description="Minimum confidence"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get ICD-10 codes commonly used with CPT code
    
    **Requires:** `patient_read` permission
    
    **Usage:** Medical billing and diagnosis matching
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        mappings = coder.map_cpt_to_icd10(
            cpt_code=cpt_code,
            min_confidence=min_confidence
        )
        
        return mappings
        
    except Exception as e:
        logger.error("map_cpt_error", error=str(e), cpt_code=cpt_code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to map CPT to ICD-10 codes"
        )


@router.post("/mapping", status_code=status.HTTP_201_CREATED)
async def create_code_mapping(
    request: Request,
    mapping: CodeMappingRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create ICD-10 to CPT code mapping
    
    **Requires:** `admin` permission
    
    **Usage:** Medical coders can add new mappings
    """
    # Check permission - only admins can create mappings
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    
    try:
        coder = get_medical_coder()
        
        mapping_id = coder.create_mapping(
            icd10_code=mapping.icd10_code,
            cpt_code=mapping.cpt_code,
            confidence=mapping.confidence
        )
        
        if not mapping_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code(s) or mapping already exists"
            )
        
        # Audit log
        log_audit(
            action=AuditAction.AGENT_RESPONSE,
            user_id=current_user.id,
            resource_type="code_mapping",
            resource_id=mapping_id,
            ip_address=get_client_ip(request),
            details={
                "icd10_code": mapping.icd10_code,
                "cpt_code": mapping.cpt_code,
                "confidence": mapping.confidence
            }
        )
        
        return {
            "mapping_id": str(mapping_id),
            "icd10_code": mapping.icd10_code,
            "cpt_code": mapping.cpt_code,
            "confidence": mapping.confidence
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_mapping_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create code mapping"
        )


# === Suggestion Endpoints ===

@router.post("/suggest", response_model=List[CodeSuggestionResponse])
async def suggest_codes(
    request: Request,
    text: str = Query(..., min_length=10, description="Clinical text"),
    code_type: CodeType = Query(CodeType.ICD10, description="Code type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Suggest codes based on clinical text
    
    **Requires:** `patient_read` permission
    
    **Usage:** AI-assisted medical coding
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        suggestions = coder.suggest_codes(
            text=text,
            code_type=code_type,
            limit=limit
        )
        
        # Audit log
        log_audit(
            action=AuditAction.AGENT_QUERY,
            user_id=current_user.id,
            resource_type="code_suggestion",
            ip_address=get_client_ip(request),
            details={
                "code_type": code_type.value,
                "text_length": len(text),
                "results_count": len(suggestions)
            }
        )
        
        return [
            CodeSuggestionResponse(
                code=s["code"],
                description=s["description"],
                relevance_score=s["relevance_score"],
                code_type=code_type.value
            )
            for s in suggestions
        ]
        
    except Exception as e:
        logger.error("suggest_codes_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suggest codes"
        )


# === Statistics Endpoints ===

@router.get("/statistics", response_model=StatisticsResponse)
async def get_code_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get medical code statistics
    
    **Requires:** `audit_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.AUDIT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'audit_read' required"
        )
    
    try:
        coder = get_medical_coder()
        
        stats = coder.get_code_statistics()
        
        return StatisticsResponse(**stats)
        
    except Exception as e:
        logger.error("statistics_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


# === Reference Endpoints ===

@router.get("/chapters", response_model=List[dict])
async def list_icd10_chapters(
    current_user: User = Depends(get_current_active_user)
):
    """
    List ICD-10 chapters
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    return [
        {"code": "A00-B99", "name": "Certain infectious and parasitic diseases"},
        {"code": "C00-D49", "name": "Neoplasms"},
        {"code": "D50-D89", "name": "Diseases of the blood and blood-forming organs"},
        {"code": "E00-E89", "name": "Endocrine, nutritional and metabolic diseases"},
        {"code": "F01-F99", "name": "Mental and behavioral disorders"},
        {"code": "G00-G99", "name": "Diseases of the nervous system"},
        {"code": "H00-H59", "name": "Diseases of the eye and adnexa"},
        {"code": "H60-H95", "name": "Diseases of the ear and mastoid process"},
        {"code": "I00-I99", "name": "Diseases of the circulatory system"},
        {"code": "J00-J99", "name": "Diseases of the respiratory system"},
        {"code": "K00-K95", "name": "Diseases of the digestive system"},
        {"code": "L00-L99", "name": "Diseases of the skin and subcutaneous tissue"},
        {"code": "M00-M99", "name": "Diseases of the musculoskeletal system"},
        {"code": "N00-N99", "name": "Diseases of the genitourinary system"},
        {"code": "O00-O9A", "name": "Pregnancy, childbirth and the puerperium"},
        {"code": "P00-P96", "name": "Certain conditions originating in perinatal period"},
        {"code": "Q00-Q99", "name": "Congenital malformations"},
        {"code": "R00-R99", "name": "Symptoms, signs and abnormal clinical findings"},
        {"code": "S00-T88", "name": "Injury, poisoning and certain other consequences"},
        {"code": "V00-Y99", "name": "External causes of morbidity"},
        {"code": "Z00-Z99", "name": "Factors influencing health status"},
        {"code": "U00-U99", "name": "Codes for special purposes"},
    ]


@router.get("/sections", response_model=List[dict])
async def list_cpt_sections(
    current_user: User = Depends(get_current_active_user)
):
    """
    List CPT sections
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    return [
        {"code_range": "99201-99499", "name": "Evaluation and Management"},
        {"code_range": "00100-01999", "name": "Anesthesia"},
        {"code_range": "10021-69990", "name": "Surgery"},
        {"code_range": "70010-79999", "name": "Radiology"},
        {"code_range": "80047-89398", "name": "Pathology and Laboratory"},
        {"code_range": "90281-99607", "name": "Medicine"},
    ]