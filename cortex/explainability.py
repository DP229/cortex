"""
Cortex Explainability Tags - EU AI Act Traceability Layer

Phase 1 Compliance Enhancement: Tags every vector embedding and
knowledge base operation with strict metadata for regulatory compliance.

EU AI Act Requirements (Article 11 - Transparency):
- Logging of AI system inputs and outputs
- Traceability of decisions
- Documentation of model versions and data sources
- Human review flags for critical operations

Key Features:
- Embedding metadata tagging (model, source, timestamp, reviewer)
- Audit trail for all retrieval operations
- Compliance report generation
- Data provenance tracking
- Human-in-the-loop review flags

For safety-critical industries (IEC 62304, EN 50128):
- Provides audit trail for regulatory submissions
- Enables post-hoc explanation of AI decisions
- Supports Tool Qualification Kit (TQK) requirements
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import hashlib
import logging

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    """Human review status for compliance items"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ConfidenceLevel(Enum):
    """Confidence levels for embeddings"""
    HIGH = "high"        # Exact match, verified
    MEDIUM = "medium"    # Semantic match, plausible
    LOW = "low"          # Fuzzy match, needs review
    UNVERIFIED = "unverified"  # No human review yet


class DataSourceType(Enum):
    """Types of data sources for provenance"""
    INGESTED_DOCUMENT = "ingested_document"
    WEB_SCRAPED = "web_scraped"
    USER_INPUT = "user_input"
    GENERATED_OUTPUT = "generated_output"
    DERIVED_CONTENT = "derived_content"


