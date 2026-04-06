"""
Cortex Document API Endpoints

FastAPI endpoints for document management:
- Upload documents
- Download documents
- Update documents (versioning)
- Delete documents
- Query documents
- Version history
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
import structlog

from cortex.security.auth import get_current_active_user
from cortex.security.rbac import Permission, get_user_permissions
from cortex.models import User, UserRole, DocumentType, DocumentStatus
from cortex.documents import (
    DocumentManager, DocumentType as DocType, DocumentStatus as DocStatus,
    get_document_manager
)
from cortex.audit import log_audit, AuditAction

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["Document Management"])


# === Helper Functions ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def map_document_status(status: str) -> DocumentStatus:
    """Map document status string to enum"""
    status_map = {
        "active": DocumentStatus.ACTIVE,
        "archived": DocumentStatus.ARCHIVED,
        "deleted": DocumentStatus.DELETED,
        "pending_review": DocumentStatus.PENDING_REVIEW,
        "retention_hold": DocumentStatus.RETENTION_HOLD,
    }
    return status_map.get(status.lower(), DocumentStatus.ACTIVE)


# === Pydantic Models ===

class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    id: str
    patient_id: str
    document_type: str
    title: str
    filename: str
    file_size: int
    version: int
    status: str
    created_at: str
    
    class Config:
        from_attributes = True


class DocumentMetadataResponse(BaseModel):
    """Document metadata response"""
    id: str
    patient_id: str
    document_type: str
    title: str
    description: Optional[str] = None
    filename: str
    file_type: str
    file_size: int
    checksum: str
    current_version: int
    status: str
    uploaded_by: str
    created_at: str
    updated_at: Optional[str] = None
    retention_until: Optional[str] = None
    tags: Optional[List[str]] = None
    consent_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class DocumentUpdateRequest(BaseModel):
    """Document update request"""
    notes: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Document list response"""
    documents: List[dict]
    total: int


class DocumentVersionResponse(BaseModel):
    """Document version response"""
    versions: List[dict]
    total: int


# === Endpoints ===

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    document_type: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    consent_id: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a new document
    
    **Requires:** `patient_write` permission
    
    **HIPAA:** Documents encrypted at rest, consent verified
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_WRITE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_write' required"
        )
    
    try:
        document_manager = get_document_manager()
        
        # Convert types
        patient_uuid = UUID(patient_id)
        doc_type = DocType(document_type.lower())
        consent_uuid = UUID(consent_id) if consent_id else None
        
        # Parse tags
        tag_list = tags.split(",") if tags else None
        tag_list = [t.strip() for t in tag_list] if tag_list else None
        
        # Upload document
        document_id = document_manager.upload_document(
            patient_id=patient_uuid,
            file_data=file.file,
            filename=file.filename,
            document_type=doc_type,
            title=title,
            description=description,
            uploaded_by=current_user.id,
            requires_consent=True,
            consent_id=consent_uuid,
            tags=tag_list
        )
        
        if not document_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document"
            )
        
        # Get metadata
        metadata = document_manager.get_document_metadata(document_id)
        
        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_CREATE,
            user_id=current_user.id,
            patient_id=patient_uuid,
            resource_type="document",
            resource_id=document_id,
            ip_address=get_client_ip(request),
            details={
                "filename": file.filename,
                "document_type": document_type,
                "file_size": metadata.get("file_size", 0) if metadata else 0
            }
        )
        
        return DocumentUploadResponse(
            id=str(document_id),
            patient_id=patient_id,
            document_type=document_type,
            title=title,
            filename=file.filename,
            file_size=metadata.get("file_size", 0) if metadata else 0,
            version=1,
            status="active",
            created_at=datetime.utcnow().isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("upload_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
async def get_document_metadata(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get document metadata
    
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
        document_manager = get_document_manager()
        
        document_uuid = UUID(document_id)
        metadata = document_manager.get_document_metadata(document_uuid)
        
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_READ,
            user_id=current_user.id,
            patient_id=UUID(metadata["patient_id"]),
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request)
        )
        
        return DocumentMetadataResponse(**metadata)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    request: Request,
    version: Optional[int] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Download document content
    
    **Requires:** `patient_read` permission
    
    **HIPAA:** All downloads logged in audit trail
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    try:
        document_manager = get_document_manager()
        
        document_uuid = UUID(document_id)
        
        # Download document
        result = document_manager.download_document(
            document_id=document_uuid,
            user=current_user.id,
            version=version
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        content, filename, mime_type = result
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(content),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content))
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


