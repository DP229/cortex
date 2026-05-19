"""
IBM ELM DOORS Next / RM Service Adapter

OSLC RM 2.0 and Reportable REST API operations:
- Query requirements artifacts with OSLC where/select
- Read requirement modules and collections
- Read individual artifacts by URL
- Parse OSLC responses (RDF/XML, JSON, Turtle)
- Handle OSLC paging for large result sets

Usage:
    service = RMService(elm_config, session_manager, user_id)
    artifacts = service.query_artifacts(project_area_url, query="oslc.where=dcterms:title like '%brake%'")
    artifact = service.read_artifact(artifact_url)
"""

import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, parse_qs, urlparse

import requests

from cortex.ibm_elm.config import ELMConfig
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError

logger = logging.getLogger(__name__)


class RMArtifact:
    """Parsed RM artifact from OSLC response"""
    def __init__(
        self,
        uri: str,
        title: str = "",
        identifier: str = "",
        description: str = "",
        artifact_type: str = "",
        module_uri: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.uri = uri
        self.title = title
        self.identifier = identifier
        self.description = description
        self.artifact_type = artifact_type
        self.module_uri = module_uri
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "identifier": self.identifier,
            "description": self.description,
            "artifact_type": self.artifact_type,
            "module_uri": self.module_uri,
            "attributes": self.attributes,
        }


class RMModule:
    """RM Module (requirements document)"""
    def __init__(
        self,
        uri: str,
        title: str = "",
        identifier: str = "",
        description: str = "",
    ):
        self.uri = uri
        self.title = title
        self.identifier = identifier
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "identifier": self.identifier,
            "description": self.description,
        }


