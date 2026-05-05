"""
Cortex Decision Reproducibility Package (DRP)

FDA 21 CFR Part 11 / IEC 62304 / EN 50716 Annex D / EU AI Act Article 9 Compliant
Audit Trail Generator for AI-Assisted Decisions

EN 50716 Annex D requires AI tool evidence:
- AI system version (semantic + commit hash)
- Training data hash (SHA-256 of corpus)
- Data provenance (source, collection date, preprocessing version)
- Model card fields (architecture, training methodology, evaluation metrics)

Every compliance-critical AI query produces a signed, timestamped audit
package containing all inputs, outputs, and metadata required for:
- Regulatory audit trails
- FDA submissions
- IEC 62304 records
- EN 50716 Annex D accountability records
- EU AI Act Article 9 accountability records

DRP Structure:
  /drp/
  └── 2026/
      └── 04/
          └── 07/
              └── drp_a1b2c3d4/
                  ├── manifest.json          # Package metadata
                  ├── prompt.json            # Exact prompt sent to model
                  ├── context_chunks.json     # Retrieved context with scores
                  ├── model_info.json        # Model version, config
                  ├── response_raw.json      # Raw model response
                  ├── citations.json          # Verified citations
                  ├── metadata.json          # Additional context
                  └── signature.json         # HMAC signature of all files

Signature Chain:
  - Each file is SHA256 hashed individually
  - manifest.json contains hashes of all other files
  - signature.json contains HMAC of manifest.json
  - HMAC key is from key_manager (key rotation supported)
"""

import os
import json
import hmac
import hashlib
import time
import uuid
import platform
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import logging
import threading
import gzip
import shutil

from cortex.deterministic_core import compute_hash, ComplianceResult, ModuleVersion
from cortex.contracts import behavioral_contract

logger = logging.getLogger(__name__)


# =============================================================================
# DRP EXCEPTION
# =============================================================================

class DRPError(Exception):
    """Base exception for DRP operations"""
    pass


class DRPWriteError(DRPError):
    """Failed to write DRP files"""
    pass


class DRPSignatureError(DRPError):
    """Signature verification failed"""
    pass


class DRPConfigurationError(DRPError):
    """Invalid DRP configuration"""
    pass


# =============================================================================
# DRP CONFIGURATION
# =============================================================================

class DRPConfig:
    """
    Configuration for Decision Reproducibility Package generation.
    
    Settings:
    - storage_path: Where DRP directories are created
    - retention_days: How long to keep DRP packages
    - compression: Compress large files with gzip
    - signature_enabled: Whether to sign packages
    - key_manager: KeyRotationManager for signing keys
    """
    
    def __init__(
        self,
        storage_path: str = "/var/log/cortex/drp",
        retention_days: int = 2555,  # ~7 years for FDA Part 11
        compression_threshold_kb: int = 100,
        signature_enabled: bool = True,
        key_manager = None,
        retention_policy: str = "archive",  # archive | delete | immutable
    ):
        self.storage_path = Path(storage_path)
        self.retention_days = retention_days
        self.compression_threshold_kb = compression_threshold_kb
        self.signature_enabled = signature_enabled
        self.key_manager = key_manager
        self.retention_policy = retention_policy
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def get_package_path(self, package_id: str) -> Path:
        """Get full path for a package"""
        now = datetime.now(timezone.utc)
        return self.storage_path / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}" / package_id
    
    def should_compress(self, content: str) -> bool:
        """Check if content should be compressed"""
        return len(content.encode('utf-8')) > self.compression_threshold_kb * 1024


# =============================================================================
# DRP PACKAGE FILES
# =============================================================================

@dataclass
class DRPManifest:
    """Metadata about the entire DRP package"""
    package_id: str
    created_at: str  # ISO 8601
    created_by: str  # System/user that created this
    hostname: str
    platform: str
    python_version: str
    cortex_version: str
    compliance_standards: List[str]  # ["FDA_21CFR_Part11", "IEC_62304", ...]
    file_hashes: Dict[str, str]  # filename -> SHA256 hash
    total_files: int
    package_size_bytes: int
    signed: bool
    signature_key_version: Optional[int] = None


@dataclass
class DRPFileMetadata:
    """Metadata for a single file in the package"""
    filename: str
    content_type: str  # json | json+gzip
    size_bytes: int
    compressed: bool
    sha256_hash: str
    created_at: str


