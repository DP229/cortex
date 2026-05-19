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
import os
import json as _json

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import (
    User, Requirement, RequirementCitation,
    RequirementPriority, RequirementStatus, VerificationStatus,
    SafetyClass, SILLevel, RequirementType,
)
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/requirements", tags=["Requirements Management"])

REQUIREMENT_TYPES = [rt.value for rt in RequirementType]


# === Pydantic Models ===

class RequirementCreateRequest(BaseModel):
    """Create an INCOSE-compliant requirement (EN 50128)"""
    requirement_id: str = Field(..., description="Unique requirement ID, e.g. REQ-SIG-001")
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., description="Full requirement text (SHALL statement)")
    rationale: Optional[str] = Field(default=None, description="INCOSE — why this requirement exists")
    requirement_type: Optional[str] = Field(default=None, description=f"INCOSE type: {', '.join(REQUIREMENT_TYPES)}")
    priority: str = Field(default=RequirementPriority.SHALL.value)
    safety_class: str = Field(default=SafetyClass.CLASS_B.value)
    sil_level: str = Field(default=SILLevel.SIL2.value)
    category: Optional[str] = Field(default=None, description="functional, safety, security, performance")
    source: Optional[str] = Field(default=None, description="INCOSE — origin: stakeholder, regulation clause, derived-from")
    compliance_ref: Optional[str] = Field(default=None, description="Formal standard clause ref, e.g. EN 50128 §5.2.3")
    stakeholder: Optional[str] = Field(default=None, description="INCOSE — who needs this requirement")
    acceptance_criteria: Optional[str] = Field(default=None, description="INCOSE — pass/fail conditions")
    allocation: Optional[str] = Field(default=None, description="INCOSE — subsystem/component allocation")
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
    rationale: Optional[str] = None
    requirement_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    safety_class: Optional[str] = None
    sil_level: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    compliance_ref: Optional[str] = None
    stakeholder: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    allocation: Optional[str] = None
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


class RequirementResponse(BaseModel):
    id: str
    requirement_id: str
    title: str
    description: str
    rationale: Optional[str] = None
    requirement_type: Optional[str] = None
    priority: str
    status: str
    safety_class: str
    sil_level: str
    category: Optional[str]
    source: Optional[str] = None
    compliance_ref: Optional[str] = None
    stakeholder: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    allocation: Optional[str] = None
    version: int = 1
    change_history: Optional[List[dict]] = None
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
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    citations: Optional[List[CitationResponse]] = None

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