@router.get("/patient/{patient_id}", response_model=DocumentListResponse)
async def get_patient_documents(
    patient_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Get all documents for a patient
    
    **Requires:** `phi_access` permission
    
    **HIPAA:** Logs PHI access
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PHI_ACCESS not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'phi_access' required"
        )
    
    try:
        document_manager = get_document_manager()
        
        patient_uuid = UUID(patient_id)
        
        # Convert filters
        doc_type = DocType(document_type.lower()) if document_type else None
        doc_status = map_document_status(status) if status else None
        
        documents = document_manager.get_patient_documents(
            patient_id=patient_uuid,
            document_type=doc_type,
            status=doc_status,
            limit=limit
        )
        
        # Audit log
        log_audit(
            action=AuditAction.PHI_ACCESS,
            user_id=current_user.id,
            patient_id=patient_uuid,
            resource_type="document",
            ip_address=get_client_ip(request),
            details={
                "action": "list_documents",
                "count": len(documents)
            }
        )
        
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("get_patient_documents_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.put("/{document_id}", response_model=dict)
async def update_document(
    document_id: str,
    request: Request,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update document (create new version)
    
    **Requires:** `patient_write` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_WRITE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_write' required"
        )
    
    try:
        document_manager = get_document_manager()
        
        document_uuid = UUID(document_id)
        
        # Update document
        new_version = document_manager.update_document(
            document_id=document_uuid,
            file_data=file.file,
            filename=file.filename,
            updated_by=current_user.id,
            notes=notes
        )
        
        if not new_version:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document"
            )
        
        # Get metadata for audit
        metadata = document_manager.get_document_metadata(document_uuid)
        
        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_UPDATE,
            user_id=current_user.id,
            patient_id=UUID(metadata["patient_id"]) if metadata else None,
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
            details={
                "version": new_version,
                "notes": notes
            }
        )
        
        return {
            "message": "Document updated successfully",
            "document_id": document_id,
            "version": new_version
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("update_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Soft delete a document
    
    **Requires:** `patient_delete` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_DELETE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_delete' required"
        )
    
    try:
        document_manager = get_document_manager()
        
        document_uuid = UUID(document_id)
        
        # Get metadata before deletion
        metadata = document_manager.get_document_metadata(document_uuid)
        
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Delete document
        success = document_manager.delete_document(
            document_id=document_uuid,
            deleted_by=current_user.id,
            reason=reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document"
            )
        
        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_DELETE,
            user_id=current_user.id,
            patient_id=UUID(metadata["patient_id"]),
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
            details={
                "reason": reason
            }
        )
        
        return {
            "message": "Document deleted successfully",
            "document_id": document_id
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get("/{document_id}/versions", response_model=DocumentVersionResponse)
async def get_document_versions(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get version history for a document
    
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
        document_manager = get_document_manager()
        
        document_uuid = UUID(document_id)
        versions = document_manager.get_document_versions(document_uuid)
        
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentVersionResponse(
            versions=versions,
            total=len(versions)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("get_versions_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve versions"
        )


@router.get("/types", response_model=List[dict])
async def list_document_types(
    current_user: User = Depends(get_current_active_user)
):
    """
    List available document types
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    types = [
        {"type": "medical_record", "description": "Medical records", "retention_days": 2555},
        {"type": "lab_result", "description": "Laboratory results", "retention_days": 2555},
        {"type": "imaging", "description": "Medical imaging (DICOM)", "retention_days": 2555},
        {"type": "consent_form", "description": "Patient consent forms", "retention_days": 2190},
        {"type": "insurance", "description": "Insurance documents", "retention_days": 2555},
        {"type": "referral", "description": "Referral documents", "retention_days": 2555},
        {"type": "clinical_note", "description": "Clinical notes", "retention_days": 2555},
        {"type": "discharge_summary", "description": "Discharge summaries", "retention_days": 2555},
        {"type": "other", "description": "Other documents", "retention_days": 1825},
    ]
    
    return types


@router.get("/statuses", response_model=List[dict])
async def list_document_statuses(
    current_user: User = Depends(get_current_active_user)
):
    """
    List available document statuses
    
    **Requires:** `patient_read` permission
    """
    # Check permission
    user_permissions = get_user_permissions(current_user)
    if Permission.PATIENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'patient_read' required"
        )
    
    statuses = [
        {"status": "active", "description": "Active document"},
        {"status": "archived", "description": "Archived document"},
        {"status": "deleted", "description": "Deleted document"},
        {"status": "pending_review", "description": "Pending review"},
        {"status": "retention_hold", "description": "On retention hold"},
    ]
    
    return statuses