@dataclass
class DRPPrompt:
    """The exact prompt sent to the AI model"""
    prompt_text: str
    system_prompt: Optional[str] = None
    conversation_history: List[Dict] = field(default_factory=list)
    expanded_query: Optional[str] = None  # If query expansion was used
    token_count: int = 0
    truncation_applied: bool = False


@dataclass
class DRPContextChunk:
    """A retrieved context chunk with relevance scoring"""
    chunk_id: str
    source_path: str
    source_title: str
    chunk_text: str
    relevance_score: float  # 0.0 - 1.0
    rank: int
    retrieval_method: str  # vector | bm25 | hybrid


@dataclass
class DRPModelInfo:
    """Model configuration and version info"""
    model_name: str
    model_version: Optional[str] = None
    provider: str = "ollama"  # ollama | openai | anthropic
    temperature: float = 0.0
    max_tokens: int = 0
    context_window: int = 0
    inference_time_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class DRPResponse:
    """Raw model response"""
    response_text: str
    finish_reason: str  # stop | length | error
    model_used: str
    raw_output: Dict[str, Any] = field(default_factory=dict)  # Provider-specific raw


@dataclass
class DRPCitation:
    """Citation verification result"""
    citation_index: int
    source_path: str
    source_title: str
    quote: str
    verification_status: str  # verified | partial | modified | not_found
    similarity_score: float
    format_detected: str


@dataclass
class DRPSignature:
    """HMAC signature of the package"""
    manifest_hash: str  # SHA256 of manifest.json
    signature: str  # HMAC-SHA256 of manifest_hash
    key_version: int
    key_id: str
    signed_at: str  # ISO 8601
    algorithm: str = "HMAC-SHA256"


@dataclass
class EN50716AnnexDMetadata:
    """
    EN 50716 Annex D metadata for AI-based tools used in railway safety.

    Required evidence fields:
    - ai_system_version: Semantic version + git hash of the AI component
    - training_data_hash: SHA-256 of the training corpus
    - data_provenance: Source institution, collection date range, preprocessing version
    - model_architecture: Type of model (transformer, RNN, ensemble)
    - training_methodology: Training approach (supervised, RLHF, fine-tuning)
    - evaluation_metrics: Key metrics from model card (accuracy, F1, BLEU, etc.)
    - dataset_split_ratio: train/val/test proportions
    - bias_assessment: Results of fairness/bias testing
    - limitations: Known failure modes and edge cases
    """
    ai_system_version: str
    ai_commit_hash: str
    training_data_hash: str
    data_provenance: str
    data_collection_start: str  # ISO 8601 date
    data_collection_end: str
    preprocessing_version: str
    model_architecture: str
    training_methodology: str
    evaluation_metrics: Dict[str, Any] = field(default_factory=dict)
    dataset_split_ratio: str = "80/10/10"
    bias_assessment: Optional[str] = None
    limitations: str = ""
    compliance_standards: List[str] = field(default_factory=lambda: ["EN_50716_Annex_D"])
    evidence_hash: str = ""

    def __post_init__(self):
        if not self.evidence_hash:
            core_fields = {
                k: v for k, v in asdict(self).items()
                if k not in ("evidence_hash",)
            }
            self.evidence_hash = compute_hash(core_fields)

    def to_evidence(self) -> dict:
        return {
            "ai_system_version": self.ai_system_version,
            "ai_commit_hash": self.ai_commit_hash,
            "training_data_hash": self.training_data_hash,
            "data_provenance": self.data_provenance,
            "data_collection_start": self.data_collection_start,
            "data_collection_end": self.data_collection_end,
            "preprocessing_version": self.preprocessing_version,
            "model_architecture": self.model_architecture,
            "training_methodology": self.training_methodology,
            "evaluation_metrics": self.evaluation_metrics,
            "dataset_split_ratio": self.dataset_split_ratio,
            "bias_assessment": self.bias_assessment,
            "limitations": self.limitations,
            "compliance_standards": self.compliance_standards,
            "evidence_hash": self.evidence_hash,
        }


# =============================================================================
# DRP WRITER
# =============================================================================