def _requirement_to_response(req: Requirement, citations: Optional[List[RequirementCitation]] = None) -> RequirementResponse:
    return RequirementResponse(
        id=str(req.id),
        requirement_id=str(req.requirement_id),
        title=req.title,
        description=req.description,
        rationale=req.rationale,
        requirement_type=req.requirement_type,
        priority=req.priority,
        status=req.status,
        safety_class=req.safety_class,
        sil_level=req.sil_level,
        category=req.category,
        source=req.source,
        compliance_ref=req.compliance_ref,
        stakeholder=req.stakeholder,
        acceptance_criteria=req.acceptance_criteria,
        allocation=req.allocation,
        version=req.version or 1,
        change_history=req.change_history,
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
        approved_at=req.approved_at.isoformat() if req.approved_at else None,
        approved_by=str(req.approved_by) if req.approved_by else None,
        citations=[_citation_to_response(c) for c in citations] if citations else None,
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
            rationale=req.rationale,
            requirement_type=req.requirement_type,
            priority=req.priority,
            status=RequirementStatus.DRAFT.value,
            safety_class=req.safety_class,
            sil_level=req.sil_level,
            category=req.category,
            source=req.source,
            compliance_ref=req.compliance_ref,
            stakeholder=req.stakeholder,
            acceptance_criteria=req.acceptance_criteria,
            allocation=req.allocation,
            version=1,
            change_history=[],
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
        response = _requirement_to_response(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_CREATE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=response.id,
        ip_address=get_client_ip(request),
        details={
            "requirement_id": req.requirement_id,
            "safety_class": req.safety_class,
            "sil_level": req.sil_level,
        },
    )

    return response


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
        req_ids = [r.id for r in results]
        citations_by_req = {}
        if req_ids:
            all_citations = session.query(RequirementCitation).filter(
                RequirementCitation.source_requirement_id.in_(req_ids)
            ).all()
            for c in all_citations:
                key = str(c.source_requirement_id)
                if key not in citations_by_req:
                    citations_by_req[key] = []
                citations_by_req[key].append(c)
        response = [_requirement_to_response(r, citations_by_req.get(str(r.id))) for r in results]

    return response
# === Import / LLM Extraction ===

class BatchImportRequest(BaseModel):
    items: List[dict]


class BatchImportSaveRequest(BaseModel):
    items: List[dict]


class ImportPreviewResponse(BaseModel):
    requirements: List[dict]
    source_document: Optional[str] = None


def _parse_document_text(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("md", "txt", "json", "yaml", "yml", "csv", "xml"):
        return content.decode("utf-8", errors="replace")
    if ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(content)) as pdf:
                return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            pass
    if ext in ("docx", "doc"):
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(_io.BytesIO(content))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            pass
    if ext in ("html", "htm"):
        try:
            import trafilatura
            text = trafilatura.extract(content.decode("utf-8", errors="replace"))
            if text:
                return text
        except ImportError:
            pass
    return content.decode("utf-8", errors="replace")


def _call_llm_for_extraction(text: str, kb_context: str = "") -> List[dict]:
    try:
        from cortex.brain import Brain, ModelProvider
        model = os.getenv("LLM_MODEL", "llama3")
        provider = os.getenv("LLM_PROVIDER", "ollama")
        brain = Brain(model=model, provider=ModelProvider(provider) if provider else ModelProvider.OLLAMA)

        kb_section = ""
        if kb_context:
            kb_section = f"\n\nProduct Knowledge Base context (domain, standards, concepts):\n{kb_context[:4000]}"

        prompt = f"""Extract ALL requirements from the following document as structured JSON.

Return ONLY a JSON array of requirement objects. Each object must have these fields:
- requirement_id: unique ID like "REQ-001", "REQ-002" etc
- title: short descriptive title
- description: the full requirement text as a SHALL statement
- rationale: why this requirement exists (if implied in text)
- requirement_type: one of [functional, performance, interface, design_constraint, security, safety, usability, maintainability, regulatory, environmental, other]
- priority: shall (mandatory), must (safety-critical), should (recommended), may (optional)
- source: where this requirement originated (stakeholder, regulation, derived-from)
- acceptance_criteria: how to verify this requirement is met (if implied)

INCOSE-style: Every requirement must be a clear SHALL/MUST statement. Derive rationale and acceptance criteria from the context.
{kb_section}

Document text:
{text[:8000]}

Requirements JSON array:"""

        result, _ = brain.generate(prompt, temperature=0.3, max_tokens=4096)
        json_str = result.strip()
        if "```" in json_str:
            parts = json_str.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    json_str = p[4:].strip()
                    break
                elif p.startswith("["):
                    json_str = p
                    break
        if "[" in json_str:
            json_str = json_str[json_str.index("["):]
            if "]" in json_str:
                json_str = json_str[:json_str.rindex("]") + 1]
        return _json.loads(json_str)
    except Exception as e:
        logger.error("llm_extraction_failed", error=str(e))
        return []


@router.post("/import-document", response_model=ImportPreviewResponse)
async def import_document(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        if "multipart" not in content_type:
            raise HTTPException(status_code=400, detail="Expected multipart/form-data with 'file' field")

        boundary = content_type.split("boundary=")[1].strip()
        filename = "document.doc"
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
            raise HTTPException(status_code=400, detail="No file content found in multipart form")

        text = _parse_document_text(filename, content)
        kb_context = ""
        try:
            db = get_database_manager()
            with db.get_session() as session:
                from cortex.models import KnowledgeArticle
                articles = session.query(KnowledgeArticle).order_by(KnowledgeArticle.created_at.desc()).limit(20).all()
                kb_context = "\n".join(f"- {a.title}: {a.content[:300]}" for a in articles)
        except:
            pass

        requirements = _call_llm_for_extraction(text, kb_context)
        for i, r in enumerate(requirements):
            if not r.get("requirement_id"):
                r["requirement_id"] = f"REQ-IMP-{i + 1:03d}"
            if not r.get("priority"):
                r["priority"] = "shall"
            r["status"] = "draft"

        return ImportPreviewResponse(requirements=requirements, source_document=filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("import_document_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Document import failed: {str(e)}")


@router.post("/import-batch", response_model=ImportPreviewResponse)
async def import_batch_validate(
    req: BatchImportRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)
    items = req.items
    for i, r in enumerate(items):
        if not r.get("requirement_id"):
            r["requirement_id"] = f"REQ-BATCH-{i + 1:03d}"
        if not r.get("priority"):
            r["priority"] = "shall"
        r["status"] = "draft"
    return ImportPreviewResponse(requirements=items)


@router.post("/import-batch/save")
async def import_batch_save(
    req: BatchImportSaveRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)
    db = get_database_manager()
    imported = []
    with db.get_session() as session:
        for item in req.items:
            existing = session.query(Requirement).filter(
                Requirement.requirement_id == item.get("requirement_id")
            ).first()
            if existing:
                continue
            r = Requirement(
                requirement_id=item.get("requirement_id", f"REQ-IMP-{len(imported) + 1:03d}"),
                title=item.get("title", item.get("description", "Untitled")[:80]),
                description=item.get("description", item.get("title", "")),
                rationale=item.get("rationale"),
                requirement_type=item.get("requirement_type"),
                priority=item.get("priority", RequirementPriority.SHALL.value),
                status=RequirementStatus.DRAFT.value,
                safety_class=item.get("safety_class", SafetyClass.CLASS_B.value),
                sil_level=item.get("sil_level", SILLevel.SIL2.value),
                category=item.get("category"),
                source=item.get("source"),
                compliance_ref=item.get("compliance_ref"),
                stakeholder=item.get("stakeholder"),
                acceptance_criteria=item.get("acceptance_criteria"),
                allocation=item.get("allocation"),
                version=1,
                change_history=[],
                traceability_tags=item.get("traceability_tags"),
                risk_level=item.get("risk_level"),
                verification_method=item.get("verification_method"),
                verification_status=VerificationStatus.PENDING.value,
                created_by=current_user.id,
            )
            session.add(r)
            imported.append(item.get("requirement_id"))
        session.commit()

    log_audit(
        action="requirements_batch_import",
        user_id=current_user.id,
        resource_type="requirement",
        details={"count": len(imported), "ids": imported[:10]},
        ip_address=get_client_ip(request),
    )
    return {"imported": len(imported), "requirement_ids": imported}


# === ReqIF Export ===

@router.get("/export-reqif")
async def export_reqif(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    ids: Optional[str] = Query(default=None, description="Comma-separated requirement IDs"),
):
    require_permission(current_user, Permission.REQUIREMENT_READ)
    from fastapi.responses import Response

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(Requirement)
        if ids:
            id_list = [i.strip() for i in ids.split(",") if i.strip()]
            query = query.filter(Requirement.requirement_id.in_(id_list))
        results = query.order_by(Requirement.created_at.desc()).limit(500).all()

        scan_results = {"requirements": [], "test_cases": [], "trace_links": []}
        for r in results:
            scan_results["requirements"].append({
                "req_id": r.requirement_id,
                "content": r.description or r.title,
                "type": r.requirement_type or r.category or "functional",
                "priority": r.priority or "shall",
                "safety_class": r.safety_class,
                "file_path": f"db://requirements/{r.requirement_id}",
                "source": r.source,
                "compliance_ref": r.compliance_ref,
                "allocation": r.allocation,
            })
            for c in (r.citations or []):
                scan_results["trace_links"].append({
                    "source_id": r.requirement_id,
                    "source_type": "requirement",
                    "target_id": c.target_requirement_id,
                    "target_type": "requirement",
                    "link_type": c.citation_type,
                    "file_path": f"db://citations/{c.id}",
                    "line_number": 0,
                })

        try:
            from cortex.reqif_helper import ReqIFExporter
            exporter = ReqIFExporter()
            reqif_xml = exporter.to_string(scan_results)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            return Response(
                content=reqif_xml,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=cortex_requirements_{ts}.reqif"
                },
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="ReqIF export requires lxml: pip install lxml")
        except Exception as e:
            logger.error("reqif_export_error", error=str(e))
            raise HTTPException(status_code=500, detail=f"ReqIF export failed: {str(e)}")


# === LLM Generator ===

class GenerationRequest(BaseModel):
    product_name: Optional[str] = None
    topic: Optional[str] = None
    count: int = Field(default=10, ge=1, le=50)


@router.post("/generate-from-kb")
async def generate_requirements(
    req: GenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    require_permission(current_user, Permission.REQUIREMENT_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        from cortex.models import KnowledgeArticle
        articles = session.query(KnowledgeArticle).order_by(KnowledgeArticle.created_at.desc()).limit(20).all()
        kb_context = "\n\n".join(f"## {a.title} [{a.category}]\n{a.content}" for a in articles)

    if req.product_name:
        kb_context = f"PRODUCT: {req.product_name}\n\n{kb_context}"
    if req.topic:
        kb_context = f"FOCUS AREA: {req.topic}\n\n{kb_context}"

    try:
        from cortex.brain import Brain, ModelProvider
        model = os.getenv("LLM_MODEL", "llama3")
        provider = os.getenv("LLM_PROVIDER", "ollama")
        brain = Brain(model=model, provider=ModelProvider(provider) if provider else ModelProvider.OLLAMA)

        prompt = f"""Generate {req.count} INCOSE-compliant system requirements based on the knowledge base.
Return ONLY a JSON array of requirement objects.

Each object must have: requirement_id, title, description (SHALL statement), rationale, requirement_type,
priority (shall/must/should/may), acceptance_criteria, source ("generated_from_kb"), compliance_ref.

Knowledge Base:
{kb_context[:10000]}

Requirements JSON array:"""

        result, _ = brain.generate(prompt, temperature=0.4, max_tokens=4096)
        json_str = result.strip()
        if "```" in json_str:
            for p in json_str.split("```"):
                p = p.strip()
                if p.startswith("json"):
                    json_str = p[4:].strip()
                    break
        if "[" in json_str:
            json_str = json_str[json_str.index("["):]
            if "]" in json_str:
                json_str = json_str[:json_str.rindex("]") + 1]
        generated = _json.loads(json_str)

        for i, r in enumerate(generated):
            if not r.get("requirement_id"):
                r["requirement_id"] = f"REQ-GEN-{i + 1:03d}"
            r["status"] = "draft"

        return {"generated": len(generated), "requirements": generated}
    except Exception as e:
        logger.error("requirement_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")



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

        response = RequirementTraceabilityResponse(
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

    return response


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
        if update.rationale is not None:
            requirement.rationale = update.rationale
        if update.requirement_type is not None:
            requirement.requirement_type = update.requirement_type
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
        if update.source is not None:
            requirement.source = update.source
        if update.compliance_ref is not None:
            requirement.compliance_ref = update.compliance_ref
        if update.stakeholder is not None:
            requirement.stakeholder = update.stakeholder
        if update.acceptance_criteria is not None:
            requirement.acceptance_criteria = update.acceptance_criteria
        if update.allocation is not None:
            requirement.allocation = update.allocation
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
            if update.verification_status == VerificationStatus.PENDING.value:
                requirement.approved_by = None
                requirement.approved_at = None

        # Bump version and record change
        ch = list(requirement.change_history or [])
        ch.append({
            "version": (requirement.version or 1) + 1,
            "who": str(current_user.id),
            "when": datetime.utcnow().isoformat(),
            "what": update.model_dump(exclude_none=True),
        })
        requirement.change_history = ch
        requirement.version = (requirement.version or 1) + 1

        session.commit()
        session.refresh(requirement)
        response = _requirement_to_response(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_UPDATE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=requirement_uuid,
        ip_address=get_client_ip(request),
        details={"updated_fields": update.model_dump(exclude_none=True)},
    )

    return response


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
        response = _requirement_to_response(requirement)

    log_audit(
        action=AuditAction.REQUIREMENT_APPROVE.value,
        user_id=current_user.id,
        resource_type="requirement",
        resource_id=requirement_uuid,
        ip_address=get_client_ip(request),
        details={"comment": body.comment if body else None, "action": "approved"},
    )

    return response


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
        response = _citation_to_response(citation)

    log_audit(
        action=AuditAction.REQUIREMENT_CITATION_ADD.value,
        user_id=current_user.id,
        resource_type="requirement_citation",
        resource_id=response.id,
        ip_address=get_client_ip(request),
        details={
            "source": citation_req.source_requirement_id,
            "target": citation_req.target_requirement_id,
            "type": citation_req.citation_type,
        },
    )

    return response


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
        response = [_citation_to_response(c) for c in results]

    return response


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
        response = _citation_to_response(citation)

    log_audit(
        action=AuditAction.REQUIREMENT_CITATION_VERIFY.value,
        user_id=current_user.id,
        resource_type="requirement_citation",
        resource_id=citation_id,
        ip_address=get_client_ip(request),
    )

    return response