@dataclass
class EmbeddingMetadata:
    """
    Metadata for every vector embedding.
    
    Required for EU AI Act Article 11 compliance.
    """
    # Identity
    embedding_id: str
    content_hash: str  # SHA256 of original content
    
    # Model information
    embedding_model: str
    embedding_model_version: str
    embedding_dimension: int
    
    # Data provenance
    source_type: str  # DataSourceType value
    source_path: str   # File path or URL
    source_title: str
    source_created_at: float
    ingested_at: float = field(default_factory=time.time)
    
    # Processing
    processing_method: str = "standard"  # chunking method used
    chunk_id: Optional[str] = None
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    
    # Review tracking (EU AI Act requirement)
    review_status: str = ReviewStatus.PENDING.value
    review_status_changed_at: float = 0
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    
    # Confidence
    confidence_level: str = ConfidenceLevel.UNVERIFIED.value
    confidence_score: float = 0.0
    
    # Compliance
    is_compliant: bool = True
    compliance_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EmbeddingMetadata':
        """Create from dictionary"""
        return cls(**data)
    
    def access(self) -> None:
        """Record an access to this embedding"""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def set_review_status(
        self,
        status: ReviewStatus,
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Update review status (human-in-the-loop)"""
        self.review_status = status.value
        self.review_status_changed_at = time.time()
        if reviewed_by:
            self.reviewed_by = reviewed_by
        if notes:
            self.review_notes = notes


@dataclass
class RetrievalAuditEntry:
    """
    Audit entry for every retrieval operation.
    
    Required for EU AI Act Article 12 (Logging) compliance.
    """
    # Identity
    audit_id: str
    operation_type: str  # "search", "retrieve", "generate"
    
    # Request
    query: str
    query_hash: str  # Hash of query for privacy
    
    # Results
    retrieved_chunk_ids: List[str]
    retrieved_paths: List[str]
    retrieval_scores: List[float]
    
    # Context
    context_injected: bool = False
    context_size_chars: int = 0
    
    # User/System
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Timing
    timestamp: float = field(default_factory=time.time)
    latency_ms: int = 0
    
    # Compliance
    is_compliant: bool = True
    compliance_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RetrievalAuditEntry':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class ComplianceReport:
    """Generated compliance report"""
    report_id: str
    generated_at: float
    period_start: float
    period_end: float
    
    # Statistics
    total_embeddings: int = 0
    total_retrievals: int = 0
    reviewed_count: int = 0
    pending_review_count: int = 0
    
    # Compliance metrics
    compliance_rate: float = 0.0
    average_confidence: float = 0.0
    
    # Issues
    flagged_items: List[Dict[str, Any]] = field(default_factory=list)
    expired_reviews: List[str] = field(default_factory=list)
    
    # EU AI Act specific
    article_11_compliant: bool = False
    article_12_compliant: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ExplainabilityTracker:
    """
    Tracks embeddings and retrieval operations for compliance.
    
    Provides the audit trail required by EU AI Act Articles 11 and 12.
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        review_expiry_days: int = 90,
        auto_flag_low_confidence: bool = True,
    ):
        self.storage_path = Path(storage_path) if storage_path else None
        self.review_expiry_days = review_expiry_days
        self.auto_flag_low_confidence = auto_flag_low_confidence
        
        # In-memory indices for fast access
        self.embeddings: Dict[str, EmbeddingMetadata] = {}
        self.audit_log: List[RetrievalAuditEntry] = []
        
        # Load from disk if available
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()
    
    def register_embedding(
        self,
        content: str,
        embedding_model: str,
        embedding_model_version: str,
        embedding_dimension: int,
        source_type: DataSourceType,
        source_path: str,
        source_title: str,
        source_created_at: float,
        processing_method: str = "standard",
        chunk_id: Optional[str] = None,
    ) -> str:
        """
        Register a new embedding with full metadata.
        
        Returns the embedding_id for reference.
        """
        embedding_id = f"emb_{uuid.uuid4().hex[:16]}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        metadata = EmbeddingMetadata(
            embedding_id=embedding_id,
            content_hash=content_hash,
            embedding_model=embedding_model,
            embedding_model_version=embedding_model_version,
            embedding_dimension=embedding_dimension,
            source_type=source_type.value,
            source_path=source_path,
            source_title=source_title,
            source_created_at=source_created_at,
            processing_method=processing_method,
            chunk_id=chunk_id,
        )
        
        self.embeddings[embedding_id] = metadata
        self._persist_embedding(metadata)
        
        return embedding_id
    
    def get_embedding(self, embedding_id: str) -> Optional[EmbeddingMetadata]:
        """Get embedding metadata"""
        if embedding_id in self.embeddings:
            self.embeddings[embedding_id].access()
            return self.embeddings[embedding_id]
        return None
    
    def get_embedding_by_content_hash(
        self,
        content_hash: str,
    ) -> Optional[EmbeddingMetadata]:
        """Find embedding by content hash"""
        for emb in self.embeddings.values():
            if emb.content_hash == content_hash:
                emb.access()
                return emb
        return None
    
    def update_confidence(
        self,
        embedding_id: str,
        confidence_score: float,
        confidence_level: ConfidenceLevel,
    ) -> None:
        """Update confidence metrics for an embedding"""
        if embedding_id not in self.embeddings:
            return
        
        metadata = self.embeddings[embedding_id]
        metadata.confidence_score = confidence_score
        metadata.confidence_level = confidence_level.value
        
        # Auto-flag for review if low confidence
        if self.auto_flag_low_confidence and confidence_level == ConfidenceLevel.LOW:
            metadata.compliance_flags.append(f"low_confidence:{confidence_score:.2f}")
        
        self._persist_embedding(metadata)
    
    def log_retrieval(
        self,
        query: str,
        retrieved_chunk_ids: List[str],
        retrieved_paths: List[str],
        retrieval_scores: List[float],
        context_injected: bool = False,
        context_size_chars: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        latency_ms: int = 0,
    ) -> str:
        """
        Log a retrieval operation for audit.
        
        Returns the audit_id for reference.
        """
        audit_id = f"audit_{uuid.uuid4().hex[:16]}"
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        entry = RetrievalAuditEntry(
            audit_id=audit_id,
            operation_type="retrieve",
            query=query,
            query_hash=query_hash,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_paths=retrieved_paths,
            retrieval_scores=retrieval_scores,
            context_injected=context_injected,
            context_size_chars=context_size_chars,
            user_id=user_id,
            session_id=session_id,
            latency_ms=latency_ms,
        )
        
        self.audit_log.append(entry)
        
        # Update access counts for retrieved embeddings
        for chunk_id in retrieved_chunk_ids:
            for emb in self.embeddings.values():
                if emb.chunk_id == chunk_id:
                    emb.access()
        
        self._persist_audit(entry)
        
        return audit_id
    
    def review_embedding(
        self,
        embedding_id: str,
        status: ReviewStatus,
        reviewed_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Mark an embedding as reviewed by human"""
        if embedding_id not in self.embeddings:
            return False
        
        metadata = self.embeddings[embedding_id]
        metadata.set_review_status(status, reviewed_by, notes)
        
        self._persist_embedding(metadata)
        
        return True
    
    def get_pending_reviews(self, limit: int = 100) -> List[EmbeddingMetadata]:
        """Get embeddings pending human review"""
        pending = [
            emb for emb in self.embeddings.values()
            if emb.review_status == ReviewStatus.PENDING.value
        ]
        
        # Sort by oldest first
        pending.sort(key=lambda x: x.created_at)
        
        return pending[:limit]
    
    def get_expiring_reviews(self, days: int = 7) -> List[EmbeddingMetadata]:
        """Get embeddings with reviews expiring soon"""
        expiry_threshold = time.time() - (self.review_expiry_days - days) * 86400
        
        expiring = [
            emb for emb in self.embeddings.values()
            if emb.review_status_changed_at < expiry_threshold
            and emb.review_status == ReviewStatus.APPROVED.value
        ]
        
        return expiring
    
    def generate_compliance_report(
        self,
        period_start: Optional[float] = None,
        period_end: Optional[float] = None,
    ) -> ComplianceReport:
        """
        Generate a compliance report for EU AI Act requirements.
        """
        if not period_end:
            period_end = time.time()
        if not period_start:
            period_start = period_end - (30 * 86400)  # Last 30 days default
        
        # Filter audit entries by period
        period_audits = [
            a for a in self.audit_log
            if period_start <= a.timestamp <= period_end
        ]
        
        # Calculate statistics
        total_embeddings = len(self.embeddings)
        total_retrievals = len(period_audits)
        
        reviewed = sum(
            1 for emb in self.embeddings.values()
            if emb.review_status == ReviewStatus.APPROVED.value
        )
        pending = sum(
            1 for emb in self.embeddings.values()
            if emb.review_status == ReviewStatus.PENDING.value
        )
        
        # Compliance rate
        flagged = sum(
            1 for emb in self.embeddings.values()
            if emb.compliance_flags or not emb.is_compliant
        )
        compliance_rate = (total_embeddings - flagged) / max(total_embeddings, 1)
        
        # Average confidence
        confidences = [e.confidence_score for e in self.embeddings.values() if e.confidence_score > 0]
        avg_confidence = sum(confidences) / max(len(confidences), 1)
        
        # Flagged items
        flagged_items = [
            {
                "embedding_id": emb.embedding_id,
                "source_path": emb.source_path,
                "flags": emb.compliance_flags,
            }
            for emb in self.embeddings.values()
            if emb.compliance_flags
        ]
        
        # Expired reviews
        expiry_threshold = time.time() - self.review_expiry_days * 86400
        expired = [
            emb.embedding_id
            for emb in self.embeddings.values()
            if emb.review_status_changed_at < expiry_threshold
            and emb.review_status == ReviewStatus.APPROVED.value
        ]
        
        report = ComplianceReport(
            report_id=f"report_{uuid.uuid4().hex[:12]}",
            generated_at=time.time(),
            period_start=period_start,
            period_end=period_end,
            total_embeddings=total_embeddings,
            total_retrievals=total_retrievals,
            reviewed_count=reviewed,
            pending_review_count=pending,
            compliance_rate=compliance_rate,
            average_confidence=avg_confidence,
            flagged_items=flagged_items,
            expired_reviews=expired,
            article_11_compliant=compliance_rate >= 0.95,
            article_12_compliant=total_retrievals > 0 and len(period_audits) == total_retrievals,
        )
        
        return report
    
    def export_audit_log(
        self,
        format: str = "json",
        period_start: Optional[float] = None,
        period_end: Optional[float] = None,
    ) -> str:
        """
        Export audit log for compliance submission.
        """
        if not period_end:
            period_end = time.time()
        if not period_start:
            period_start = 0
        
        entries = [
            a for a in self.audit_log
            if period_start <= a.timestamp <= period_end
        ]
        
        if format == "json":
            return json.dumps([e.to_dict() for e in entries], indent=2)
        elif format == "csv":
            lines = ["audit_id,operation_type,query_hash,timestamp,latency_ms,retrieved_count"]
            for e in entries:
                lines.append(
                    f"{e.audit_id},{e.operation_type},{e.query_hash},"
                    f"{e.timestamp},{e.latency_ms},{len(e.retrieved_chunk_ids)}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _persist_embedding(self, metadata: EmbeddingMetadata) -> None:
        """Persist embedding metadata to disk"""
        if not self.storage_path:
            return
        
        path = self.storage_path / f"{metadata.embedding_id}.json"
        path.write_text(json.dumps(metadata.to_dict(), indent=2))
    
    def _persist_audit(self, entry: RetrievalAuditEntry) -> None:
        """Persist audit entry to disk"""
        if not self.storage_path:
            return
        
        path = self.storage_path / "audit" / f"{entry.audit_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry.to_dict(), indent=2))
    
    def _load_from_disk(self) -> None:
        """Load persisted data from disk"""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        # Load embeddings
        for path in self.storage_path.glob("emb_*.json"):
            try:
                data = json.loads(path.read_text())
                metadata = EmbeddingMetadata.from_dict(data)
                self.embeddings[metadata.embedding_id] = metadata
            except Exception as e:
                logger.warning(f"Failed to load embedding from {path}: {e}")
        
        # Load audit entries
        audit_dir = self.storage_path / "audit"
        if audit_dir.exists():
            for path in audit_dir.glob("audit_*.json"):
                try:
                    data = json.loads(path.read_text())
                    entry = RetrievalAuditEntry.from_dict(data)
                    self.audit_log.append(entry)
                except Exception as e:
                    logger.warning(f"Failed to load audit entry from {path}: {e}")
        
        logger.info(f"Loaded {len(self.embeddings)} embeddings and {len(self.audit_log)} audit entries")


# === Integration Helpers ===

def create_explainability_tracker(
    storage_path: Optional[str] = None,
) -> ExplainabilityTracker:
    """Factory to create explainability tracker"""
    return ExplainabilityTracker(storage_path=storage_path)


def tag_retrieval_operation(
    tracker: ExplainabilityTracker,
    query: str,
    results: List[Any],
    latency_ms: int = 0,
) -> str:
    """
    Tag a retrieval operation with explainability metadata.
    
    Usage:
        tracker = create_explainability_tracker()
        audit_id = tag_retrieval_operation(tracker, query, search_results)
    """
    chunk_ids = [r.chunk_id for r in results if hasattr(r, 'chunk_id')]
    paths = [r.path for r in results if hasattr(r, 'path')]
    scores = [r.score for r in results if hasattr(r, 'score')]
    
    return tracker.log_retrieval(
        query=query,
        retrieved_chunk_ids=chunk_ids,
        retrieved_paths=paths,
        retrieval_scores=scores,
        latency_ms=latency_ms,
    )


# === Compliance Check Functions ===

def check_article_11_compliance(tracker: ExplainabilityTracker) -> Tuple[bool, List[str]]:
    """
    Check EU AI Act Article 11 (Transparency) compliance.
    
    Returns: (is_compliant, list_of_issues)
    """
    issues = []
    
    total = len(tracker.embeddings)
    if total == 0:
        issues.append("No embeddings registered")
        return False, issues
    
    # Check for model version tagging
    untagged = [
        e.embedding_id for e in tracker.embeddings.values()
        if not e.embedding_model_version
    ]
    if untagged:
        issues.append(f"{len(untagged)} embeddings without model version")
    
    # Check for source provenance
    no_source = [
        e.embedding_id for e in tracker.embeddings.values()
        if not e.source_path
    ]
    if no_source:
        issues.append(f"{len(no_source)} embeddings without source provenance")
    
    # Check for timestamps
    no_timestamp = [
        e.embedding_id for e in tracker.embeddings.values()
        if not e.created_at
    ]
    if no_timestamp:
        issues.append(f"{len(no_timestamp)} embeddings without timestamp")
    
    compliance_rate = (total - len(untagged) - len(no_source) - len(no_timestamp)) / total
    
    return compliance_rate >= 0.95, issues


def check_article_12_compliance(tracker: ExplainabilityTracker) -> Tuple[bool, List[str]]:
    """
    Check EU AI Act Article 12 (Logging) compliance.
    
    Returns: (is_compliant, list_of_issues)
    """
    issues = []
    
    if not tracker.audit_log:
        issues.append("No audit log entries found")
        return False, issues
    
    # Check for complete retrieval logging
    incomplete = [
        a.audit_id for a in tracker.audit_log
        if not a.query or not a.retrieved_chunk_ids
    ]
    if incomplete:
        issues.append(f"{len(incomplete)} audit entries with missing data")
    
    # Check for timestamp continuity
    timestamps = [a.timestamp for a in tracker.audit_log]
    gaps = sum(1 for i in range(1, len(timestamps)) if timestamps[i] - timestamps[i-1] > 86400 * 7)
    if gaps > 0:
        issues.append(f"{gaps} gaps >7 days in audit log")
    
    return len(issues) == 0, issues