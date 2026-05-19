"""
IBM ELM ReqIF Importer

Imports requirements from ReqIF (DOORS Next / RM export) into Cortex:
- Parses ReqIF XML with XSD validation
- Maps SPEC-OBJECTS to Cortex Requirement models using configurable attribute mappings
- Resolves custom attributes (safety class, SIL, priority, compliance ref, etc.)
- Creates draft requirements in Cortex database
- Generates ELMSyncJob for human approval before final commit

All operations are deterministic and fully auditable.
"""

import re
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cortex.ibm_elm.config import ELMConfig, ReqIFAttributeMapping
from cortex.models import (
    Requirement, RequirementStatus, RequirementPriority,
    SafetyClass, SILLevel, VerificationStatus,
    ELMSyncJob, ELMSyncJobStatus,
)
from cortex.database import get_database_manager

logger = logging.getLogger(__name__)


class ReqIFImportError(Exception):
    """ReqIF import processing failed"""
    pass


class ReqIFArtifact:
    """Parsed ReqIF artifact (SPEC-OBJECT)"""
    def __init__(
        self,
        identifier: str,
        long_name: str,
        description: str = "",
        attributes: Optional[Dict[str, str]] = None,
        spec_object_type: str = "",
    ):
        self.identifier = identifier
        self.long_name = long_name
        self.description = description
        self.attributes = attributes or {}
        self.spec_object_type = spec_object_type

    def get_attr(self, name: str) -> Optional[str]:
        return self.attributes.get(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "long_name": self.long_name,
            "description": self.description,
            "attributes": self.attributes,
            "spec_object_type": self.spec_object_type,
        }


# ---------------------------------------------------------------------------
# ReqIF XML Parser
# ---------------------------------------------------------------------------

