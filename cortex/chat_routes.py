"""
Cortex Chat Assistant API - AI Compliance Copilot

Enables conversation with the unified Brain (Ollama/OpenAI) to ask compliance questions,
supported by dynamic Retrieval-Augmented Generation (RAG) against the local Knowledge Base.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, KnowledgeArticle
from cortex.audit import log_audit
from cortex.database import get_database_manager
from cortex.brain import Brain, ModelConfig

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["AI Assistant"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Current message from the user")
    history: List[ChatMessage] = Field(default_factory=list, description="Previous messages in the conversation")


class ChatSource(BaseModel):
    id: str
    title: str
    category: str
    source: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[ChatSource]


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
            detail=f"Permission '{permission.value}' required to access compliance agent.",
        )


@router.post("", response_model=ChatResponse)
async def chat_with_agent(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Submit a prompt to the AI Compliance Assistant.
    Retrieves matching articles from the local Knowledge Base for RAG context.
    """
    # Require read permissions for compliance data
    require_permission(current_user, Permission.REQUIREMENT_READ)

    # 1. Retrieve RAG context from the Knowledge Base
    db = get_database_manager()
    sources: List[ChatSource] = []
    kb_context_parts = []
    
    # Simple keyword search
    search_query = req.message.strip()
    # Try to find relevant articles
    with db.get_session() as session:
        # Search title/content for search_query, or filter based on words
        words = [w for w in search_query.split() if len(w) > 3]
        query = session.query(KnowledgeArticle)
        
        if words:
            # Build filters
            filters = []
            for word in words[:3]:  # limit to first 3 words for simplicity
                like = f"%{word}%"
                filters.append(
                    (KnowledgeArticle.title.ilike(like)) |
                    (KnowledgeArticle.content.ilike(like))
                )
            if filters:
                from sqlalchemy import or_
                query = query.filter(or_(*filters))
        else:
            like = f"%{search_query}%"
            query = query.filter(
                (KnowledgeArticle.title.ilike(like)) |
                (KnowledgeArticle.content.ilike(like))
            )
            
        articles = query.order_by(KnowledgeArticle.created_at.desc()).limit(3).all()
        
        for a in articles:
            sources.append(ChatSource(
                id=str(a.id),
                title=a.title,
                category=a.category,
                source=a.source
            ))
            kb_context_parts.append(
                f"## Article: {a.title} ({a.category})\n"
                f"Source standard reference: {a.source or 'N/A'}\n"
                f"Content:\n{a.content[:1500]}"
            )

    kb_context = "\n\n---\n\n".join(kb_context_parts) if kb_context_parts else "No relevant articles found in Knowledge Base."

    # 2. Build model prompt with chat history
    system_prompt = (
        "You are Cortex, an enterprise software lifecycle AI safety and compliance assistant for railway systems "
        "(conforming to EN 50128 / EN 50716 Class B, and IEC 62443 cybersecurity standards).\n"
        "Your goal is to help software engineers, safety managers, and compliance officers review requirements, "
        "verify safety integrity levels (SIL), justify SOUP components, and prepare for audits.\n\n"
        "Instructions:\n"
        "1. Answer user requests professionally and authoritatively.\n"
        "2. Ground your answers in the provided Knowledge Base context when available. Cite sources/articles where appropriate.\n"
        "3. Use structured markdown (bullet points, bold text, code blocks, tables) for clarity.\n"
        "4. If standard compliance guidelines are requested but context is lacking, use your general knowledge of "
        "EN 50128 and IEC 62443 to assist safely, but remind the user to verify against standard documents.\n"
        "5. Be concise and precise. Never make up safety facts."
    )

    # Construct chat format prompt
    formatted_prompt = "Here is the context retrieved from the local compliance Knowledge Base:\n\n"
    formatted_prompt += f"{kb_context}\n\n"
    formatted_prompt += "Here is the conversation history:\n"
    
    for msg in req.history:
        role_name = "User" if msg.role == "user" else "Assistant"
        formatted_prompt += f"{role_name}: {msg.content}\n"
        
    formatted_prompt += f"\nUser: {req.message}\n"
    formatted_prompt += "Assistant:"

    # 3. Call the Brain model
    try:
        model = os.getenv("LLM_MODEL", "llama3")
        brain = Brain(default_model=model)
        
        response_text, _ = brain.generate(
            prompt=formatted_prompt,
            system_prompt=system_prompt,
            config=ModelConfig(temperature=0.3, max_tokens=3000)
        )
    except Exception as e:
        logger.error("chat_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI agent failed to generate response: {str(e)}"
        )

    # 4. Log audit event
    log_audit(
        action="chat_assistant_query",
        user_id=current_user.id,
        resource_type="ai_assistant",
        resource_id="chat",
        ip_address=get_client_ip(request),
        details={"query": req.message[:100], "retrieved_sources": len(sources)},
    )

    return ChatResponse(
        response=response_text,
        sources=sources
    )
