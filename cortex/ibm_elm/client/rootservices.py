"""
IBM ELM Root Services Discovery

Parses Jazz Team Server Root Services document to discover:
- RM (DOORS Next) service catalog URL
- CCM (EWM) service catalog URL
- QM (ETM) service catalog URL
- GCM service catalog URL
- JTS user registry URL
- OAuth / OIDC configuration URLs

Usage:
    discoverer = RootServicesDiscoverer("https://elm.company.com:9443/jts")
    services = discoverer.discover_all()
    rm_url = services.rm_catalog_url
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredServices:
    """Container for discovered ELM service URLs"""
    jts_url: str = ""
    rm_catalog_url: Optional[str] = None
    ccm_catalog_url: Optional[str] = None
    qm_catalog_url: Optional[str] = None
    gcm_catalog_url: Optional[str] = None
    rm_rootservices_url: Optional[str] = None
    ccm_rootservices_url: Optional[str] = None
    qm_rootservices_url: Optional[str] = None
    gcm_rootservices_url: Optional[str] = None
    jts_user_registry_url: Optional[str] = None
    oauth_request_token_url: Optional[str] = None
    oauth_authorization_url: Optional[str] = None
    oauth_access_token_url: Optional[str] = None
    oidc_issuer_url: Optional[str] = None
    project_areas: list = field(default_factory=list)
    raw_xml: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jts_url": self.jts_url,
            "rm_catalog_url": self.rm_catalog_url,
            "ccm_catalog_url": self.ccm_catalog_url,
            "qm_catalog_url": self.qm_catalog_url,
            "gcm_catalog_url": self.gcm_catalog_url,
            "rm_rootservices_url": self.rm_rootservices_url,
            "ccm_rootservices_url": self.ccm_rootservices_url,
            "qm_rootservices_url": self.qm_rootservices_url,
            "gcm_rootservices_url": self.gcm_rootservices_url,
            "jts_user_registry_url": self.jts_user_registry_url,
            "oauth_request_token_url": self.oauth_request_token_url,
            "oauth_authorization_url": self.oauth_authorization_url,
            "oauth_access_token_url": self.oauth_access_token_url,
            "oidc_issuer_url": self.oidc_issuer_url,
            "project_areas": self.project_areas,
        }


class RootServicesDiscoverer:
    """
    Discover ELM application URLs from Jazz Team Server Root Services.
    """

    # OSLC Catalog relation types (from Jazz Root Services spec)
    CATALOG_REL_TYPES = {
        "rm": "http://jazz.net/ns/rm#requirementsManagement",
        "ccm": "http://jazz.net/ns/ccm#workItem",
        "qm": "http://jazz.net/ns/qm#qualityManagement",
        "gcm": "http://jazz.net/ns/gcm#globalConfiguration",
    }

    # Root Services relation types
    ROOTSERVICES_REL_TYPES = {
        "rm": "http://jazz.net/ns/rm#requirementsManagement",
        "ccm": "http://jazz.net/ns/ccm#workItem",
        "qm": "http://jazz.net/ns/qm#qualityManagement",
        "gcm": "http://jazz.net/ns/gcm#globalConfiguration",
    }

    def __init__(
        self,
        jts_url: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.jts_url = jts_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._session.headers.update({
            "Accept": "application/xml",
            "OSLC-Core-Version": "2.0",
        })

    def _fetch_root_services(self) -> str:
        """Fetch raw Root Services XML from JTS"""
        url = f"{self.jts_url}/rootservices"
        logger.info("rootservices_fetch", url=url)

        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error("rootservices_fetch_failed", error=str(e), url=url)
            raise

    def _parse_xml_minimal(self, xml_text: str) -> Dict[str, str]:
        """
        Minimal XML parsing without external dependencies.
        Uses regex for reliability in restricted environments.
        """
        import re

        results: Dict[str, str] = {}

        # Extract catalog URLs
        for app, rel_type in self.CATALOG_REL_TYPES.items():
            # Pattern: <element rdf:resource="URL"> with rel="rel_type"
            pattern = rf'<[^\s>]+\s+rdf:resource=["\']([^"\']+)["\'][^\u003e]*\s+rel=["\']{re.escape(rel_type)}["\'][^\u003e]*>'
            match = re.search(pattern, xml_text)
            if match:
                results[f"{app}_catalog_url"] = match.group(1)
                continue
            # Reverse pattern: rel first, resource second
            pattern2 = rf'<[^\s>]+\s+rel=["\']{re.escape(rel_type)}["\'][^\u003e]*\s+rdf:resource=["\']([^"\']+)["\'][^\u003e]*>'
            match2 = re.search(pattern2, xml_text)
            if match2:
                results[f"{app}_catalog_url"] = match2.group(1)

        # Extract root services URLs ( jazz_ns:app rootservices )
        for app, rel_type in self.ROOTSERVICES_REL_TYPES.items():
            pattern = rf'<[^\s>]+\s+rdf:resource=["\']([^"\']+)["\'][^\u003e]*\s+rel=["\']{re.escape(rel_type)}["\'][^\u003e]*>'
            match = re.search(pattern, xml_text)
            if match:
                results[f"{app}_rootservices_url"] = match.group(1)
            else:
                pattern2 = rf'<[^\s>]+\s+rel=["\']{re.escape(rel_type)}["\'][^\u003e]*\s+rdf:resource=["\']([^"\']+)["\'][^\u003e]*>'
                match2 = re.search(pattern2, xml_text)
                if match2:
                    results[f"{app}_rootservices_url"] = match2.group(1)

        # OAuth 1.0a URLs
        oauth_patterns = {
            "oauth_request_token_url": r'jazz_ns:oauthRequestTokenUrl\s*>([^&lt;]+)\u003c',
            "oauth_authorization_url": r'jazz_ns:oauthAuthorizationUrl\s*>([^&lt;]+)\u003c',
            "oauth_access_token_url": r'jazz_ns:oauthAccessTokenUrl\s*>([^&lt;]+)\u003c',
        }
        for key, pattern in oauth_patterns.items():
            match = re.search(pattern, xml_text)
            if match:
                results[key] = match.group(1).strip()

        # OIDC issuer
        oidc_patterns = [
            r'jazz_ns:openidConnectProvider\s+rdf:resource=["\']([^"\']+)["\']',
            r'openidConnectProvider\s+rdf:resource=["\']([^"\']+)["\']',
        ]
        for pattern in oidc_patterns:
            match = re.search(pattern, xml_text)
            if match:
                results["oidc_issuer_url"] = match.group(1)
                break

        # JTS user registry
        registry_pattern = r'jts\s*:userRegistry\s+rdf:resource=["\']([^"\']+)["\']'
        match = re.search(registry_pattern, xml_text, re.IGNORECASE)
        if match:
            results["jts_user_registry_url"] = match.group(1)

        return results

    def _parse_with_lxml(self, xml_text: str) -> Dict[str, str]:
        """More robust parsing using lxml if available"""
        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            nsmap = root.nsmap

            # Find all elements with rdf:resource attributes
            results: Dict[str, str] = {}

            # Define namespaces
            ns = {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "oslc": "http://open-services.net/ns/core#",
                "jazz_ns": "http://jazz.net/xmlns/prod/jazz/jazz/1.0/",
                "jp06": "http://jazz.net/xmlns/prod/jazz/process/1.0/",
            }

            # Search for all link elements
            for elem in root.iter():
                resource = elem.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                if not resource:
                    resource = elem.get("rdf:resource")
                if not resource:
                    continue

                rel = elem.get("rel")
                if not rel:
                    # Check tag name as fallback
                    tag = etree.QName(elem).localname
                    if tag in ("rmServiceProvider", "qmServiceProvider", "cmServiceProvider"):
                        # Determine app from tag
                        app_map = {
                            "rmServiceProvider": "rm",
                            "qmServiceProvider": "qm",
                            "cmServiceProvider": "ccm",
                        }
                        app = app_map.get(tag)
                        if app:
                            results[f"{app}_catalog_url"] = resource
                    continue

                for app, rel_type in self.CATALOG_REL_TYPES.items():
                    if rel == rel_type:
                        results[f"{app}_catalog_url"] = resource

                for app, rel_type in self.ROOTSERVICES_REL_TYPES.items():
                    if rel == rel_type:
                        results[f"{app}_rootservices_url"] = resource

            # Extract OAuth/OIDC info
            for elem in root.iter():
                tag = etree.QName(elem).localname
                if tag == "oauthRequestTokenUrl" and elem.text:
                    results["oauth_request_token_url"] = elem.text.strip()
                elif tag == "oauthAuthorizationUrl" and elem.text:
                    results["oauth_authorization_url"] = elem.text.strip()
                elif tag == "oauthAccessTokenUrl" and elem.text:
                    results["oauth_access_token_url"] = elem.text.strip()
                elif tag == "openidConnectProvider":
                    resource = elem.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                    if resource:
                        results["oidc_issuer_url"] = resource

            return results

        except ImportError:
            logger.debug("lxml_not_available_using_regex_parsing")
            return {}
        except Exception as e:
            logger.warning("lxml_parse_failed", error=str(e))
            return {}

    def discover_all(self) -> DiscoveredServices:
        """
        Discover all ELM services from JTS Root Services.

        Returns:
            DiscoveredServices with all available URLs
        """
        xml_text = self._fetch_root_services()

        # Try lxml first, fallback to regex
        parsed = self._parse_with_lxml(xml_text)
        if not parsed:
            parsed = self._parse_xml_minimal(xml_text)

        services = DiscoveredServices(
            jts_url=self.jts_url,
            raw_xml=xml_text,
        )

        # Map parsed results
        services.rm_catalog_url = parsed.get("rm_catalog_url")
        services.ccm_catalog_url = parsed.get("ccm_catalog_url")
        services.qm_catalog_url = parsed.get("qm_catalog_url")
        services.gcm_catalog_url = parsed.get("gcm_catalog_url")
        services.rm_rootservices_url = parsed.get("rm_rootservices_url")
        services.ccm_rootservices_url = parsed.get("ccm_rootservices_url")
        services.qm_rootservices_url = parsed.get("qm_rootservices_url")
        services.gcm_rootservices_url = parsed.get("gcm_rootservices_url")
        services.jts_user_registry_url = parsed.get("jts_user_registry_url")
        services.oauth_request_token_url = parsed.get("oauth_request_token_url")
        services.oauth_authorization_url = parsed.get("oauth_authorization_url")
        services.oauth_access_token_url = parsed.get("oauth_access_token_url")
        services.oidc_issuer_url = parsed.get("oidc_issuer_url")

        logger.info(
            "rootservices_discovery_complete",
            rm=services.rm_catalog_url is not None,
            ccm=services.ccm_catalog_url is not None,
            qm=services.qm_catalog_url is not None,
            gcm=services.gcm_catalog_url is not None,
            oidc=services.oidc_issuer_url is not None,
        )

        return services

    def discover_project_areas(self, catalog_url: Optional[str] = None) -> list:
        """
        Discover project areas from an OSLC Service Provider Catalog.
        If no catalog_url is given, uses RM catalog if available.
        """
        if not catalog_url:
            services = self.discover_all()
            catalog_url = services.rm_catalog_url or services.ccm_catalog_url

        if not catalog_url:
            logger.warning("no_catalog_url_for_project_area_discovery")
            return []

        logger.info("project_area_discovery_start", catalog_url=catalog_url)

        try:
            response = self._session.get(catalog_url, timeout=self.timeout)
            response.raise_for_status()
            xml_text = response.text

            # Parse ServiceProviderCatalog for oslc:ServiceProvider entries
            project_areas = []

            try:
                from lxml import etree
                root = etree.fromstring(xml_text.encode("utf-8"))
                ns = {
                    "oslc": "http://open-services.net/ns/core#",
                    "dcterms": "http://purl.org/dc/terms/",
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                }

                for provider in root.iter("{http://open-services.net/ns/core#}ServiceProvider"):
                    title_elem = provider.find("{http://purl.org/dc/terms/}title")
                    desc_elem = provider.find("{http://purl.org/dc/terms/}description")
                    details_elem = provider.find("{http://open-services.net/ns/core#}details")

                    area = {
                        "title": title_elem.text if title_elem is not None else "Unknown",
                        "description": desc_elem.text if desc_elem is not None else None,
                        "url": details_elem.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                        if details_elem is not None else None,
                    }
                    project_areas.append(area)

            except ImportError:
                # Regex fallback for ServiceProvider entries
                import re
                provider_pattern = r'<oslc:ServiceProvider[^\u003e]*>(.*?)&lt;/oslc:ServiceProvider\u003e'
                for match in re.finditer(provider_pattern, xml_text, re.DOTALL):
                    block = match.group(1)
                    title_match = re.search(r'<dcterms:title>([^&lt;]+)\u003c/dcterms:title>', block)
                    desc_match = re.search(r'<dcterms:description>([^&lt;]+)\u003c/dcterms:description>', block)
                    url_match = re.search(r'<oslc:details\s+rdf:resource=["\']([^"\']+)["\']', block)

                    project_areas.append({
                        "title": title_match.group(1) if title_match else "Unknown",
                        "description": desc_match.group(1) if desc_match else None,
                        "url": url_match.group(1) if url_match else None,
                    })

            logger.info("project_area_discovery_complete", count=len(project_areas))
            return project_areas

        except requests.RequestException as e:
            logger.error("project_area_discovery_failed", error=str(e))
            return []
