"""
Cortex Document API Endpoints - Railway Safety Compliance

EN 50128 Class B compliant document management:
- Upload/download/version railway compliance documents
- Asset traceability
- Retention policy enforcement
- SHA-256 integrity verification
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog

from cortex.security.auth import get_current_active_user
from cortex.security.rbac import Permission, get_user_permissions
from cortex.models import User, UserRole, DocumentType, DocumentStatus
from cortex.documents import DocumentManager
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


# === Pydantic Models ===

class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    id: str
    asset_id: Optional[str] = None
    document_type: str
    title: str
    filename: str
    file_size: int
    version: int
    status: str
    created_at: str


class DocumentMetadataResponse(BaseModel):
    """Document metadata response"""
    id: str
    asset_id: Optional[str] = None
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

    class Config:
        from_attributes = True


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
    asset_id: Optional[str] = Form(None),
    document_type: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload a new railway compliance document.

    **Requires:** `document_write` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_WRITE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_write' required",
        )

    try:
        document_manager = DocumentManager()

        doc_type = DocumentType(document_type.lower())
        asset_uuid = UUID(asset_id) if asset_id else None
        tag_list = [t.strip() for t in tags.split(",")] if tags else None

        document_id = document_manager.upload_document(
            file_data=file.file,
            filename=file.filename,
            document_type=doc_type,
            title=title,
            description=description,
            asset_id=asset_uuid,
            uploaded_by=current_user.id,
            tags=tag_list,
        )

        if not document_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document",
            )

        # Get metadata
        metadata = document_manager.get_document(document_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document uploaded but failed to retrieve metadata",
            )

        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_CREATE,
            user_id=current_user.id,
            asset_id=asset_uuid,
            resource_type="document",
            resource_id=document_id,
            ip_address=get_client_ip(request),
            details={
                "filename": file.filename,
                "document_type": document_type,
                "file_size": metadata.file_size,
                "checksum": metadata.checksum,
            }
        )

        return DocumentUploadResponse(
            id=str(document_id),
            asset_id=asset_id,
            document_type=document_type,
            title=title,
            filename=file.filename,
            file_size=metadata.file_size,
            version=1,
            status="active",
            created_at=metadata.created_at.isoformat(),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("upload_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
async def get_document_metadata(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get document metadata.

    **Requires:** `document_read` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_read' required",
        )

    try:
        document_manager = DocumentManager()
        document_uuid = UUID(document_id)
        document = document_manager.get_document(document_uuid)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_READ,
            user_id=current_user.id,
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
        )

        return DocumentMetadataResponse(
            id=str(document.id),
            asset_id=str(document.asset_id) if document.asset_id else None,
            document_type=document.document_type,
            title=document.title,
            description=document.description,
            filename=document.original_filename,
            file_type=document.file_type,
            file_size=document.file_size,
            checksum=document.checksum,
            current_version=document.current_version,
            status=document.status,
            uploaded_by=str(document.uploaded_by) if document.uploaded_by else None,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat() if document.updated_at else None,
            retention_until=document.retention_until.isoformat() if document.retention_until else None,
            tags=document.tags,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document",
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    request: Request,
    version: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    Download document content with integrity verification.

    **Requires:** `document_read` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_read' required",
        )

    try:
        document_manager = DocumentManager()
        document_uuid = UUID(document_id)

        result = document_manager.download_document(
            document_id=document_uuid,
            user=current_user.id,
            version=version,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or integrity check failed",
            )

        content, filename, mime_type = result

        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_READ,
            user_id=current_user.id,
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
            details={
                "filename": filename,
                "version": version,
                "integrity_verified": True,
            }
        )

        return StreamingResponse(
            BytesIO(content),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
                "X-Content-Checksum": document_manager._generate_checksum(content),
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document",
        )


@router.put("/{document_id}", response_model=dict)
async def update_document(
    document_id: str,
    request: Request,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update document (creates new version).

    **Requires:** `document_write` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_WRITE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_write' required",
        )

    try:
        document_manager = DocumentManager()
        document_uuid = UUID(document_id)

        new_version = document_manager.update_document(
            document_id=document_uuid,
            file_data=file.file,
            filename=file.filename,
            updated_by=current_user.id,
            notes=notes,
        )

        if not new_version:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document",
            )

        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_UPDATE,
            user_id=current_user.id,
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
            details={
                "version": new_version,
                "filename": file.filename,
            }
        )

        return {
            "message": "Document updated successfully",
            "document_id": document_id,
            "version": new_version,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("update_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document",
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    Soft-delete a document (retention hold — EN 50128).

    Documents are not physically deleted; they are marked as deleted
    and placed under retention hold per the EN 50128 retention policy.

    **Requires:** `document_delete` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_DELETE not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_delete' required",
        )

    try:
        document_manager = DocumentManager()
        document_uuid = UUID(document_id)

        success = document_manager.delete_document(
            document_id=document_uuid,
            deleted_by=current_user.id,
            reason=reason,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        # Audit log
        log_audit(
            action=AuditAction.DOCUMENT_DELETE,
            user_id=current_user.id,
            resource_type="document",
            resource_id=document_uuid,
            ip_address=get_client_ip(request),
            details={"reason": reason},
        )

        return {"message": "Document deleted successfully", "document_id": document_id}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("delete_document_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    asset_id: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List documents with filtering and pagination.

    **Requires:** `document_read` permission
    """
    user_permissions = get_user_permissions(current_user)
    if Permission.DOCUMENT_READ not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'document_read' required",
        )

    try:
        document_manager = DocumentManager()

        asset_uuid = UUID(asset_id) if asset_id else None
        doc_type = DocumentType(document_type.lower()) if document_type else None
        doc_status = DocumentStatus(status.lower()) if status else None

        documents, total = document_manager.list_documents(
            asset_id=asset_uuid,
            document_type=doc_type,
            status=doc_status,
            limit=limit,
            offset=offset,
        )

        return DocumentListResponse(
            documents=[
                {
                    "id": str(doc.id),
                    "asset_id": str(doc.asset_id) if doc.asset_id else None,
                    "document_type": doc.document_type,
                    "title": doc.title,
                    "filename": doc.original_filename,
                    "file_size": doc.file_size,
                    "current_version": doc.current_version,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                }
                for doc in documents
            ],
            total=total,
        )

    except Exception as e:
        logger.error("list_documents_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        )
