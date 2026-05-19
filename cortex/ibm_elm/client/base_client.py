"""
IBM ELM Base HTTP Client

Production-grade HTTP client for IBM ELM APIs:
- Automatic cookie / Authorization header injection from session manager
- Request/response audit logging
- Exponential backoff retry with jitter
- Rate-limit respect (reads Retry-After header)
- Dry-run mode: intercepts writes and returns preview instead
- OSLC Core-Version header management
- Response validation and error translation

Usage:
    client = ELMHTTPClient(
        elm_config=config.elm,
        session_manager=session_manager,
        user_id="..."
    )
    response = client.get("https://elm.company.com/rm/resources/...")
"""

import json
import time
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class ELMHTTPError(Exception):
    """ELM HTTP request failed"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ELMRateLimitError(ELMHTTPError):
    """Rate limited by ELM server"""
    def __init__(self, retry_after: int, **kwargs):
        super().__init__(f"Rate limited. Retry after {retry_after}s", **kwargs)
        self.retry_after = retry_after


class ELMAuthenticationError(ELMHTTPError):
    """Authentication with ELM failed (401/403)"""
    pass


class ELMHTTPClient:
    """
    Secure, audited HTTP client for IBM ELM REST/OSLC APIs.
    """

    def __init__(
        self,
        elm_config,
        session_manager,
        user_id: str,
        dry_run: Optional[bool] = None,
    ):
        from cortex.ibm_elm.config import ELMConfig
        from cortex.ibm_elm.auth.session_manager import ELMSessionManager

        self.config: ELMConfig = elm_config
        self.session_manager: ELMSessionManager = session_manager
        self.user_id = user_id
        self.dry_run = dry_run if dry_run is not None else elm_config.dry_run_default

        self._http = requests.Session()
        self._http.verify = elm_config.verify_ssl

        # Default headers for OSLC
        self._default_headers = {
            "Accept": "application/rdf+xml, application/json, text/turtle",
            "OSLC-Core-Version": "2.0",
            "Accept-Language": "en-US",
        }

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build request headers with auth cookies/tokens"""
        headers = dict(self._default_headers)

        # Check if we have an active session
        access_token = self.session_manager.get_access_token(self.user_id)
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        return headers

    def _get_auth_cookies(self) -> Dict[str, str]:
        """Get auth cookies for requests Session"""
        return self.session_manager.get_auth_cookies(self.user_id)

    def _update_cookies(self) -> None:
        """Sync cookies from session manager into requests Session"""
        cookies = self._get_auth_cookies()
        self._http.cookies.clear()
        for name, value in cookies.items():
            self._http.cookies.set(name, value)

    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> requests.Response:
        """
        Execute HTTP request with retry, audit, and auth.

        Returns:
            requests.Response object

        Raises:
            ELMHTTPError on failure
        """
        # Merge headers
        req_headers = self._get_auth_headers()
        if headers:
            req_headers.update(headers)
        if content_type:
            req_headers["Content-Type"] = content_type

        # Ensure cookies are set
        self._update_cookies()

        # Check token expiry and refresh if needed
        if self.session_manager.is_token_expired(self.user_id):
            logger.info("elm_token_expired_attempting_refresh", user_id=self.user_id)
            self._refresh_token()
            # Rebuild headers after refresh
            req_headers = self._get_auth_headers()
            if headers:
                req_headers.update(headers)
            if content_type:
                req_headers["Content-Type"] = content_type

        # Dry-run interception for mutating methods
        if self.dry_run and method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            return self._dry_run_response(method, url, req_headers, data or json_data)

        # Build request kwargs
        kwargs = {
            "headers": req_headers,
            "timeout": self.config.request_timeout_seconds,
        }
        if params:
            kwargs["params"] = params
        if json_data:
            kwargs["json"] = json_data
        elif data:
            kwargs["data"] = data

        # Execute with retry
        last_exception = None
        for attempt in range(self.config.max_retries):
            try:
                logger.debug("elm_request", method=method, url=url, attempt=attempt + 1)
                response = self._http.request(method, url, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("elm_rate_limited", retry_after=retry_after, url=url)
                    if attempt < self.config.max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise ELMRateLimitError(retry_after, status_code=429, response_body=response.text)

                # Handle auth failure
                if response.status_code in (401, 403):
                    logger.error("elm_auth_failed", status=response.status_code, url=url)
                    raise ELMAuthenticationError(
                        f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                # Handle server errors with retry
                if 500 <= response.status_code < 600:
                    logger.warning("elm_server_error", status=response.status_code, url=url)
                    if attempt < self.config.max_retries - 1:
                        backoff = (2 ** attempt) + 1  # Exponential backoff
                        time.sleep(backoff)
                        continue

                response.raise_for_status()
                return response

            except requests.RequestException as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    backoff = (2 ** attempt) + 1
                    time.sleep(backoff)
                    continue

        # All retries exhausted
        raise ELMHTTPError(
            f"Request failed after {self.config.max_retries} attempts: {last_exception}",
            response_body=str(last_exception) if last_exception else None,
        )

    def _refresh_token(self) -> bool:
        """Attempt to refresh OIDC access token"""
        refresh_token = self.session_manager.get_refresh_token(self.user_id)
        if not refresh_token:
            logger.error("elm_no_refresh_token", user_id=self.user_id)
            return False

        try:
            from cortex.ibm_elm.auth.oidc_client import OIDCClient, OIDCError

            oidc = OIDCClient(
                issuer_url=self.config.oidc_issuer_url,
                client_id=self.config.oidc_client_id,
                client_secret=self._get_client_secret(),
                verify_ssl=self.config.verify_ssl,
            )
            tokens = oidc.refresh_access_token(refresh_token)

            new_access = tokens.get("access_token")
            new_refresh = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in")
            expires_at = None
            if expires_in:
                from datetime import timedelta
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            self.session_manager.update_tokens(
                user_id=self.user_id,
                access_token=new_access,
                refresh_token=new_refresh,
                token_expires_at=expires_at,
            )

            logger.info("elm_token_refreshed", user_id=self.user_id)
            return True

        except Exception as e:
            logger.error("elm_token_refresh_failed", error=str(e), user_id=self.user_id)
            return False

    def _get_client_secret(self) -> Optional[str]:
        """Retrieve OIDC client secret from key manager"""
        from cortex.security.encryption import get_key_manager
        key_manager = get_key_manager()
        # Stored under a well-known key name
        return key_manager.get_secret("elm_oidc_client_secret")

    def _dry_run_response(self, method: str, url: str, headers: Dict[str, str], payload: Any) -> requests.Response:
        """
        Simulate a mutating request in dry-run mode.
        Returns a 200 OK response with preview body.
        """
        preview = {
            "dry_run": True,
            "method": method,
            "url": url,
            "headers": {k: v for k, v in headers.items() if k.lower() not in ("authorization", "cookie")},
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "This is a dry-run preview. No changes were made to ELM. "
                       "Approve via /elm/sync-jobs to commit.",
        }

        # Create a synthetic Response object
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(preview).encode("utf-8")
        response.headers["Content-Type"] = "application/json"
        response.headers["X-Dry-Run"] = "true"

        logger.info("elm_dry_run_preview", method=method, url=url, user_id=self.user_id)
        return response

    # === Convenience methods ===

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return self._make_request("GET", url, headers=headers, params=params)

    def post(self, url: str, data: Any = None, json_data: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None, content_type: Optional[str] = None) -> requests.Response:
        return self._make_request("POST", url, headers=headers, data=data, json_data=json_data, content_type=content_type)

    def put(self, url: str, data: Any = None, json_data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None, content_type: Optional[str] = None) -> requests.Response:
        return self._make_request("PUT", url, headers=headers, data=data, json_data=json_data, content_type=content_type)

    def patch(self, url: str, data: Any = None, json_data: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None, content_type: Optional[str] = None) -> requests.Response:
        return self._make_request("PATCH", url, headers=headers, data=data, json_data=json_data, content_type=content_type)

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        return self._make_request("DELETE", url, headers=headers)

    # === Audit helpers ===

    def log_request_audit(
        self,
        action: str,
        url: str,
        method: str,
        status_code: Optional[int] = None,
        payload_hash: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Write audit log entry for ELM request"""
        from cortex.audit import log_audit, AuditAction
        from cortex.database import get_database_manager

        try:
            audit_action = getattr(AuditAction, action, AuditAction.ELM_RM_ARTIFACT_READ)
            log_audit(
                action=audit_action.value,
                user_id=self.user_id,
                resource_type="elm_request",
                resource_id=None,
                details={
                    "url": url,
                    "method": method,
                    "status_code": status_code,
                    "payload_hash": payload_hash,
                    "error": error,
                },
            )
        except Exception as e:
            logger.error("elm_audit_log_failed", error=str(e))

    @staticmethod
    def hash_payload(payload: Any) -> str:
        """Compute SHA-256 hash of payload for audit"""
        if isinstance(payload, dict):
            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        elif isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        elif payload is None:
            payload_bytes = b""
        else:
            payload_bytes = str(payload).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()
