"""
Cortex Knowledge Base API - Railway Safety Knowledge Management

EN 50128 / EN 50716 compliance knowledge base:
- Searchable repository of railway standards, regulations, and best practices
- Linked to requirements via traceability tags
- Supports knowledge injection from standards documents
- Tag-based filtering and full-text search
"""

from datetime import datetime, UTC
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, KnowledgeArticle
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


class ArticleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=50)
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    references: Optional[List[str]] = None


class ArticleUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    references: Optional[List[str]] = None
    status: Optional[str] = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: Optional[List[str]]
    status: str
    source: Optional[str]
    references: Optional[List[str]]
    created_by: str
    approved_by: Optional[str]
    approved_at: Optional[str]
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


def _to_response(a: KnowledgeArticle) -> ArticleResponse:
    return ArticleResponse(
        id=str(a.id),
        title=a.title,
        content=a.content,
        category=a.category,
        tags=a.tags,
        status=a.status,
        source=a.source,
        references=a.references,
        created_by=str(a.created_by),
        approved_by=str(a.approved_by) if a.approved_by else None,
        approved_at=a.approved_at.isoformat() if a.approved_at else None,
        created_at=a.created_at.isoformat() if a.created_at else None,
        updated_at=a.updated_at.isoformat() if a.updated_at else None,
    )


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


@router.post("/articles", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    req: ArticleCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        article = KnowledgeArticle(
            title=req.title,
            content=req.content,
            category=req.category,
            tags=req.tags,
            source=req.source,
            references=req.references,
            status="published",
            created_by=current_user.id,
        )
        session.add(article)
        session.commit()
        session.refresh(article)
        response = _to_response(article)

    log_audit(
        action="knowledge_article_created",
        user_id=current_user.id,
        resource_type="knowledge_article",
        resource_id=response.id,
        ip_address=get_client_ip(request),
        details={"title": req.title, "category": req.category},
    )
    return response


@router.get("/articles", response_model=List[ArticleResponse])
async def list_articles(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    search: Optional[str] = Query(default=None, description="Search title and content"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(KnowledgeArticle)

        if search:
            like = f"%{search}%"
            query = query.filter(
                (KnowledgeArticle.title.ilike(like)) |
                (KnowledgeArticle.content.ilike(like))
            )
        if category:
            query = query.filter(KnowledgeArticle.category == category)
        if tag:
            query = query.filter(KnowledgeArticle.tags.contains([tag]))
        if status_filter:
            query = query.filter(KnowledgeArticle.status == status_filter)

        total = query.count()
        results = query.order_by(KnowledgeArticle.created_at.desc()).offset(offset).limit(limit).all()
        response = [_to_response(r) for r in results]

    return response


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        article = session.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        response = _to_response(article)
    return response


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: str,
    update: ArticleUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        article = session.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        if update.title is not None:
            article.title = update.title
        if update.content is not None:
            article.content = update.content
        if update.category is not None:
            article.category = update.category
        if update.tags is not None:
            article.tags = update.tags
        if update.source is not None:
            article.source = update.source
        if update.references is not None:
            article.references = update.references
        if update.status is not None:
            article.status = update.status

        session.commit()
        session.refresh(article)
        response = _to_response(article)

    log_audit(
        action="knowledge_article_updated",
        user_id=current_user.id,
        resource_type="knowledge_article",
        resource_id=article_id,
        ip_address=get_client_ip(request),
    )
    return response


@router.delete("/articles/{article_id}", status_code=status.HTTP_200_OK)
async def delete_article(
    article_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        article = session.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        session.delete(article)
        session.commit()

    log_audit(
        action="knowledge_article_deleted",
        user_id=current_user.id,
        resource_type="knowledge_article",
        resource_id=article_id,
        ip_address=get_client_ip(request),
    )
    return {"message": "Article deleted", "article_id": article_id}


@router.get("/categories", response_model=List[str])
async def list_categories(
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        results = session.query(KnowledgeArticle.category).distinct().all()
        categories = [r[0] for r in results]
    return categories


@router.get("/search", response_model=List[ArticleResponse])
async def search_articles(
    q: str = Query(..., min_length=1, description="Search query"),
    current_user: User = Depends(get_current_active_user_from_request),
    limit: int = Query(default=20, le=100),
):
    require_permission(current_user, Permission.REQUIREMENT_READ)

    db = get_database_manager()
    with db.get_session() as session:
        like = f"%{q}%"
        results = session.query(KnowledgeArticle).filter(
            (KnowledgeArticle.title.ilike(like)) |
            (KnowledgeArticle.content.ilike(like))
        ).order_by(KnowledgeArticle.created_at.desc()).limit(limit).all()
        response = [_to_response(r) for r in results]
    return response
