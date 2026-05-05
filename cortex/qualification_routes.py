"""
Cortex Qualification API Routes  -  T2 Tool Qualification Endpoints

Provides REST endpoints for self-qualification:
  POST /v2/qualification/run    - Execute T2 qualification
  GET  /v2/qualification/status - Get last run status
  GET  /v2/qualification/tor    - Get TOR document (markdown)
  GET  /v2/qualification/tvp    - Get TVP document (markdown)
  GET  /v2/qualification/tvr    - Get TVR document (markdown)
  GET  /v2/qualification/evidence - Get signed evidence package (JSON)
  POST /v2/qualification/verify   - Verify evidence package signature
"""

from fastapi import APIRouter, HTTPException, Query, Request, status as http_status
import logging

from cortex.tqk.t2_qualifier import QualificationEngine, T2EvidencePackage
from cortex.tqk.t2_evidence import EvidenceCollector

router = APIRouter(prefix="/v2/qualification", tags=["qualification"])

logger = logging.getLogger("cortex.api.qualification")

_engine = None


def _get_engine() -> QualificationEngine:
    global _engine
    if _engine is None:
        _engine = QualificationEngine()
    return _engine


@router.post("/run", status_code=http_status.HTTP_200_OK)
async def run_qualification(
    sil_target: str = Query("SIL2", description="Target SIL level (SIL0-SIL4)"),
    request: Request = None,
) -> dict:
    engine = _get_engine()
    try:
        evidence = engine.qualify(sil_target=sil_target.upper())
        collector = EvidenceCollector()
        signed = collector.collect_and_sign(evidence)

        return {
            "status": "ok",
            "qualification_status": evidence.tvr.qualification_status,
            "grade": evidence.qualification_grade,
            "is_t2_qualified": evidence.is_t2_qualified,
            "package_hash": evidence.package_hash,
            "run_id": evidence.run_id,
            "tor_hash": evidence.run_metadata.get("tor_hash", ""),
            "tvp_hash": evidence.run_metadata.get("tvp_hash", ""),
            "tvr_hash": evidence.run_metadata.get("tvr_hash", ""),
            "test_count": evidence.run_metadata.get("test_count", 0),
            "pass_count": evidence.run_metadata.get("pass_count", 0),
            "fail_count": evidence.run_metadata.get("fail_count", 0),
            "sil_target": sil_target.upper(),
            "sil_validated": evidence.run_metadata.get("sil_validated", False),
            "evidence_signature": signed.signature.signature[:16] + "...",
        }
    except Exception as exc:
        logger.error("qualification_run_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def qualification_status() -> dict:
    engine = _get_engine()
    last = engine.get_last_run()
    if last is None:
        return {"status": "not_executed"}
    return {
        "status": last.qualification_status,
        "run_id": last.run_id,
        "overall_result": last.overall_result,
        "test_count": last.test_count,
        "pass_count": last.pass_count,
        "fail_count": last.fail_count,
        "sil_validated": last.sil_validated,
    }


@router.get("/tor")
async def get_tor_document(format: str = Query("markdown", description="Output format: markdown or json")) -> dict:
    engine = _get_engine()
    last = engine.get_last_run()
    if last is None:
        engine = QualificationEngine()
        evidence = engine.qualify(sil_target="SIL2")
    else:
        engine._qualify_silent("SIL2")  # regenerate for display
        global _engine
        _engine = QualificationEngine()
        evidence = _engine.qualify(sil_target="SIL2")

    return {
        "format": format,
        "content": evidence.tor_markdown(),
        "hash": evidence.run_metadata.get("tor_hash", ""),
    }


@router.get("/tvp")
async def get_tvp_document(format: str = Query("markdown", description="Output format: markdown or json")) -> dict:
    engine = _get_engine()
    evidence = engine.qualify(sil_target="SIL2")
    return {
        "format": format,
        "content": evidence.tvp_markdown(),
        "hash": evidence.run_metadata.get("tvp_hash", ""),
    }


@router.get("/tvr")
async def get_tvr_document(format: str = Query("markdown", description="Output format: markdown or json")) -> dict:
    engine = _get_engine()
    evidence = engine.qualify(sil_target="SIL2")
    return {
        "format": format,
        "content": evidence.tvr_markdown(),
        "hash": evidence.run_metadata.get("tvr_hash", ""),
    }


@router.get("/evidence")
async def get_evidence_package() -> dict:
    engine = QualificationEngine()
    evidence = engine.qualify(sil_target="SIL2")
    collector = EvidenceCollector()
    signed = collector.collect_and_sign(evidence)
    return signed.to_evidence()


@router.post("/verify")
async def verify_evidence_package(evidence_json: dict) -> dict:
    import json
    try:
        json_str = json.dumps(evidence_json, sort_keys=True)
        ok, msg = EvidenceCollector.verify_from_json(json_str)
        return {"valid": ok, "message": msg}
    except Exception as exc:
        return {"valid": False, "message": f"Verification error: {exc}"}
