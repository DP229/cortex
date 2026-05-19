"""
IBM ELM Configuration - Secure, auditable connection settings

Provides:
- ELM server endpoint configuration (JTS, RM, CCM, QM, GCM)
- OIDC/OAuth authentication parameters
- Project area discovery settings
- ReqIF attribute mapping configuration
- Dry-run and batch-size controls

All secrets are stored via the key manager, not in YAML.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReqIFAttributeMapping:
    """Mapping from ReqIF custom attribute name to Cortex Requirement field"""
    reqif_name: str
    cortex_field: str
    data_type: str = "string"  # string, integer, boolean, enumeration
    enumeration_values: Optional[List[str]] = None


@dataclass
class ELMConfig:
    """IBM Engineering Lifecycle Management connector configuration"""

    # Master switch
    enabled: bool = False

    # Server URLs (auto-discovered from Root Services if base_url provided)
    base_url: Optional[str] = None          # e.g., https://elm.company.com:9443
    jts_url: Optional[str] = None          # Jazz Team Server
    rm_url: Optional[str] = None          # DOORS Next / RM
    ccm_url: Optional[str] = None         # EWM / CCM
    qm_url: Optional[str] = None          # ETM / QM
    gcm_url: Optional[str] = None         # Global Configuration Management

    # Project area (discovered dynamically if not set)
    project_area_name: Optional[str] = None
    project_area_uuid: Optional[str] = None

    # Authentication mode: oidc | oauth1a | basic | form
    auth_mode: str = "oidc"

    # OIDC settings (secrets managed via key manager)
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    # client_secret is NEVER stored here — loaded from key manager at runtime

    # OAuth 1.0a settings (fallback)
    oauth1a_consumer_key: Optional[str] = None
    # consumer_secret via key manager

    # Basic auth / Form auth (testing only, not for production)
    service_account_username: Optional[str] = None
    # password via key manager

    # TLS / Security
    verify_ssl: bool = True
    ca_bundle_path: Optional[str] = None

    # Operational settings
    dry_run_default: bool = True           # All writes require preview first
    max_sync_batch: int = 100
    request_timeout_seconds: int = 60
    max_retries: int = 3

    # ReqIF standard attribute mapping
    # These map ReqIF standard/custom attributes to Cortex Requirement fields
    reqif_attribute_mappings: List[ReqIFAttributeMapping] = field(default_factory=lambda: [
        ReqIFAttributeMapping("ReqIF.Text", "description", "string"),
        ReqIFAttributeMapping("ReqIF.Name", "title", "string"),
        ReqIFAttributeMapping("ReqIF.ChapterName", "title", "string"),
        ReqIFAttributeMapping("ReqIF.ForeignID", "requirement_id", "string"),
        ReqIFAttributeMapping("ReqIF.Comment", "rationale", "string"),
        ReqIFAttributeMapping("ReqIF.Status", "status", "string"),
    ])

    # Extended/custom attribute mappings for DOORS Next
    # Users can override these in config YAML
    custom_attribute_mappings: List[ReqIFAttributeMapping] = field(default_factory=lambda: [
        ReqIFAttributeMapping("dng:type", "requirement_type", "string"),
        ReqIFAttributeMapping("dng:priority", "priority", "string"),
        ReqIFAttributeMapping("dng:safetyClass", "safety_class", "string"),
        ReqIFAttributeMapping("dng:silLevel", "sil_level", "string"),
        ReqIFAttributeMapping("dng:category", "category", "string"),
        ReqIFAttributeMapping("dng:complianceRef", "compliance_ref", "string"),
        ReqIFAttributeMapping("dng:stakeholder", "stakeholder", "string"),
        ReqIFAttributeMapping("dng:acceptanceCriteria", "acceptance_criteria", "string"),
        ReqIFAttributeMapping("dng:allocation", "allocation", "string"),
        ReqIFAttributeMapping("dng:riskLevel", "risk_level", "string"),
        ReqIFAttributeMapping("dng:verificationMethod", "verification_method", "string"),
        ReqIFAttributeMapping("dng:verificationStatus", "verification_status", "string"),
    ])

    @classmethod
    def from_dict(cls, data: dict) -> "ELMConfig":
        """Create ELMConfig from dictionary (YAML deserialization)"""
        # Handle nested dataclasses manually
        reqif_maps = []
        for m in data.get("reqif_attribute_mappings", []):
            reqif_maps.append(ReqIFAttributeMapping(**m))
        custom_maps = []
        for m in data.get("custom_attribute_mappings", []):
            custom_maps.append(ReqIFAttributeMapping(**m))

        # Build kwargs, excluding the mapping lists which we handle above
        kwargs = {k: v for k, v in data.items()
                  if k not in ("reqif_attribute_mappings", "custom_attribute_mappings")}
        kwargs["reqif_attribute_mappings"] = reqif_maps if reqif_maps else cls().reqif_attribute_mappings
        kwargs["custom_attribute_mappings"] = custom_maps if custom_maps else cls().custom_attribute_mappings

        return cls(**kwargs)

    def to_dict(self) -> dict:
        """Serialize to dictionary (YAML-friendly) — secrets excluded"""
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "jts_url": self.jts_url,
            "rm_url": self.rm_url,
            "ccm_url": self.ccm_url,
            "qm_url": self.qm_url,
            "gcm_url": self.gcm_url,
            "project_area_name": self.project_area_name,
            "project_area_uuid": self.project_area_uuid,
            "auth_mode": self.auth_mode,
            "oidc_issuer_url": self.oidc_issuer_url,
            "oidc_client_id": self.oidc_client_id,
            "oauth1a_consumer_key": self.oauth1a_consumer_key,
            "service_account_username": self.service_account_username,
            "verify_ssl": self.verify_ssl,
            "ca_bundle_path": self.ca_bundle_path,
            "dry_run_default": self.dry_run_default,
            "max_sync_batch": self.max_sync_batch,
            "request_timeout_seconds": self.request_timeout_seconds,
            "max_retries": self.max_retries,
            "reqif_attribute_mappings": [
                {"reqif_name": m.reqif_name, "cortex_field": m.cortex_field,
                 "data_type": m.data_type, "enumeration_values": m.enumeration_values}
                for m in self.reqif_attribute_mappings
            ],
            "custom_attribute_mappings": [
                {"reqif_name": m.reqif_name, "cortex_field": m.cortex_field,
                 "data_type": m.data_type, "enumeration_values": m.enumeration_values}
                for m in self.custom_attribute_mappings
            ],
        }

    def get_all_mappings(self) -> List[ReqIFAttributeMapping]:
        """Return combined standard + custom mappings"""
        return self.reqif_attribute_mappings + self.custom_attribute_mappings

    def get_mapping_for_reqif(self, reqif_name: str) -> Optional[ReqIFAttributeMapping]:
        """Find Cortex field mapping for a given ReqIF attribute name"""
        for m in self.get_all_mappings():
            if m.reqif_name == reqif_name:
                return m
        return None

    def get_mapping_for_cortex(self, cortex_field: str) -> Optional[ReqIFAttributeMapping]:
        """Find ReqIF attribute name for a given Cortex field"""
        for m in self.get_all_mappings():
            if m.cortex_field == cortex_field:
                return m
        return None

    def validate(self) -> List[str]:
        """Validate configuration and return list of error messages"""
        errors = []

        if not self.enabled:
            return errors  # Nothing to validate if disabled

        if not self.base_url and not self.jts_url:
            errors.append("Either base_url or jts_url must be set")

        if self.auth_mode not in ("oidc", "oauth1a", "basic", "form"):
            errors.append(f"Invalid auth_mode: {self.auth_mode}")

        if self.auth_mode == "oidc":
            if not self.oidc_issuer_url:
                errors.append("oidc_issuer_url is required for OIDC auth")
            if not self.oidc_client_id:
                errors.append("oidc_client_id is required for OIDC auth")

        if self.auth_mode == "oauth1a":
            if not self.oauth1a_consumer_key:
                errors.append("oauth1a_consumer_key is required for OAuth 1.0a")

        if self.max_sync_batch < 1 or self.max_sync_batch > 1000:
            errors.append("max_sync_batch must be between 1 and 1000")

        if self.request_timeout_seconds < 1:
            errors.append("request_timeout_seconds must be >= 1")

        return errors