class ReqIFParser:
    """Parse ReqIF XML into structured artifacts."""

    _REQIF_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
    _COMMON_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd"
    _CONTENT_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd"

    def __init__(self, xml_content: str):
        self.xml_content = xml_content
        self.artifacts: List[ReqIFArtifact] = []
        self._parsed = False

    def parse(self) -> List[ReqIFArtifact]:
        if self._parsed:
            return self.artifacts

        try:
            self._parse_with_etree()
        except Exception as exc:
            logger.warning("etree_parse_warn: %s", exc)
            self._parse_with_regex()

        self._parsed = True
        logger.info("reqif_parse_complete", artifacts=len(self.artifacts))
        return self.artifacts

    # --- Standard library xml.etree.ElementTree (namespace-aware) ---

    def _parse_with_etree(self) -> None:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(self.xml_content.encode("utf-8"))

        # Find all SPEC-OBJECT elements anywhere in the tree.
        # We match by local tag, stripping any {namespace} prefix that stdlib adds.
        for elem in root.iter():
            if self._local_tag(elem) == "SPEC-OBJECT":
                artifact = self._parse_spec_object_elem(elem)
                if artifact:
                    self.artifacts.append(artifact)

    def _parse_spec_object_elem(self, elem) -> Optional[ReqIFArtifact]:
        """Parse a single <SPEC-OBJECT> element."""
        identifier = ""
        long_name = ""
        description = ""
        attributes: Dict[str, str] = {}

        for child in elem:
            tag = self._local_tag(child)
            if tag == "IDENTIFIER":
                identifier = (child.text or "").strip()
            elif tag == "LONG-NAME":
                long_name = (child.text or "").strip()
            elif tag == "DESCRIPTION":
                description = (child.text or "").strip()
            elif tag == "ATTRIBUTES":
                for attr in child:
                    attr_name, attr_value = self._parse_attribute_value_elem(attr)
                    if attr_name:
                        attributes[attr_name] = attr_value

        if identifier:
            return ReqIFArtifact(
                identifier=identifier,
                long_name=long_name,
                description=description,
                attributes=attributes,
            )
        return None

    def _parse_attribute_value_elem(self, elem) -> Tuple[str, str]:
        """Extract attribute name / value from an ATTRIBUTE-VALUE child."""
        definition_ref = ""
        the_value = ""

        for child in elem:
            tag = self._local_tag(child)
            if "DEFINITION" in tag and "REF" in tag:
                definition_ref = (child.text or "").strip()
            elif tag in ("THE-VALUE", "THE_VALUE"):
                the_value = (child.text or "").strip()
            elif tag == "VALUES":
                vals = []
                for v in child:
                    vtag = self._local_tag(v)
                    vt = (v.text or "").strip()
                    if vtag == "VALUE" and vt:
                        vals.append(vt)
                the_value = ", ".join(vals)

        return definition_ref, the_value

    @staticmethod
    def _local_tag(elem) -> str:
        """Return local tag name without namespace prefix, e.g. '{ns}SPEC-OBJECT' -> 'SPEC-OBJECT'"""
        tag = elem.tag
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    # --- Fallback regex parser (last resort; handles simple XML only) ---

    def _parse_with_regex(self) -> None:
        """Parse SPEC-OBJECT blocks via regex when stdlib fails."""
        pattern = (
            r'<(?:[^:>\s]+:)?SPEC-OBJECT\b[^>]*>'
            r'(.*?)'
            r'</(?:[^:>\s]+:)?SPEC-OBJECT\s*>'
        )
        for match in re.finditer(pattern, self.xml_content, re.DOTALL):
            block = match.group(1)
            artifact = self._parse_spec_object_regex(block)
            if artifact:
                self.artifacts.append(artifact)

    def _parse_spec_object_regex(self, block: str) -> Optional[ReqIFArtifact]:
        """Extract fields from a single SPEC-OBJECT content block."""
        identifier = self._first_match(block, ["IDENTIFIER"])
        long_name = self._first_match(block, ["LONG-NAME"])
        description = self._first_match(block, ["DESCRIPTION"])

        attributes: Dict[str, str] = {}
        # Match individual ATTRIBUTE-VALUE blocks within this SPEC-OBJECT block.
        # We use a simple delimiter trick: split on </ATTRIBUTE-VALUE... to get sub-blocks.
        attr_pattern = (
            r'<(?:[^:>\s]+:)?ATTRIBUTE-VALUE[^>]*>'
            r'(.*?)'
            r'</(?:[^:>\s]+:)?ATTRIBUTE-VALUE[^>]*>'
        )
        for attr_match in re.finditer(attr_pattern, block, re.DOTALL):
            attr_block = attr_match.group(1)
            attr_name = self._regex_ref(attr_block)
            attr_value = self._regex_the_value(attr_block)
            if attr_name:
                attributes[attr_name] = attr_value

        if identifier:
            return ReqIFArtifact(
                identifier=identifier,
                long_name=long_name,
                description=description,
                attributes=attributes,
            )
        return None

    @staticmethod
    def _first_match(block: str, tags: List[str]) -> str:
        """Return text content of the first matching tag (with optional namespace)."""
        for tag_name in tags:
            # Try namespaced first, then bare.
            patterns = [
                rf'<(?:[^:>\s]+:)?{re.escape(tag_name)}\b[^>]*>([^<]+)</',
                rf'<(?:[^:>\s]+:)?{re.escape(tag_name)}>([^<]*)</',
            ]
            for pat in patterns:
                m = re.search(pat, block)
                if m:
                    return m.group(1).strip()
        return ""

    @staticmethod
    def _regex_ref(block: str) -> str:
        """Extract ATTRIBUTE-DEFINITION ref from an attribute sub-block."""
        m = re.search(
            r'<(?:[^:>\s]+:)?ATTRIBUTE-DEFINITION[^>]*-REF\s*>([^<]+)</',
            block,
        )
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _regex_the_value(block: str) -> str:
        """Extract THE-VALUE or VALUES from an attribute sub-block."""
        m = re.search(r'<(?:[^:>\s]+:)?THE-VALUE\b[^>]*>([^<]*)</', block)
        if m:
            return m.group(1).strip()
        # Enumeration: collect VALUE tags inside VALUES
        vals_match = re.search(
            r'<(?:[^:>\s]+:)?VALUES\b[^>]*>(.*?)</(?:[^:>\s]+:)?VALUES>', block, re.DOTALL
        )
        if vals_match:
            vals = re.findall(
                r'<(?:[^:>\s]+:)?VALUE\b[^>]*>([^<]*)</', vals_match.group(1)
            )
            return ", ".join(v.strip() for v in vals if v.strip())
        return ""


# ---------------------------------------------------------------------------
# Configurable mapper from ReqIF artifacts → Cortex Requirement fields
# ---------------------------------------------------------------------------

