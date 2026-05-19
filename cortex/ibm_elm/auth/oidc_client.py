"""
IBM ELM OIDC Authentication Client

Implements OpenID Connect authentication for IBM Jazz Team Server / ELM:
- OIDC Discovery (fetch .well-known/openid-configuration)
- Authorization Code + PKCE flow (or backend channel)
- Token exchange: code → id_token + access_token
- Token refresh with automatic expiry handling
- Jazz session establishment: access_token → JSESSIONID / LtpaToken2

All tokens are encrypted at rest via cortex.security.encryption.
"""

import os
import base64
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import logging

import requests
import structlog

logger = structlog.get_logger()


class OIDCError(Exception):
    """OIDC authentication failed"""
    pass


class OIDCTokenExpiredError(OIDCError):
    """OIDC access token has expired and refresh failed"""
    pass


class OIDCClient:
    """
    OIDC client for IBM ELM / Jazz Team Server authentication.

    Usage:
        client = OIDCClient(
            issuer_url="https://okta.company.com",
            client_id="cortex-elm-client",
            client_secret="...",  # from key manager
            redirect_uri="https://cortex.company.com/elm/auth/callback"
        )

        # Step 1: Generate authorization URL
        auth_url, code_verifier = client.get_authorization_url(state="random_state")

        # Step 2: Exchange code for tokens
        tokens = client.exchange_code_for_tokens(auth_code, code_verifier)

        # Step 3: Establish Jazz session
        jazz_cookies = client.establish_jazz_session(
            jts_url="https://elm.company.com:9443/jts",
            access_token=tokens["access_token"]
        )
    """

    def __init__(
        self,
        issuer_url: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.issuer_url = issuer_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or "urn:ietf:wg:oauth:2.0:oob"
        self.scopes = scopes or ["openid", "profile"]
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self._discovery_data: Optional[Dict[str, Any]] = None
        self._session = requests.Session()
        self._session.verify = verify_ssl

    def _discover(self) -> Dict[str, Any]:
        """Fetch OIDC discovery document (.well-known/openid-configuration)"""
        if self._discovery_data is not None:
            return self._discovery_data

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        logger.info("oidc_discovery_start", url=discovery_url)

        try:
            response = self._session.get(discovery_url, timeout=self.timeout)
            response.raise_for_status()
            self._discovery_data = response.json()
            logger.info("oidc_discovery_success", issuer=self._discovery_data.get("issuer"))
            return self._discovery_data
        except requests.RequestException as e:
            logger.error("oidc_discovery_failed", error=str(e), url=discovery_url)
            raise OIDCError(f"OIDC discovery failed: {e}")

    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate authorization URL with PKCE.

        Returns:
            Tuple of (authorization_url, code_verifier)
        """
        discovery = self._discover()
        auth_endpoint = discovery.get("authorization_endpoint")
        if not auth_endpoint:
            raise OIDCError("authorization_endpoint not found in OIDC discovery")

        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode("ascii").rstrip("=")
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode("ascii").rstrip("=")

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "redirect_uri": self.redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state or secrets.token_urlsafe(16),
        }

        auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
        logger.info("oidc_authorization_url_generated", client_id=self.client_id)
        return auth_url, code_verifier

    def exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.

        Returns:
            Dict with access_token, id_token, refresh_token, expires_in, token_type
        """
        discovery = self._discover()
        token_endpoint = discovery.get("token_endpoint")
        if not token_endpoint:
            raise OIDCError("token_endpoint not found in OIDC discovery")

        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }

        if self.client_secret:
            payload["client_secret"] = self.client_secret

        logger.info("oidc_token_exchange_start", token_endpoint=token_endpoint)

        try:
            response = self._session.post(
                token_endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            tokens = response.json()

            if "error" in tokens:
                raise OIDCError(f"Token endpoint error: {tokens['error']} - {tokens.get('error_description', '')}")

            logger.info("oidc_token_exchange_success")
            return tokens
        except requests.RequestException as e:
            logger.error("oidc_token_exchange_failed", error=str(e))
            raise OIDCError(f"Token exchange failed: {e}")

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Returns:
            New token dict (may include new refresh_token)
        """
        discovery = self._discover()
        token_endpoint = discovery.get("token_endpoint")
        if not token_endpoint:
            raise OIDCError("token_endpoint not found in OIDC discovery")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }

        if self.client_secret:
            payload["client_secret"] = self.client_secret

        logger.info("oidc_token_refresh_start")

        try:
            response = self._session.post(
                token_endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            tokens = response.json()

            if "error" in tokens:
                raise OIDCTokenExpiredError(
                    f"Refresh failed: {tokens['error']} - {tokens.get('error_description', '')}"
                )

            logger.info("oidc_token_refresh_success")
            return tokens
        except requests.RequestException as e:
            logger.error("oidc_token_refresh_failed", error=str(e))
            raise OIDCTokenExpiredError(f"Token refresh failed: {e}")

    def establish_jazz_session(
        self,
        jts_url: str,
        access_token: str,
    ) -> Dict[str, str]:
        """
        Establish Jazz-authenticated session using OIDC access token.

        IBM ELM 7.x supports presenting an OIDC access token to the
        Jazz authentication check endpoint, which returns JSESSIONID
        and/or LtpaToken2 cookies.

        Args:
            jts_url: Full JTS URL, e.g. https://elm.company.com:9443/jts
            access_token: Valid OIDC access token

        Returns:
            Dict of cookie name -> value (e.g., {"JSESSIONID": "...", "LtpaToken2": "..."})
        """
        jts_url = jts_url.rstrip("/")
        # Primary endpoint: Jazz auth check with bearer token
        auth_check_url = f"{jts_url}/auth/authcheck"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        logger.info("jazz_session_establish_start", jts_url=jts_url)

        try:
            response = self._session.get(
                auth_check_url,
                headers=headers,
                allow_redirects=True,
                timeout=self.timeout,
            )

            cookies = {}
            for cookie in response.cookies:
                cookies[cookie.name] = cookie.value

            if not cookies:
                # Fallback: try form-auth handshake or check if already authenticated
                logger.warning("jazz_session_no_cookies", status=response.status_code)
                # Some Jazz servers require a POST to jauth-proxy or jts/jauth-check
                fallback_url = f"{jts_url}/jauth-check"
                response2 = self._session.get(
                    fallback_url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=self.timeout,
                )
                for cookie in response2.cookies:
                    cookies[cookie.name] = cookie.value

            logger.info("jazz_session_establish_done", cookies=list(cookies.keys()))
            return cookies

        except requests.RequestException as e:
            logger.error("jazz_session_establish_failed", error=str(e))
            raise OIDCError(f"Jazz session establishment failed: {e}")

    def verify_token(self, access_token: str) -> Dict[str, Any]:
        """Verify access token via introspection or userinfo endpoint"""
        discovery = self._discover()

        # Try userinfo first
        userinfo_endpoint = discovery.get("userinfo_endpoint")
        if userinfo_endpoint:
            try:
                response = self._session.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    return response.json()
            except requests.RequestException:
                pass

        # Try introspection
        introspection_endpoint = discovery.get("introspection_endpoint")
        if introspection_endpoint and self.client_secret:
            try:
                response = self._session.post(
                    introspection_endpoint,
                    data={"token": access_token, "client_id": self.client_id, "client_secret": self.client_secret},
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    return response.json()
            except requests.RequestException:
                pass

        return {"active": False}

    def get_token_expiry(self, token_response: Dict[str, Any]) -> Optional[datetime]:
        """Calculate token expiry from token response"""
        expires_in = token_response.get("expires_in")
        if expires_in:
            return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        return None
