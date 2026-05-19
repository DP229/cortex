"""
IBM ELM Connector for Cortex

Bidirectional integration with IBM Engineering Lifecycle Management:
- DOORS Next / RM (Requirements Management)
- EWM / CCM (Change and Configuration Management)
- ETM / QM (Quality / Test Management)
- GCM (Global Configuration Management)

Core philosophy: AI-assisted, human-approved.
All writes to ELM require explicit approval via the sync job queue.
"""

from cortex.ibm_elm.config import ELMConfig, ReqIFAttributeMapping
from cortex.ibm_elm.reqif.importer import ReqIFImporter, ReqIFToCortexMapper
from cortex.ibm_elm.reqif.exporter import CortexToReqIFExporter
from cortex.ibm_elm.auth.oidc_client import OIDCClient, OIDCError, OIDCTokenExpiredError
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.rootservices import RootServicesDiscoverer, DiscoveredServices
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError, ELMRateLimitError, ELMAuthenticationError

__all__ = [
    "ELMConfig",
    "ReqIFAttributeMapping",
    "ReqIFImporter",
    "ReqIFToCortexMapper",
    "CortexToReqIFExporter",
    "OIDCClient",
    "OIDCError",
    "OIDCTokenExpiredError",
    "ELMSessionManager",
    "RootServicesDiscoverer",
    "DiscoveredServices",
    "ELMHTTPClient",
    "ELMHTTPError",
    "ELMRateLimitError",
    "ELMAuthenticationError",
]