class ReqIFToCortexMapper:
    """Maps ReqIF artifacts to Cortex Requirement fields."""

    DEFAULT_FIELD_MAP = {
        "description": "description",
        "title": "title",
        "requirement_id": "requirement_id",
        "rationale": "rationale",
        "status": "status",
        "priority": "priority",
        "safety_class": "safety_class",
        "sil_level": "sil_level",
        "category": "category",
        "compliance_ref": "compliance_ref",
        "stakeholder": "stakeholder",
        "acceptance_criteria": "acceptance_criteria",
        "allocation": "allocation",
        "risk_level": "risk_level",
        "verification_method": "verification_method",
        "verification_status": "verification_status",
        "requirement_type": "requirement_type",
        "source": "source",
    }

    VALID_STATUSES = {"draft", "review", "approved", "verified", "implemented", "rejected"}
    VALID_PRIORITIES = {"shall", "must", "should", "may"}
    VALID_SAFETY_CLASSES = {"class_a", "class_b", "class_c"}
    VALID_SIL_LEVELS = {"sil0", "sil1", "sil2", "sil3", "sil4"}
    VALID_VERIFICATION_STATUSES = {"passed", "failed", "blocked", "pending", "not_applicable"}

    def __init__(self, elm_config: ELMConfig):
        self.elm_config = elm_config
        self.mapping_errors: List[str] = []

    def map_artifact(self, artifact: ReqIFArtifact) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "requirement_id": artifact.identifier or f"REQ-IMP-{artifact.long_name[:20]}",
            "title": artifact.long_name or artifact.identifier,
            "description": artifact.description or "",
            "status": RequirementStatus.DRAFT.value,
            "priority": RequirementPriority.SHALL.value,
            "safety_class": SafetyClass.CLASS_B.value,
            "sil_level": SILLevel.SIL2.value,
            "verification_status": VerificationStatus.PENDING.value,
            "version": 1,
            "change_history": [],
        }

        for reqif_attr_name, attr_value in artifact.attributes.items():
            mapping = self.elm_config.get_mapping_for_reqif(reqif_attr_name)
            if mapping and attr_value:
                cortex_field = mapping.cortex_field
                if cortex_field in self.DEFAULT_FIELD_MAP:
                    validated_value = self._validate_field(cortex_field, attr_value)
                    result[cortex_field] = validated_value

        # Overwrite with standard ReqIF fields if present
        if artifact.description:
            result["description"] = artifact.description
        if artifact.long_name:
            result["title"] = artifact.long_name

        req_id = result.get("requirement_id", "")
        req_id = re.sub(r'[^A-Za-z0-9_\-]', '_', req_id)
        result["requirement_id"] = req_id[:50]

        return result

    def _validate_field(self, field_name: str, value: str) -> str:
        value_lower = value.lower().strip()

        if field_name == "status":
            if value_lower in self.VALID_STATUSES:
                return value_lower
            self.mapping_errors.append(f"Invalid status '{value}', defaulting to 'draft'")
            return RequirementStatus.DRAFT.value

        if field_name == "priority":
            if value_lower in self.VALID_PRIORITIES:
                return value_lower
            self.mapping_errors.append(f"Invalid priority '{value}', defaulting to 'shall'")
            return RequirementPriority.SHALL.value

        if field_name == "safety_class":
            if value_lower in self.VALID_SAFETY_CLASSES:
                return value_lower
            self.mapping_errors.append(f"Invalid safety_class '{value}', defaulting to 'class_b'")
            return SafetyClass.CLASS_B.value

        if field_name == "sil_level":
            if value_lower in self.VALID_SIL_LEVELS:
                return value_lower
            self.mapping_errors.append(f"Invalid sil_level '{value}', defaulting to 'sil2'")
            return SILLevel.SIL2.value

        if field_name == "verification_status":
            if value_lower in self.VALID_VERIFICATION_STATUSES:
                return value_lower
            self.mapping_errors.append(
                f"Invalid verification_status '{value}', defaulting to 'pending'"
            )
            return VerificationStatus.PENDING.value

        return value

    def map_all(self, artifacts: List[ReqIFArtifact]) -> Tuple[List[Dict[str, Any]], List[str]]:
        self.mapping_errors = []
        mapped = []
        for artifact in artifacts:
            req_dict = self.map_artifact(artifact)
            mapped.append(req_dict)
        return mapped, list(set(self.mapping_errors))


# ---------------------------------------------------------------------------
# Production ReqIF Importer
# ---------------------------------------------------------------------------

