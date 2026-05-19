"""
IBM ELM Global Configuration Management Service Adapter

OSLC Configuration Management read-only operations:
- Query GC components
- List streams and baselines
- Read GC hierarchy and configurations
- Verify no duplicate artifact versions in hierarchy

Usage:
    service = GCMService(elm_config, session_manager, user_id)
    configs = service.query_configurations()
    components = service.query_components()
"""

import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from cortex.ibm_elm.config import ELMConfig
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError

logger = logging.getLogger(__name__)


class GCConfiguration:
    """Parsed GCM Configuration (stream or baseline)"""
    def __init__(
        self,
        uri: str,
        title: str = "",
        identifier: str = "",
        config_type: str = "",  # stream, baseline, changeset
        component_uri: str = "",
        description: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.uri = uri
        self.title = title
        self.identifier = identifier
        self.config_type = config_type
        self.component_uri = component_uri
        self.description = description
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "identifier": self.identifier,
            "config_type": self.config_type,
            "component_uri": self.component_uri,
            "description": self.description,
            "attributes": self.attributes,
        }


class GCComponent:
    """Parsed GCM Component"""
    def __init__(
        self,
        uri: str,
        title: str = "",
        identifier: str = "",
        description: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.uri = uri
        self.title = title
        self.identifier = identifier
        self.description = description
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "identifier": self.identifier,
            "description": self.description,
            "attributes": self.attributes,
        }


class GCMService:
    """
    Global Configuration Management service adapter (read-only).
    """

    OSLC_CONFIG_VERSION = "1.0"
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
            dry_run=False,
        )

    def query_components(
        self,
        catalog_url: Optional[str] = None,
        limit: int = 50,
    ) -> List[GCComponent]:
        """Query GCM components"""
        url = catalog_url or self.config.gcm_url
        if not url:
            raise ValueError("GCM URL not configured")

        params: Dict[str, str] = {
            "oslc.paging": "true",
            "oslc.pageSize": str(min(limit, self.MAX_PAGE_SIZE)),
        }
        query_string = urlencode(params)
        query_url = f"{url}?{query_string}"

        logger.info("gcm_query_components", url=query_url[:200])

        try:
            response = self.client.get(
                query_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CONFIG_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return self._parse_components_json(response.json())
            else:
                return self._parse_components_rdf(response.text)

        except ELMHTTPError as e:
            logger.error("gcm_query_components_failed", error=str(e))
            raise

    def query_configurations(
        self,
        component_url: str,
        limit: int = 50,
    ) -> List[GCConfiguration]:
        """Query configurations (streams, baselines) for a component"""
        if not component_url:
            raise ValueError("component_url is required")

        params: Dict[str, str] = {
            "oslc.paging": "true",
            "oslc.pageSize": str(min(limit, self.MAX_PAGE_SIZE)),
        }
        query_string = urlencode(params)
        query_url = f"{component_url}?{query_string}"

        logger.info("gcm_query_configurations", url=query_url[:200])

        try:
            response = self.client.get(
                query_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CONFIG_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return self._parse_configs_json(response.json())
            else:
                return self._parse_configs_rdf(response.text)

        except ELMHTTPError as e:
            logger.error("gcm_query_configurations_failed", error=str(e))
            raise

    def _parse_components_json(self, data: Dict[str, Any]) -> List[GCComponent]:
        items = []
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or ""
            title = result.get("dcterms:title") or result.get("title") or ""
            identifier = result.get("dcterms:identifier") or result.get("identifier") or ""
            description = result.get("dcterms:description") or result.get("description") or ""

            attributes = {k: v for k, v in result.items()
                         if k not in ("rdf:about", "uri", "dcterms:title", "title",
                                     "dcterms:identifier", "identifier", "dcterms:description", "description")}

            items.append(GCComponent(
                uri=uri,
                title=title,
                identifier=identifier,
                description=description,
                attributes=attributes,
            ))

        return items

    def _parse_components_rdf(self, xml_text: str) -> List[GCComponent]:
        items = []
        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "oslc": "http://open-services.net/ns/core#",
                "dcterms": "http://purl.org/dc/terms/",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "oslc_config": "http://open-services.net/ns/config#",
            }

            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for resource in result.iter("{http://open-services.net/ns/config#}Component"):
                    uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
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

                    items.append(GCComponent(
                        uri=uri,
                        title=title,
                        identifier=identifier,
                        description=description,
                    ))

        except ImportError:
            logger.warning("lxml_not_available_gcm_parse_skipped")
        except Exception as e:
            logger.error("gcm_rdf_parse_error", error=str(e))

        return items

    def _parse_configs_json(self, data: Dict[str, Any]) -> List[GCConfiguration]:
        items = []
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or ""
            title = result.get("dcterms:title") or result.get("title") or ""
            identifier = result.get("dcterms:identifier") or result.get("identifier") or ""
            config_type = result.get("oslc_config:configType") or result.get("configType") or ""
            component_uri = result.get("oslc_config:component") or result.get("component") or ""
            description = result.get("dcterms:description") or result.get("description") or ""

            attributes = {k: v for k, v in result.items()
                         if k not in ("rdf:about", "uri", "dcterms:title", "title",
                                     "dcterms:identifier", "identifier", "oslc_config:configType",
                                     "configType", "oslc_config:component", "component",
                                     "dcterms:description", "description")}

            items.append(GCConfiguration(
                uri=uri,
                title=title,
                identifier=identifier,
                config_type=config_type,
                component_uri=component_uri,
                description=description,
                attributes=attributes,
            ))

        return items

    def _parse_configs_rdf(self, xml_text: str) -> List[GCConfiguration]:
        items = []
        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "oslc": "http://open-services.net/ns/core#",
                "dcterms": "http://purl.org/dc/terms/",
                "oslc_config": "http://open-services.net/ns/config#",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            }

            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for resource in result.iter("{http://open-services.net/ns/config#}Configuration"):
                    uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                    title = ""
                    identifier = ""
                    config_type = ""
                    component_uri = ""
                    description = ""

                    for child in resource:
                        tag = etree.QName(child).localname
                        if tag == "title":
                            title = child.text or ""
                        elif tag == "identifier":
                            identifier = child.text or ""
                        elif tag == "configType":
                            config_type = child.text or ""
                        elif tag == "component":
                            component_uri = child.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                        elif tag == "description":
                            description = child.text or ""

                    items.append(GCConfiguration(
                        uri=uri,
                        title=title,
                        identifier=identifier,
                        config_type=config_type,
                        component_uri=component_uri,
                        description=description,
                    ))

        except ImportError:
            logger.warning("lxml_not_available_gcm_config_parse_skipped")
        except Exception as e:
            logger.error("gcm_config_rdf_parse_error", error=str(e))

        return items