class RMService:
    """
    DOORS Next / Requirements Management service adapter.

    Provides read access to RM artifacts via OSLC and Reportable REST.
    """

    OSLC_CORE_VERSION = "2.0"
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        elm_config: ELMConfig,
        session_manager: ELMSessionManager,
        user_id: str,
    ):
        self.config = elm_config
        self.session_manager = session_manager
        self.user_id = user_id
        self.client = ELMHTTPClient(
            elm_config=elm_config,
            session_manager=session_manager,
            user_id=user_id,
            dry_run=False,  # Reads are always live
        )

    def query_artifacts(
        self,
        project_area_url: str,
        oslc_query: Optional[str] = None,
        select: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[RMArtifact]:
        """
        Query RM artifacts using OSLC query syntax.

        Args:
            project_area_url: Service provider URL for the project area
            oslc_query: OSLC where clause, e.g. "dcterms:title like '%brake%'"
            select: Fields to return, e.g. ["dcterms:title", "dcterms:identifier"]
            order_by: Field to order by
            limit: Max results (OSLC paging handles large sets)

        Returns:
            List of RMArtifact objects
        """
        if not project_area_url:
            raise ValueError("project_area_url is required")

        # Build query URL
        params: Dict[str, str] = {
            "oslc.paging": "true",
            "oslc.pageSize": str(min(limit, self.MAX_PAGE_SIZE)),
        }

        if oslc_query:
            params["oslc.where"] = oslc_query
        if select:
            params["oslc.select"] = ",".join(select)
        if order_by:
            params["oslc.orderBy"] = order_by

        query_string = urlencode(params)
        query_url = f"{project_area_url}?{query_string}"

        logger.info("rm_query_artifacts", url=query_url[:200])

        try:
            response = self.client.get(
                query_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CORE_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")

            if "json" in content_type:
                return self._parse_json_response(response.json())
            else:
                return self._parse_rdf_xml_response(response.text)

        except ELMHTTPError as e:
            logger.error("rm_query_failed", error=str(e), status=e.status_code)
            raise

    def read_artifact(self, artifact_url: str) -> Optional[RMArtifact]:
        """
        Read a single artifact by its OSLC/RM URL.

        Returns:
            RMArtifact or None if not found
        """
        logger.info("rm_read_artifact", url=artifact_url[:200])

        try:
            response = self.client.get(
                artifact_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CORE_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")

            if "json" in content_type:
                artifacts = self._parse_json_response(response.json())
            else:
                artifacts = self._parse_rdf_xml_response(response.text)

            return artifacts[0] if artifacts else None

        except ELMHTTPError as e:
            if e.status_code == 404:
                return None
            raise

    def query_modules(
        self,
        project_area_url: str,
        limit: int = 50,
    ) -> List[RMModule]:
        """
        Query requirement modules (documents) in a project area.

        In OSLC RM, modules are often found via oslc:usage of "module"
        or by querying with a specific type filter.
        """
        # Query for artifacts that are modules
        # DNG-specific: modules have rdf:type of rm:Module or oslc:Module
        oslc_query = "rdf:type=%3Chttp%3A%2F%2Fjazz.net%2Fns%2Frm%23Module%3E"

        params = {
            "oslc.paging": "true",
            "oslc.pageSize": str(min(limit, self.MAX_PAGE_SIZE)),
            "oslc.where": oslc_query,
        }

        query_string = urlencode(params)
        query_url = f"{project_area_url}?{query_string}"

        logger.info("rm_query_modules", url=project_area_url)

        try:
            response = self.client.get(
                query_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CORE_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")

            if "json" in content_type:
                return self._parse_modules_json(response.json())
            else:
                return self._parse_modules_rdf(response.text)

        except ELMHTTPError as e:
            logger.error("rm_query_modules_failed", error=str(e))
            return []

    def get_project_area_service_provider(self, catalog_url: str, project_area_name: str) -> Optional[str]:
        """
        Find the OSLC Service Provider URL for a named project area.

        Args:
            catalog_url: Service Provider Catalog URL (from Root Services)
            project_area_name: Name of the project area

        Returns:
            Service Provider URL or None
        """
        try:
            response = self.client.get(
                catalog_url,
                headers={"Accept": "application/xml, application/rdf+xml"},
            )

            # Parse ServiceProviderCatalog for matching title
            text = response.text

            try:
                from lxml import etree
                root = etree.fromstring(text.encode("utf-8"))
                ns = {
                    "oslc": "http://open-services.net/ns/core#",
                    "dcterms": "http://purl.org/dc/terms/",
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                }

                for provider in root.iter("{http://open-services.net/ns/core#}ServiceProvider"):
                    title_elem = provider.find("{http://purl.org/dc/terms/}title")
                    if title_elem is not None and title_elem.text:
                        if title_elem.text.strip().lower() == project_area_name.lower():
                            details = provider.find("{http://open-services.net/ns/core#}details")
                            if details is not None:
                                return details.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")

            except ImportError:
                # Regex fallback
                import re
                provider_pattern = r'<oslc:ServiceProvider[^>]*>(.*?)</oslc:ServiceProvider>'
                for match in re.finditer(provider_pattern, text, re.DOTALL):
                    block = match.group(1)
                    title_match = re.search(r'<dcterms:title>([^<]+)</dcterms:title>', block)
                    if title_match and title_match.group(1).strip().lower() == project_area_name.lower():
                        url_match = re.search(r'<oslc:details\s+rdf:resource="([^"]+)"', block)
                        if url_match:
                            return url_match.group(1)

        except Exception as e:
            logger.error("get_project_area_service_provider_failed", error=str(e))

        return None

    def _parse_json_response(self, data: Dict[str, Any]) -> List[RMArtifact]:
        """Parse OSLC JSON response into RMArtifacts"""
        artifacts = []

        # OSLC JSON format: {"oslc:results": [{...}]}
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or result.get("@id", "")
            title = result.get("dcterms:title") or result.get("title") or ""
            identifier = result.get("dcterms:identifier") or result.get("identifier") or ""
            description = result.get("dcterms:description") or result.get("description") or ""
            artifact_type = result.get("dcterms:type") or result.get("type") or ""

            # Extra attributes
            attributes = {k: v for k, v in result.items()
                         if k not in ("rdf:about", "dcterms:title", "dcterms:identifier",
                                     "dcterms:description", "dcterms:type", "uri", "title",
                                     "identifier", "description", "type", "@id")}

            artifacts.append(RMArtifact(
                uri=uri,
                title=title,
                identifier=identifier,
                description=description,
                artifact_type=artifact_type,
                attributes=attributes,
            ))

        return artifacts

    def _parse_rdf_xml_response(self, xml_text: str) -> List[RMArtifact]:
        """Parse OSLC RDF/XML response into RMArtifacts"""
        artifacts = []

        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dcterms": "http://purl.org/dc/terms/",
                "oslc": "http://open-services.net/ns/core#",
                "rm": "http://open-services.net/ns/rm#",
            }

            # Find all response items
            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for item in result.iter("{http://open-services.net/ns/core#}results"):
                    for resource in item:
                        uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                        if not uri:
                            continue

                        title = ""
                        identifier = ""
                        description = ""
                        artifact_type = ""
                        attributes = {}

                        for child in resource:
                            tag = etree.QName(child).localname
                            ns_local = etree.QName(child).namespace

                            if tag == "title":
                                title = child.text or ""
                            elif tag == "identifier":
                                identifier = child.text or ""
                            elif tag == "description":
                                description = child.text or ""
                            elif tag == "type":
                                artifact_type = child.text or ""
                            else:
                                attributes[f"{ns_local}:{tag}"] = child.text or ""

                        artifacts.append(RMArtifact(
                            uri=uri,
                            title=title,
                            identifier=identifier,
                            description=description,
                            artifact_type=artifact_type,
                            attributes=attributes,
                        ))

        except ImportError:
            logger.warning("lxml_not_available_rdf_parse_skipped")
        except Exception as e:
            logger.error("rdf_parse_error", error=str(e))

        return artifacts

    def _parse_modules_json(self, data: Dict[str, Any]) -> List[RMModule]:
        """Parse module list from JSON"""
        modules = []
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or ""
            title = result.get("dcterms:title") or result.get("title") or ""
            identifier = result.get("dcterms:identifier") or result.get("identifier") or ""
            description = result.get("dcterms:description") or result.get("description") or ""

            modules.append(RMModule(
                uri=uri,
                title=title,
                identifier=identifier,
                description=description,
            ))

        return modules

    def _parse_modules_rdf(self, xml_text: str) -> List[RMModule]:
        """Parse module list from RDF/XML"""
        modules = []

        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dcterms": "http://purl.org/dc/terms/",
                "oslc": "http://open-services.net/ns/core#",
            }

            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for item in result.iter("{http://open-services.net/ns/core#}results"):
                    for resource in item:
                        uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                        if not uri:
                            continue

                        title = ""
                        identifier = ""
                        description = ""

                        for child in resource:
                            tag = etree.QName(child).localname
                            if tag == "title":
                                title = child.text or ""
                            elif tag == "identifier":
                                identifier = child.text or ""
                            elif tag == "description":
                                description = child.text or ""

                        modules.append(RMModule(
                            uri=uri,
                            title=title,
                            identifier=identifier,
                            description=description,
                        ))

        except ImportError:
            pass
        except Exception as e:
            logger.error("modules_rdf_parse_error", error=str(e))

        return modules
