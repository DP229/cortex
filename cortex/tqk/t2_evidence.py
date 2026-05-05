"""
T2 Evidence Collector  -  Signed Qualification Evidence Package

Collects all qualification artifacts (TOR, TVP, TVR) into a single
signed evidence package for regulatory submission.

Evidence structure:
  {
    "manifest": { "version": "1.0.0", "generated_at": "...", "sil_target": "..." },
    "hashes": { "tor_hash": "...", "tvp_hash": "...", "tvr_hash": "..." },
    "files": [ { "name": "...", "hash": "...", "size_bytes": N } ],
    "signature": { "algorithm": "HMAC-SHA256", "signature": "...", "key_version": 1 },
  }
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
import logging
import shutil

from cortex.deterministic_core import compute_hash, ComplianceResult, ModuleVersion, hmac_safe_compare
from cortex.contracts import behavioral_contract

logger = logging.getLogger("cortex.t2.evidence")


@dataclass
class EvidenceFile:
    name: str
    content_type: str
    content: Any
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = compute_hash(self.content)

    def size_bytes(self) -> int:
        serialized = json.dumps(self.content, sort_keys=True, default=str)
        return len(serialized.encode("utf-8"))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "content_type": self.content_type,
            "hash": self.hash,
            "size_bytes": self.size_bytes(),
        }


@dataclass
class T2EvidenceManifest:
    version: str
    generated_at: str
    sil_target: str
    run_id: str
    evidence_count: int
    total_size_bytes: int
    file_hashes: Dict[str, str]
    package_hash: str
    qualified: bool
    grade: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class T2EvidenceSignature:
    algorithm: str = "HMAC-SHA256"
    signature: str = ""
    key_version: int = 1
    key_id: str = ""
    signed_at: str = ""
    manifest_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SignedT2Evidence:
    manifest: T2EvidenceManifest
    files: List[EvidenceFile]
    signature: T2EvidenceSignature
    raw_json: str = ""

    def to_json(self) -> str:
        signature_data = self.signature.to_dict()
        signature_data.pop("manifest_hash", None)
        return json.dumps({
            "manifest": self.manifest.to_dict(),
            "files": [f.to_dict() for f in self.files],
            "signature": signature_data,
        }, indent=2, sort_keys=True)

    def to_evidence(self) -> dict:
        return json.loads(self.to_json())


class EvidenceCollector:
    MODULE = "cortex.t2.evidence_collector"
    VERSION = ModuleVersion(major=1, minor=0, patch=0)

    def __init__(self, output_dir: str = ""):
        if not output_dir:
            output_dir = os.path.join(os.getcwd(), ".cortex", "evidence")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @behavioral_contract(
        invariants=[
            lambda r: r is not None,
            lambda r: len(r.signature.signature) > 0,
        ],
    )
    def collect_and_sign(
        self,
        evidence_package,
        signing_key: Optional[bytes] = None,
    ) -> SignedT2Evidence:
        files: List[EvidenceFile] = []

        tor_dict = evidence_package.tor.to_dict()
        files.append(EvidenceFile(name="tor.json", content_type="application/json", content=tor_dict))

        tvp_dict = evidence_package.tvp.to_dict()
        files.append(EvidenceFile(name="tvp.json", content_type="application/json", content=tvp_dict))

        tvr_dict = evidence_package.tvr.to_dict()
        files.append(EvidenceFile(name="tvr.json", content_type="application/json", content=tvr_dict))

        evidence_dict = evidence_package.to_evidence()
        files.append(EvidenceFile(name="evidence.json", content_type="application/json", content=evidence_dict))

        file_hashes = {f.name: f.hash for f in files}
        total_size = sum(f.size_bytes() for f in files)

        manifest = T2EvidenceManifest(
            version="1.0.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            sil_target=evidence_package.sil_target,
            run_id=evidence_package.run_id,
            evidence_count=len(files),
            total_size_bytes=total_size,
            file_hashes=file_hashes,
            package_hash=evidence_package.package_hash,
            qualified=evidence_package.is_t2_qualified,
            grade=evidence_package.qualification_grade,
        )

        manifest_hash = compute_hash(manifest.to_dict())
        signature = T2EvidenceSignature(
            manifest_hash=manifest_hash,
            signed_at=datetime.now(timezone.utc).isoformat(),
            key_id=f"key_{uuid.uuid4().hex[:8]}",
        )

        if signing_key is None:
            signing_key = hashlib.sha256(b"cortex_t2_default_signing_key").digest()

        sig_value = hmac_mod.new(
            signing_key,
            manifest_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        signature.signature = sig_value

        signed = SignedT2Evidence(
            manifest=manifest,
            files=files,
            signature=signature,
        )
        signed.raw_json = signed.to_json()

        output_path = self.output_dir / f"evidence_{signed.manifest.run_id}.json"
        output_path.write_text(signed.raw_json, encoding="utf-8")

        logger.info("evidence_signed", extra={
            "run_id": signed.manifest.run_id,
            "package_hash": signed.manifest.package_hash[:16],
            "qualified": signed.manifest.qualified,
        })

        return signed

    @classmethod
    def verify_evidence(cls, signed: SignedT2Evidence, signing_key: Optional[bytes] = None) -> Tuple[bool, str]:
        manifest_hash = compute_hash(signed.manifest.to_dict())
        if manifest_hash != signed.signature.manifest_hash:
            return False, "Manifest hash mismatch"

        if signing_key is None:
            signing_key = hashlib.sha256(b"cortex_t2_default_signing_key").digest()

        expected_sig = hmac_mod.new(
            signing_key,
            manifest_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac_safe_compare(expected_sig, signed.signature.signature):
            return False, "Signature verification failed"

        for f in signed.files:
            actual_hash = compute_hash(f.content)
            expected_hash = signed.manifest.file_hashes.get(f.name, "")
            if actual_hash != expected_hash:
                return False, f"File hash mismatch: {f.name}"

        return True, "Evidence package verified"

    @classmethod
    def verify_from_json(cls, json_content: str, signing_key: Optional[bytes] = None) -> Tuple[bool, str]:
        data = json.loads(json_content)
        try:
            manifest = T2EvidenceManifest(**data["manifest"])
            sig_data = data["signature"]
            recomputed_manifest_hash = compute_hash(manifest.to_dict())
            if signing_key is None:
                signing_key = hashlib.sha256(b"cortex_t2_default_signing_key").digest()
            computed_sig = hmac_mod.new(signing_key, recomputed_manifest_hash.encode("utf-8"), hashlib.sha256).hexdigest()
            expected_sig = sig_data["signature"]
            if not hmac_safe_compare(computed_sig, expected_sig):
                return False, "Signature verification failed"
            return True, "Evidence package verified"
        except (KeyError, TypeError) as exc:
            return False, f"Invalid evidence structure: {exc}"
