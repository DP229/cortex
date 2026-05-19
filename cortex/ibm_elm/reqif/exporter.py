"""
IBM ELM ReqIF Exporter

Exports Cortex requirements to ReqIF format for import into DOORS Next / RM:
- Queries Cortex Requirement database
- Maps fields to ReqIF standard + custom attributes
- Generates validated ReqIF XML using existing ReqIFExporter infrastructure
- Supports filtering by requirement IDs, status, or asset
"""

import io
import json
import hashlib
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from cortex.database import get_database_manager
from cortex.models import Requirement, RequirementCitation
from cortex.reqif_helper import ReqIFExporter, ReqIFValidationError
from cortex.ibm_elm.config import ELMConfig

logger = logging.getLogger(__name__)


class CortexToReqIFExporter:
    """
    Export Cortex requirements to ReqIF XML.
    Wraps and extends the existing ReqIFExporter from reqif_helper.py.
    """

    def __init__(self, elm_config: ELMConfig):
        self.elm_config = elm_config
        self._reqif_exporter = ReqIFExporter(
            tool_name="Cortex ELM Connector",
            tool_vendor="Cortex",
            tool_version="1.0",
            validate=True,
        )

    def export_requirements(
        self,
        requirement_ids: Optional[List[str]] = None,
        status_filter: Optional[str] = None,
        asset_id: Optional[str] = None,
        include_citations: bool = True,
    ) -> str:
        """
        Export selected requirements to ReqIF XML string.

        Args:
            requirement_ids: Specific requirement IDs to export (None = all)
            status_filter: Filter by status (e.g., 'approved')
            asset_id: Filter by linked asset UUID
            include_citations: Include traceability links as SPEC-RELATIONS

        Returns:
            ReqIF XML string
        """
        db = get_database_manager()

        with db.get_session() as session:
            query = session.query(Requirement)

            if requirement_ids:
                query = query.filter(Requirement.requirement_id.in_(requirement_ids))
            if status_filter:
                query = query.filter(Requirement.status == status_filter)
            if asset_id:
                query = query.filter(Requirement.asset_id == asset_id)

            requirements = query.limit(self.elm_config.max_sync_batch).all()

            if not requirements:
                logger.warning("reqif_export_no_requirements_found")
                return self._generate_empty_reqif()

            # Build scan_results dict for ReqIFExporter
            scan_results = {
                "requirements": [],
                "test_cases": [],
                "trace_links": [],
            }

            for req in requirements:
                req_dict = self._requirement_to_reqif_dict(req)
                scan_results["requirements"].append(req_dict)

                # Add citations as trace links
                if include_citations:
                    citations = session.query(RequirementCitation).filter(
                        RequirementCitation.source_requirement_id == req.id
                    ).all()
                    for c in citations:
                        target = session.query(Requirement).filter(
                            Requirement.id == c.target_requirement_id
                        ).first()
                        if target:
                            scan_results["trace_links"].append({
                                "source_id": req.requirement_id,
                                "source_type": "requirement",
                                "target_id": target.requirement_id,
                                "target_type": "requirement",
                                "link_type": c.citation_type,
                                "file_path": f"db://citations/{c.id}",
                                "line_number": 0,
                            })

        # Generate ReqIF XML
        try:
            xml_content = self._reqif_exporter.to_string(
                scan_results,
                spec_object_type_name="CortexRequirement",
                spec_relation_type_name="Verifies",
            )
            logger.info("reqif_export_success", requirements=len(requirements))
            return xml_content
        except ReqIFValidationError as e:
            logger.error("reqif_export_validation_failed", errors=e.errors)
            raise
        except Exception as e:
            logger.error("reqif_export_failed", error=str(e))
            raise

    def _requirement_to_reqif_dict(self, req: Requirement) -> Dict[str, Any]:
        """Map Cortex Requirement to ReqIF-compatible dict"""
        # Build attributes dict using configured mappings
        attributes = {
            "type": req.requirement_type or req.category or "functional",
            "priority": req.priority or "shall",
            "safety_class": req.safety_class or "class_b",
            "file_path": f"cortex://requirements/{req.requirement_id}",
            "source": req.source or "cortex",
            "compliance_ref": req.compliance_ref or "",
            "allocation": req.allocation or "",
        }

        # Add custom attributes from mappings
        for mapping in self.elm_config.custom_attribute_mappings:
            # Get value from requirement
            value = getattr(req, mapping.cortex_field, None)
            if value:
                attributes[mapping.reqif_name] = value

        return {
            "req_id": req.requirement_id,
            "content": req.description or req.title or "",
            "type": req.requirement_type or req.category or "functional",
            "priority": req.priority or "shall",
            "safety_class": req.safety_class or "class_b",
            "file_path": f"cortex://requirements/{req.requirement_id}",
            "source": req.source or "cortex",
            "compliance_ref": req.compliance_ref or "",
            "allocation": req.allocation or "",
            "attributes": attributes,
        }

    def _generate_empty_reqif(self) -> str:
        """Generate minimal valid ReqIF with no requirements"""
        scan_results = {"requirements": [], "test_cases": [], "trace_links": []}
        return self._reqif_exporter.to_string(scan_results)


def export_requirements_to_reqif(
    elm_config: ELMConfig,
    requirement_ids: Optional[List[str]] = None,
    status_filter: Optional[str] = None,
) -> str:
    """Convenience function for single-call export"""
    exporter = CortexToReqIFExporter(elm_config)
    return exporter.export_requirements(
        requirement_ids=requirement_ids,
        status_filter=status_filter,
    )
