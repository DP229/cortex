"""
IBM ELM EWM / CCM Service Adapter

OSLC CM 2.0 and Resource-Oriented WorkItem API operations:
- Query work items (Epic, Story, Task, EWR, Issue, Defect)
- Read work item details
- Create work items (via OSLC Creation Factory)
- Update work item fields
- Create links between work items and RM artifacts

Usage:
    service = CCMService(elm_config, session_manager, user_id)
    work_items = service.query_workitems(project_area_url, "oslc.where=dcterms:type='com.ibm.team.apt.workItemType.story'")
    work_item = service.read_workitem(workitem_url)
"""

import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from cortex.ibm_elm.config import ELMConfig
from cortex.ibm_elm.auth.session_manager import ELMSessionManager
from cortex.ibm_elm.client.base_client import ELMHTTPClient, ELMHTTPError

logger = logging.getLogger(__name__)


class CCMWorkItem:
    """Parsed CCM Work Item"""
    def __init__(
        self,
        uri: str,
        identifier: str = "",
        title: str = "",
        description: str = "",
        work_item_type: str = "",
        state: str = "",
        owner: str = "",
        planned_for: str = "",
        project_area: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.uri = uri
        self.identifier = identifier
        self.title = title
        self.description = description
        self.work_item_type = work_item_type
        self.state = state
        self.owner = owner
        self.planned_for = planned_for
        self.project_area = project_area
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "work_item_type": self.work_item_type,
            "state": self.state,
            "owner": self.owner,
            "planned_for": self.planned_for,
            "project_area": self.project_area,
            "attributes": self.attributes,
        }


class CCMService:
    """
    EWM / CCM Work Item service adapter.
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

    def query_workitems(
        self,
        project_area_url: str,
        oslc_query: Optional[str] = None,
        select: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[CCMWorkItem]:
        """
        Query CCM work items using OSLC.

        Args:
            project_area_url: Service provider URL for the project area
            oslc_query: OSLC where clause, e.g. "dcterms:type='com.ibm.team.apt.workItemType.story'"
            select: Fields to return
            order_by: Field to order by
            limit: Max results

        Returns:
            List of CCMWorkItem objects
        """
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
        if order_by:
            params["oslc.orderBy"] = order_by

        query_string = urlencode(params)
        query_url = f"{project_area_url}?{query_string}"

        logger.info("ccm_query_workitems", url=query_url[:200])

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
            logger.error("ccm_query_failed", error=str(e))
            raise

    def read_workitem(self, workitem_url: str) -> Optional[CCMWorkItem]:
        """Read a single work item by URL"""
        logger.info("ccm_read_workitem", url=workitem_url[:200])

        try:
            response = self.client.get(
                workitem_url,
                headers={
                    "Accept": "application/rdf+xml, application/json",
                    "OSLC-Core-Version": self.OSLC_CORE_VERSION,
                },
            )

            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                items = self._parse_json_response(response.json())
            else:
                items = self._parse_rdf_response(response.text)

            return items[0] if items else None

        except ELMHTTPError as e:
            if e.status_code == 404:
                return None
            raise

    def create_workitem(
        self,
        creation_factory_url: str,
        title: str,
        description: str,
        work_item_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create a new work item via OSLC Creation Factory.

        Returns:
            URL of created work item, or None on failure
        """
        # Build OSLC JSON payload
        payload = {
            "dcterms:title": title,
            "dcterms:description": description,
            "dcterms:type": work_item_type,
        }
        if attributes:
            payload.update(attributes)

        logger.info("ccm_create_workitem", type=work_item_type, title=title[:50])

        try:
            response = self.client.post(
                creation_factory_url,
                json_data=payload,
                headers={
                    "Content-Type": "application/json",
                    "OSLC-Core-Version": self.OSLC_CORE_VERSION,
                    "Accept": "application/json",
                },
            )

            # Created work item URL is in Location header or response body
            location = response.headers.get("Location")
            if location:
                return location

            # Try to extract from JSON response
            body = response.json() if response.text else {}
            return body.get("rdf:about") or body.get("uri")

        except ELMHTTPError as e:
            logger.error("ccm_create_workitem_failed", error=str(e))
            raise

    def _parse_json_response(self, data: Dict[str, Any]) -> List[CCMWorkItem]:
        """Parse OSLC JSON response into CCMWorkItems"""
        items = []
        results = data.get("oslc:results") or data.get("results") or []
        if not isinstance(results, list):
            results = [results]

        for result in results:
            uri = result.get("rdf:about") or result.get("uri") or result.get("@id", "")
            identifier = result.get("oslc_cm:changeRequestId") or result.get("dcterms:identifier") or ""
            title = result.get("dcterms:title") or result.get("title") or ""
            description = result.get("dcterms:description") or result.get("description") or ""
            wi_type = result.get("dcterms:type") or result.get("type") or ""
            state = result.get("oslc_cm:status") or result.get("status") or ""
            owner = result.get("oslc_cm:ownedBy") or ""
            planned_for = result.get("rtc:plannedFor") or ""

            attributes = {k: v for k, v in result.items()
                         if k not in ("rdf:about", "uri", "@id", "dcterms:title", "title",
                                     "dcterms:description", "description", "dcterms:type", "type",
                                     "dcterms:identifier", "identifier", "oslc_cm:status", "status",
                                     "oslc_cm:ownedBy", "rtc:plannedFor")}

            items.append(CCMWorkItem(
                uri=uri,
                identifier=identifier,
                title=title,
                description=description,
                work_item_type=wi_type,
                state=state,
                owner=owner,
                planned_for=planned_for,
                attributes=attributes,
            ))

        return items

    def _parse_rdf_response(self, xml_text: str) -> List[CCMWorkItem]:
        """Parse OSLC RDF/XML response into CCMWorkItems"""
        items = []
        try:
            from lxml import etree
            root = etree.fromstring(xml_text.encode("utf-8"))
            ns = {
                "oslc": "http://open-services.net/ns/core#",
                "dcterms": "http://purl.org/dc/terms/",
                "oslc_cm": "http://open-services.net/ns/cm#",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            }

            for result in root.iter("{http://open-services.net/ns/core#}Response"):
                for resource in result.iter("{http://open-services.net/ns/cm#}ChangeRequest"):
                    uri = resource.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource") or ""
                    identifier = ""
                    title = ""
                    description = ""
                    wi_type = ""
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
                            wi_type = child.text or ""
                        elif tag == "status":
                            state = child.text or ""

                    items.append(CCMWorkItem(
                        uri=uri,
                        identifier=identifier,
                        title=title,
                        description=description,
                        work_item_type=wi_type,
                        state=state,
                    ))

        except ImportError:
            logger.warning("lxml_not_available_ccm_parse_skipped")
        except Exception as e:
            logger.error("ccm_rdf_parse_error", error=str(e))

        return items