class DRPWriter:
    """
    Writes Decision Reproducibility Packages to disk.
    
    Thread-safe: Uses threading.Lock for atomic operations.
    
    Usage:
        config = DRPConfig(storage_path="/var/log/cortex/drp")
        writer = DRPWriter(config)
        
        package_id = writer.create_package()
        writer.write_prompt(package_id, prompt_data)
        writer.write_context(package_id, chunks)
        writer.write_response(package_id, response)
        writer.finalize_package(package_id)  # Signs and seals
    """
    
    def __init__(self, config: DRPConfig):
        self.config = config
        self._lock = threading.RLock()
        self._packages: Dict[str, Dict[str, Any]] = {}
        self._pending_files: Dict[str, List[str]] = {}
    
    def create_package(
        self,
        package_id: Optional[str] = None,
        created_by: str = "system",
        compliance_standards: Optional[List[str]] = None,
    ) -> str:
        """
        Create a new DRP package directory.
        
        Args:
            package_id: Optional ID (auto-generated if not provided)
            created_by: User or system creating the package
            compliance_standards: List of standards this package addresses
            
        Returns:
            The package_id (UUID-based)
        """
        with self._lock:
            if package_id is None:
                package_id = f"drp_{uuid.uuid4().hex[:12]}"
            
            if compliance_standards is None:
                compliance_standards = ["IEC_62304", "FDA_21CFR_Part11"]
            
            package_path = self.config.get_package_path(package_id)
            package_path.mkdir(parents=True, exist_ok=True)
            
            self._packages[package_id] = {
                "path": package_path,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": created_by,
                "compliance_standards": compliance_standards,
                "files": {},
                "finalized": False,
            }
            
            self._pending_files[package_id] = []
            
            logger.info(f"drp_package_created package_id={package_id} path={package_path}")
            
            return package_id
    
    def write_manifest(
        self,
        package_id: str,
        file_hashes: Dict[str, str],
        package_size_bytes: int,
    ) -> None:
        """Write the manifest file"""
        with self._lock:
            if package_id not in self._packages:
                raise DRPWriteError(f"Package {package_id} not found")
            
            pkg = self._packages[package_id]
            
            manifest = DRPManifest(
                package_id=package_id,
                created_at=pkg["created_at"],
                created_by=pkg["created_by"],
                hostname=platform.node(),
                platform=platform.platform(),
                python_version=platform.python_version(),
                cortex_version="1.0",  # Would come from version file
                compliance_standards=pkg["compliance_standards"],
                file_hashes=file_hashes,
                total_files=len(file_hashes),
                package_size_bytes=package_size_bytes,
                signed=False,
            )
            
            content = json.dumps(asdict(manifest), indent=2)
            self._write_file(package_id, "manifest.json", content, "json")
            
            pkg["manifest"] = manifest
    
    def write_prompt(self, package_id: str, prompt_data: DRPPrompt) -> None:
        """Write the prompt file"""
        with self._lock:
            content = json.dumps(asdict(prompt_data), indent=2, default=str)
            self._write_file(package_id, "prompt.json", content, "json")
    
    def write_context_chunks(
        self,
        package_id: str,
        chunks: List[DRPContextChunk],
    ) -> None:
        """Write the context chunks file"""
        with self._lock:
            data = {
                "total_chunks": len(chunks),
                "chunks": [asdict(c) for c in chunks],
            }
            content = json.dumps(data, indent=2, default=str)
            self._write_file(package_id, "context_chunks.json", content, "json")
    
    def write_model_info(self, package_id: str, model_info: DRPModelInfo) -> None:
        """Write the model info file"""
        with self._lock:
            content = json.dumps(asdict(model_info), indent=2, default=str)
            self._write_file(package_id, "model_info.json", content, "json")
    
    def write_response(self, package_id: str, response: DRPResponse) -> None:
        """Write the raw response file"""
        with self._lock:
            content = json.dumps(asdict(response), indent=2, default=str)
            self._write_file(package_id, "response_raw.json", content, "json")
    
    def write_citations(
        self,
        package_id: str,
        citations: List[DRPCitation],
    ) -> None:
        """Write the citations file"""
        with self._lock:
            data = {
                "total_citations": len(citations),
                "verified": sum(1 for c in citations if c.verification_status == "verified"),
                "citations": [asdict(c) for c in citations],
            }
            content = json.dumps(data, indent=2, default=str)
            self._write_file(package_id, "citations.json", content, "json")
    
    def write_metadata(
        self,
        package_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Write additional metadata file"""
        with self._lock:
            # Add system metadata
            metadata["written_at"] = datetime.now(timezone.utc).isoformat()
            metadata["hostname"] = platform.node()
            
            content = json.dumps(metadata, indent=2, default=str)
            self._write_file(package_id, "metadata.json", content, "json")
    
    def finalize_package(self, package_id: str) -> Dict[str, Any]:
        """
        Finalize and sign the package.
        
        This must be called after all files are written.
        It computes file hashes, creates manifest, and signs.
        
        Returns:
            Dict with package summary and signature info
        """
        with self._lock:
            if package_id not in self._packages:
                raise DRPWriteError(f"Package {package_id} not found")
            
            pkg = self._packages[package_id]
            package_path = pkg["path"]
            
            # Collect all file hashes
            file_hashes: Dict[str, str] = {}
            total_size = 0
            
            for filename in self._pending_files[package_id]:
                file_path = package_path / filename
                if file_path.exists():
                    file_hashes[filename] = self._compute_sha256(file_path)
                    total_size += file_path.stat().st_size
            
            # Write manifest with file hashes
            self.write_manifest(package_id, file_hashes, total_size)
            
            # Re-read manifest to get its hash
            manifest_path = package_path / "manifest.json"
            manifest_hash = self._compute_sha256(manifest_path)
            
            # Sign if enabled
            signature_info = None
            if self.config.signature_enabled:
                signature_info = self._sign_package(package_id, manifest_hash)
            
            # Mark as finalized
            pkg["finalized"] = True
            pkg["manifest_hash"] = manifest_hash
            pkg["signature"] = signature_info
            
            # Create a seal file to indicate package is complete
            seal_path = package_path / ".sealed"
            seal_path.write_text(f"SEALED_AT={datetime.now(timezone.utc).isoformat()}\n")
            
            logger.info(
                f"drp_package_finalized package_id={package_id} "
                f"files={len(file_hashes)} size={total_size} signed={signature_info is not None}"
            )
            
            return {
                "package_id": package_id,
                "path": str(package_path),
                "manifest_hash": manifest_hash,
                "total_files": len(file_hashes),
                "package_size_bytes": total_size,
                "signed": signature_info is not None,
                "signature": signature_info,
            }
    
    def _write_file(
        self,
        package_id: str,
        filename: str,
        content: str,
        content_type: str,
    ) -> None:
        """Internal: Write a file to the package"""
        if package_id not in self._packages:
            raise DRPWriteError(f"Package {package_id} not found")
        
        pkg = self._packages[package_id]
        package_path = pkg["path"]
        
        file_path = package_path / filename
        
        # Check if should compress
        compressed = False
        if self.config.should_compress(content):
            compressed = True
            with gzip.open(file_path.with_suffix('.json.gz'), 'wb') as f:
                f.write(content.encode('utf-8'))
            filename = filename.replace('.json', '.json.gz')
        else:
            file_path.write_text(content, encoding='utf-8')
        
        pkg["files"][filename] = {
            "content_type": content_type,
            "compressed": compressed,
            "size_bytes": len(content.encode('utf-8')),
        }
        
        self._pending_files[package_id].append(filename)
    
    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _sign_package(self, package_id: str, manifest_hash: str) -> Optional[DRPSignature]:
        """Sign the package with HMAC"""
        if self.config.key_manager is None:
            logger.warning("drp_signing_disabled_no_key_manager")
            return None
        
        try:
            key = self.config.key_manager.get_signing_key()
            key_version = self.config.key_manager.get_current_key_version()
            key_id = self.config.key_manager._key_state.get("current_key_id", "unknown")
            
            # Sign the manifest hash
            signature = hmac.new(
                key,
                manifest_hash.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            sig = DRPSignature(
                manifest_hash=manifest_hash,
                signature=signature,
                key_version=key_version,
                key_id=key_id,
                signed_at=datetime.now(timezone.utc).isoformat(),
            )
            
            # Write signature file
            pkg = self._packages[package_id]
            sig_path = pkg["path"] / "signature.json"
            sig_path.write_text(json.dumps(asdict(sig), indent=2), encoding='utf-8')
            
            return sig
        
        except Exception as e:
            logger.error(f"drp_signing_failed package_id={package_id} error={e}")
            raise DRPSignatureError(f"Failed to sign package: {e}")
    
    def verify_package(self, package_id: str) -> Tuple[bool, List[str]]:
        """
        Verify package integrity.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: List[str] = []
        
        with self._lock:
            if package_id not in self._packages:
                return False, [f"Package {package_id} not found"]
            
            pkg = self._packages[package_id]
            package_path = pkg["path"]
            
            # Check if sealed
            seal_path = package_path / ".sealed"
            if not seal_path.exists():
                errors.append("Package not sealed - may be incomplete")
            
            # Check manifest exists
            manifest_path = package_path / "manifest.json"
            if not manifest_path.exists():
                errors.append("manifest.json not found")
                return False, errors
            
            # Load and verify manifest
            try:
                manifest_data = json.loads(manifest_path.read_text())
            except Exception as e:
                errors.append(f"Failed to parse manifest: {e}")
                return False, errors
            
            # Verify file hashes
            for filename, expected_hash in manifest_data.get("file_hashes", {}).items():
                file_path = package_path / filename
                if not file_path.exists():
                    errors.append(f"File missing: {filename}")
                    continue
                
                actual_hash = self._compute_sha256(file_path)
                if actual_hash != expected_hash:
                    errors.append(f"Hash mismatch for {filename}")
            
            # Verify signature if present
            sig_path = package_path / "signature.json"
            if sig_path.exists() and self.config.key_manager:
                try:
                    sig_data = json.loads(sig_path.read_text())
                    
                    # Re-verify signature
                    key = self.config.key_manager.get_key_for_version(sig_data["key_version"])
                    if key:
                        expected_sig = hmac.new(
                            key,
                            sig_data["manifest_hash"].encode('utf-8'),
                            hashlib.sha256
                        ).hexdigest()
                        
                        if not hmac.compare_digest(expected_sig, sig_data["signature"]):
                            errors.append("Signature verification failed")
                    else:
                        errors.append(f"Signing key version {sig_data['key_version']} not found")
                
                except Exception as e:
                    errors.append(f"Signature verification error: {e}")
            
            return len(errors) == 0, errors


# =============================================================================
# DRP WRAPPER FOR COMPLIANCE QUERIES
# =============================================================================

class ComplianceQueryWrapper:
    """
    Wrapper for compliance-critical AI queries that automatically
    generates a Decision Reproducibility Package.
    
    Usage:
        config = DRPConfig()
        key_manager = KeyRotationManager(...)
        
        wrapper = ComplianceQueryWrapper(config, key_manager)
        
        result = wrapper.execute(
            query="What is the failure rate of component X?",
            context_retriever=retriever,
            model=ollama_model,
        )
        
        # result.package_id can be used for audit references
    """
    
    def __init__(
        self,
        drp_config: DRPConfig,
        key_manager = None,
        retriever = None,
        model = None,
    ):
        self.config = drp_config
        if key_manager:
            self.config.key_manager = key_manager
        
        self.writer = DRPWriter(self.config)
        self.retriever = retriever
        self.model = model
    
    def execute(
        self,
        query: str,
        context_retriever,
        model,
        system_prompt: Optional[str] = None,
        safety_class: str = "unknown",
        compliance_standards: Optional[List[str]] = None,
        include_citations: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a compliance-critical query with full DRP generation.
        
        Args:
            query: The user query
            context_retriever: ContextualRetriever instance
            model: Model to use for inference
            system_prompt: Optional system prompt
            safety_class: IEC 62304 safety class
            compliance_standards: List of compliance standards
            include_citations: Whether to verify citations
            metadata: Additional metadata to store
            
        Returns:
            Dict with query result and DRP package info
        """
        start_time = time.time()
        package_id = None
        
        try:
            # Determine compliance standards
            if compliance_standards is None:
                compliance_standards = ["IEC_62304"]
                if safety_class in ("critical", "high"):
                    compliance_standards.append("FDA_21CFR_Part11")
            
            # Create package
            package_id = self.writer.create_package(
                created_by="compliance_query",
                compliance_standards=compliance_standards,
            )
            
            # Build prompt
            prompt_data = self._build_prompt(query, system_prompt, context_retriever)
            self.writer.write_prompt(package_id, prompt_data)
            
            # Retrieve context
            chunks = self._retrieve_context(query, context_retriever)
            self.writer.write_context_chunks(package_id, chunks)
            
            # Get model info
            model_info = self._get_model_info(model)
            self.writer.write_model_info(package_id, model_info)
            
            # Execute query
            response = self._execute_model(model, prompt_data, context_retriever)
            self.writer.write_response(package_id, response)
            
            # Verify citations if requested
            if include_citations:
                citations = self._verify_citations(response, context_retriever)
                self.writer.write_citations(package_id, citations)
            
            # Write metadata
            exec_time_ms = int((time.time() - start_time) * 1000)
            meta = {
                "safety_class": safety_class,
                "query": query,
                "execution_time_ms": exec_time_ms,
                **(metadata or {}),
            }
            self.writer.write_metadata(package_id, meta)
            
            # Finalize (signs and seals)
            summary = self.writer.finalize_package(package_id)
            
            logger.info(
                f"drp_query_completed package_id={package_id} "
                f"exec_time={exec_time_ms}ms safety_class={safety_class}"
            )
            
            return {
                "response": response.response_text,
                "package_id": package_id,
                "package_path": summary["path"],
                "manifest_hash": summary["manifest_hash"],
                "citations": citations if include_citations else [],
                "model_info": asdict(model_info),
                "execution_time_ms": exec_time_ms,
            }
        
        except Exception as e:
            logger.error(f"drp_query_failed package_id={package_id} error={e}")
            
            # Try to at least write what we have
            if package_id:
                try:
                    error_meta = {
                        "error": str(e),
                        "failed_at": "query_execution",
                    }
                    self.writer.write_metadata(package_id, error_meta)
                    self.writer.finalize_package(package_id)
                except Exception:
                    pass
            
            raise
    
    def _build_prompt(
        self,
        query: str,
        system_prompt: Optional[str],
        retriever,
    ) -> DRPPrompt:
        """Build the prompt with context"""
        # Get relevant context
        context_results = retriever.retrieve(query, top_k=5, include_parent_context=True)
        
        # Build context string
        context_parts = []
        for i, result in enumerate(context_results):
            chunk = result["chunk"]
            context_parts.append(f"[{i+1}] {chunk.path}\n{chunk.content[:500]}")
        
        context_str = "\n\n".join(context_parts)
        
        # Build full prompt
        full_prompt = f"""Based on the following context, answer the question.

Context:
{context_str}

Question: {query}

Answer:"""
        
        prompt_data = DRPPrompt(
            prompt_text=full_prompt,
            system_prompt=system_prompt or "You are a compliance assistant for safety-critical systems.",
            expanded_query=query,
            token_count=len(full_prompt.split()),
        )
        
        return prompt_data
    
    def _retrieve_context(
        self,
        query: str,
        retriever,
    ) -> List[DRPContextChunk]:
        """Retrieve context chunks with scoring"""
        results = retriever.retrieve(query, top_k=5, include_parent_context=False)
        
        chunks = []
        for i, result in enumerate(results):
            chunk = result["chunk"]
            chunks.append(DRPContextChunk(
                chunk_id=chunk.chunk_id,
                source_path=chunk.path,
                source_title=chunk.title,
                chunk_text=chunk.content[:1000],  # Truncate for storage
                relevance_score=result["score"],
                rank=i + 1,
                retrieval_method="hybrid",  # Could be vector or bm25
            ))
        
        return chunks
    
    def _get_model_info(self, model) -> DRPModelInfo:
        """Get model information"""
        return DRPModelInfo(
            model_name=getattr(model, 'name', 'unknown'),
            model_version=getattr(model, 'version', None),
            provider="ollama",
            temperature=0.0,
            max_tokens=4096,
            context_window=8192,
        )
    
    def _execute_model(
        self,
        model,
        prompt_data: DRPPrompt,
        retriever,
    ) -> DRPResponse:
        """Execute the model and return raw response"""
        try:
            # Call the model
            output = model(prompt_data.prompt_text)
            
            return DRPResponse(
                response_text=output.get("response", str(output)),
                finish_reason=output.get("done_reason", "stop"),
                model_used=getattr(model, 'name', 'unknown'),
                raw_output=output,
            )
        except Exception as e:
            return DRPResponse(
                response_text=f"Error: {str(e)}",
                finish_reason="error",
                model_used=getattr(model, 'name', 'unknown'),
                raw_output={"error": str(e)},
            )
    
    def _verify_citations(
        self,
        response: DRPResponse,
        retriever,
    ) -> List[DRPCitation]:
        """Verify citations in the response"""
        # This would integrate with deterministic.py
        # For now, return empty list
        return []


# =============================================================================
# DRP QUERY UTILITY
# =============================================================================

def create_drp_package(
    query: str,
    context_chunks: List[Dict],
    model_response: str,
    model_info: Dict[str, Any],
    output_dir: str = "/var/log/cortex/drp",
    compliance_standards: Optional[List[str]] = None,
    key_manager = None,
) -> str:
    """
    Simple utility to create a DRP package from query/response data.
    
    Usage:
        package_id = create_drp_package(
            query="What is the safety class?",
            context_chunks=[{"content": "...", "score": 0.95}],
            model_response="The safety class is A.",
            model_info={"model": "llama3", "version": "1.0"},
        )
    """
    config = DRPConfig(storage_path=output_dir)
    if key_manager:
        config.key_manager = key_manager
    
    writer = DRPWriter(config)
    
    package_id = writer.create_package(
        compliance_standards=compliance_standards or ["IEC_62304"]
    )
    
    # Write prompt
    prompt = DRPPrompt(
        prompt_text=query,
        token_count=len(query.split()),
    )
    writer.write_prompt(package_id, prompt)
    
    # Write context
    chunks = [
        DRPContextChunk(
            chunk_id=f"chunk_{i}",
            source_path=c.get("path", "unknown"),
            source_title=c.get("title", "Unknown"),
            chunk_text=c.get("content", "")[:500],
            relevance_score=c.get("score", 0.0),
            rank=i + 1,
            retrieval_method=c.get("method", "unknown"),
        )
        for i, c in enumerate(context_chunks)
    ]
    writer.write_context_chunks(package_id, chunks)
    
    # Write model info
    info = DRPModelInfo(**model_info)
    writer.write_model_info(package_id, info)
    
    # Write response
    resp = DRPResponse(
        response_text=model_response,
        finish_reason="stop",
        model_used=model_info.get("model_name", "unknown"),
    )
    writer.write_response(package_id, resp)
    
    # Finalize
    summary = writer.finalize_package(package_id)
    
    return summary["path"]


# =============================================================================
# DRP RETENTION MANAGER
# =============================================================================

class DRPRetentionManager:
    """
    Manages DRP retention policies.
    
    FDA 21 CFR Part 11 requires records to be retained for
    at least the lifetime of the device, plus 2 years.
    
    IEC 62304 requires records for the system lifetime.
    """
    
    def __init__(self, config: DRPConfig):
        self.config = config
    
    def cleanup_expired(self) -> Dict[str, Any]:
        """
        Remove packages older than retention period.
        
        Returns:
            Dict with cleanup statistics
        """
        cutoff = time.time() - (self.config.retention_days * 86400)
        removed = 0
        errors = 0
        
        try:
            for year_dir in self.config.storage_path.iterdir():
                if not year_dir.is_dir():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        
                        # Check if directory is older than retention
                        mtime = day_dir.stat().st_mtime
                        if mtime < cutoff:
                            if self.config.retention_policy == "delete":
                                try:
                                    shutil.rmtree(day_dir)
                                    removed += 1
                                except Exception as e:
                                    logger.error(f"cleanup_error path={day_dir} error={e}")
                                    errors += 1
                            elif self.config.retention_policy == "archive":
                                # Could implement archiving here
                                pass
        
        except Exception as e:
            logger.error(f"cleanup_failed error={e}")
        
        return {
            "removed_packages": removed,
            "errors": errors,
            "cutoff_days": self.config.retention_days,
        }
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics"""
        total_size = 0
        total_files = 0
        package_count = 0
        
        try:
            for year_dir in self.config.storage_path.iterdir():
                if not year_dir.is_dir():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        
                        package_count += 1
                        
                        for file_path in day_dir.rglob("*"):
                            if file_path.is_file():
                                total_size += file_path.stat().st_size
                                total_files += 1
        
        except Exception as e:
            logger.error(f"stats_collection_failed error={e}")
        
        return {
            "total_packages": package_count,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "storage_path": str(self.config.storage_path),
            "retention_days": self.config.retention_days,
        }