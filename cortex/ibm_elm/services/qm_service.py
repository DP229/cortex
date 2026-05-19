"""
IBM ELM ETM / QM Service Adapter

OSLC QM V2 API and Reportable REST operations:
- Query test plans, test cases, test scripts
- Read test execution results
- Read validation links (requirements -> test artifacts)

Usage:
    service = QMService(elm_config, session_manager, user_id)
    testcases = service.query_testcases(project_area_url, "oslc.where=dcterms:title like '%brake%'")
"""

import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from cortex.ibm_elm.config import ELMConfig
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError

logger = logging.getLogger(__name__)


class QMTestCase:
    """Parsed QM Test Case"""
    def __init__(
        self,
        uri: str,
        title: str = "",
        identifier: str = "",
        description: str = "",
        test_case_type: str = "",
        state: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.uri = uri
        self.title = title
        self.identifier = identifier
        self.description = description
        self.test_case_type = test_case_type
        self.state = state
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "identifier": self.identifier,
            "description": self.description,
            "test_case_type": self.test_case_type,
            "state": self.state,
            "attributes": self.attributes,
        }


class QMService:
    """
    ETM / Quality Management service adapter (read-only for now).
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
            dry_run=False,
        )

    def query_testcases(
        self,
        project_area_url: str,
        oslc_query: Optional[str] = None,
        select: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[QMTestCase]:
        """Query test cases via OSLC QM"""
        if not project_area_url:
            raise ValueError("project_area_url is required")

        params: Dict[str, str] = {
            "oslc.paging": "true",
            "oslc.pageSize": str(min(limit, self.MAX_PAGE_SIZE)),
        }
        if oslc_query:
            params["oslc.where"] = oslc_query
        if select:
            params["oslc.select"] = ",".join(select)

        query_string = urlencode(params)
        query_url = f"{project_area_url}?{query_string}"

        logger.info("qm_query_testcases", url=query_url[:200])

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
                return self._parse_rdf_response(response.text)

        except ELMHTTPError as e:
            logger.error("qm_query_failed", error=str(e))
            raise

    def _parse_json_response(self, data: Dict[str, Any]) -> List[QMTestCase]:
        items = []
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or ""
            title = result.get("dcterms:title") or result.get("title") or ""
            identifier = result.get("dcterms:identifier") or result.get("identifier") or ""
            description = result.get("dcterms:description") or result.get("description") or ""
            tc_type = result.get("dcterms:type") or result.get("type") or ""
            state = result.get("oslc_cm:status") or result.get("status") or ""

            attributes = {k: v for k, v in result.items()
                         if k not in ("rdf:about", "uri", "dcterms:title", "title",
                                     "dcterms:identifier", "identifier", "dcterms:description",
                                     "description", "dcterms:type", "type", "oslc_cm:status", "status")}

            items.append(QMTestCase(
                uri=uri,
                title=title,
                identifier=identifier,
                description=description,
                test_case_type=tc_type,
                state=state,
                attributes=attributes,
            ))

        return items

    def _parse_rdf_response(self, xml_text: str) -> List[QMTestCase]:
        items = []
        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "oslc": "http://open-services.net/ns/core#",
                "dcterms": "http://purl.org/dc/terms/",
                "oslc_qm": "http://open-services.net/ns/qm#",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            }

            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for resource in result.iter("{http://open-services.net/ns/qm#}TestCase"):
                    uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                    title = ""
                    identifier = ""
                    description = ""
                    tc_type = ""
                    state = ""

                    for child in resource:
                        tag = etree.QName(child).localname
                        if tag == "title":
                            title = child.text or ""
                        elif tag == "identifier":
                            identifier = child.text or ""
                        elif tag == "description":
                            description = child.text or ""
                        elif tag == "type":
                            tc_type = child.text or ""
                        elif tag == "status":
                            state = child.text or ""

                    items.append(QMTestCase(
                        uri=uri,
                        title=title,
                        identifier=identifier,
                        description=description,
                        test_case_type=tc_type,
                        state=state,
                    ))

        except ImportError:
            logger.warning("lxml_not_available_qm_parse_skipped")
        except Exception as e:
            logger.error("qm_rdf_parse_error", error=str(e))

        return items