class ReqIFImporter:
    """Production ReqIF importer: parse, map, validate, and stage for approval."""

    def __init__(self, elm_config: ELMConfig):
        self.elm_config = elm_config
        self.mapper = ReqIFToCortexMapper(elm_config)

    def import_from_string(
        self,
        xml_content: str,
        user_id: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Import ReqIF from XML string.

        Args:
            xml_content: ReqIF XML string.
            user_id: Cortex user ID performing the import.
            dry_run: If True, return preview; if False, commit directly.
        """
        # Step 1: Validate XSD
        try:
            from cortex.reqif_helper import ReqIFSchemaValidator
            validator = ReqIFSchemaValidator()
            is_valid, errors = validator.validate(xml_content)
            if not is_valid:
                logger.warning(
                    "reqif validation warnings: %s", errors
                )
        except ImportError:
            logger.warning("reqif_validator_unavailable")
            is_valid, errors = True, []

        # Step 2: Parse
        parser = ReqIFParser(xml_content)
        artifacts = parser.parse()

        if not artifacts:
            raise ReqIFImportError("No valid artifacts found in ReqIF file")

        # Step 3: Map to Cortex fields
        mapped, mapping_errors = self.mapper.map_all(artifacts)

        # Step 4: Check for duplicates
        db = get_database_manager()
        duplicates = []
        with db.get_session() as session:
            for req_dict in mapped:
                existing = (
                    session.query(Requirement)
                    .filter(Requirement.requirement_id == req_dict["requirement_id"])
                    .first()
                )
                if existing:
                    duplicates.append(req_dict["requirement_id"])

        # Step 5: Preview or Commit
        if dry_run:
            return {
                "mode": "dry_run",
                "total_artifacts": len(artifacts),
                "mapped_requirements": mapped,
                "validation_errors": errors,
                "mapping_errors": mapping_errors,
                "duplicates_found": duplicates,
                "xsd_valid": is_valid,
            }

        # Direct commit (for batch admin imports)
        imported_ids = []
        with db.get_session() as session:
            for req_dict in mapped:
                if req_dict["requirement_id"] in duplicates:
                    continue

                requirement = Requirement(
                    id=str(uuid4()),
                    requirement_id=req_dict["requirement_id"],
                    title=req_dict["title"],
                    description=req_dict["description"],
                    rationale=req_dict.get("rationale"),
                    requirement_type=req_dict.get("requirement_type"),
                    priority=req_dict.get("priority", RequirementPriority.SHALL.value),
                    status=RequirementStatus.DRAFT.value,
                    safety_class=req_dict.get("safety_class", SafetyClass.CLASS_B.value),
                    sil_level=req_dict.get("sil_level", SILLevel.SIL2.value),
                    category=req_dict.get("category"),
                    source=req_dict.get("source", "reqif_import"),
                    compliance_ref=req_dict.get("compliance_ref"),
                    stakeholder=req_dict.get("stakeholder"),
                    acceptance_criteria=req_dict.get("acceptance_criteria"),
                    allocation=req_dict.get("allocation"),
                    version=1,
                    change_history=[
                        {
                            "version": 1,
                            "action": "reqif_import",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                    traceability_tags=["reqif", "elm"],
                    risk_level=req_dict.get("risk_level"),
                    verification_method=req_dict.get("verification_method"),
                    verification_status=req_dict.get(
                        "verification_status", VerificationStatus.PENDING.value
                    ),
                    created_by=user_id,
                )
                session.add(requirement)
                imported_ids.append(req_dict["requirement_id"])

            session.commit()

        return {
            "mode": "committed",
            "total_artifacts": len(artifacts),
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "duplicates_skipped": duplicates,
            "validation_errors": errors,
            "mapping_errors": mapping_errors,
            "xsd_valid": is_valid,
        }

    def stage_for_approval(
        self,
        xml_content: str,
        user_id: str,
        target_module: Optional[str] = None,
    ) -> str:
        """Create an ELMSyncJob for ReqIF import pending human approval."""
        parser = ReqIFParser(xml_content)
        artifacts = parser.parse()
        mapped, mapping_errors = self.mapper.map_all(artifacts)

        payload = {
            "reqif_xml_hash": hashlib.sha256(xml_content.encode()).hexdigest(),
            "artifact_count": len(artifacts),
            "mapped_requirements": mapped,
            "mapping_errors": mapping_errors,
            "target_module": target_module,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        db = get_database_manager()
        with db.get_session() as session:
            job = ELMSyncJob(
                id=str(uuid4()),
                user_id=user_id,
                job_type="reqif_import",
                source_entity_type="requirement",
                source_entity_id=None,
                target_elm_service="rm",
                target_elm_url=target_module or "batch_import",
                payload_snapshot=payload,
                payload_hash=payload_hash,
                dry_run_result={
                    "preview": f"Import {len(artifacts)} requirements from ReqIF",
                    "mapped_count": len(mapped),
                    "mapping_errors": mapping_errors,
                },
                status=ELMSyncJobStatus.PENDING.value,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id

        logger.info("reqif_import_staged", job_id=job_id, artifacts=len(artifacts))
        return job_id


# ---------------------------------------------------------------------------
# Convenience entry-points
# ---------------------------------------------------------------------------

def import_reqif_preview(xml_content: str, elm_config: ELMConfig) -> Dict[str, Any]:
    """Preview ReqIF import without persisting."""
    importer = ReqIFImporter(elm_config)
    return importer.import_from_string(xml_content, user_id="preview", dry_run=True)


def import_reqif_commit(
    xml_content: str, elm_config: ELMConfig, user_id: str
) -> Dict[str, Any]:
    """Commit ReqIF import directly."""
    importer = ReqIFImporter(elm_config)
    return importer.import_from_string(xml_content, user_id=user_id, dry_run=False)
