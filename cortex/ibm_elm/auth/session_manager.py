"""
IBM ELM Session Manager

Secure storage and lifecycle management of per-user ELM sessions:
- Encrypts tokens at rest (AES-256 via key manager)
- Auto-refreshes expired OIDC tokens
- Retrieves JSESSIONID / LTPA for HTTP requests
- Cleans expired sessions

All operations are audited.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from cortex.database import get_database_manager
from cortex.models import ELMSession
from cortex.security.encryption import EncryptionManager, get_key_manager

logger = logging.getLogger(__name__)


class ELMSessionManager:
    """
    Manages encrypted ELM sessions per Cortex user.

    Usage:
        mgr = ELMSessionManager()

        # Store new session after OIDC exchange
        mgr.create_session(
            user_id="...",
            auth_mode="oidc",
            jts_url="https://elm.company.com:9443/jts",
            access_token="...",
            refresh_token="...",
            jsession_id="...",
            ltpa_token="...",
            expires_in=3600
        )

        # Retrieve active session
        session = mgr.get_active_session(user_id)
        cookies = session.get_auth_cookies()
    """

    SESSION_LIFETIME_HOURS = 8  # Max session lifetime before re-auth required

    def __init__(self):
        self._encryption: Optional[EncryptionManager] = None

    def _get_encryption(self) -> EncryptionManager:
        """Lazy-init encryption manager"""
        if self._encryption is None:
            key_manager = get_key_manager()
            self._encryption = EncryptionManager(key_manager.get_encryption_key())
        return self._encryption

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string; returns ciphertext JSON string"""
        if not plaintext:
            return ""
        return self._get_encryption().encrypt(plaintext)["ciphertext"]

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string"""
        if not ciphertext:
            return ""
        try:
            return self._get_encryption().decrypt({"ciphertext": ciphertext})
        except Exception as e:
            logger.error("session_decrypt_failed", error=str(e))
            return ""

    def create_session(
        self,
        user_id: str,
        auth_mode: str,
        jts_url: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        jsession_id: Optional[str] = None,
        ltpa_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> ELMSession:
        """
        Create or replace an ELM session for a user.
        All tokens are encrypted before storage.
        """
        db = get_database_manager()

        with db.get_session() as session:
            # Deactivate any existing session for this user
            existing = session.query(ELMSession).filter(
                ELMSession.user_id == user_id,
                ELMSession.is_active == True,
            ).first()

            if existing:
                existing.is_active = False
                session.commit()
                logger.info("elm_session_deactivated_existing", user_id=user_id)

            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=self.SESSION_LIFETIME_HOURS)

            elm_session = ELMSession(
                id=str(uuid4()),
                user_id=user_id,
                auth_mode=auth_mode,
                jts_url=jts_url,
                access_token_encrypted=self._encrypt(access_token or ""),
                refresh_token_encrypted=self._encrypt(refresh_token or ""),
                jsession_id_encrypted=self._encrypt(jsession_id or ""),
                ltpa_token_encrypted=self._encrypt(ltpa_token or ""),
                token_expires_at=token_expires_at,
                session_expires_at=expires,
                last_used_at=now,
                is_active=True,
            )

            session.add(elm_session)
            session.commit()
            session.refresh(elm_session)

            logger.info(
                "elm_session_created",
                user_id=user_id,
                auth_mode=auth_mode,
                session_id=elm_session.id,
            )
            return elm_session

    def get_active_session(self, user_id: str) -> Optional[ELMSession]:
        """
        Retrieve the active session for a user.
        Checks expiry and returns None if expired.
        """
        db = get_database_manager()

        with db.get_session() as session:
            elm_session = session.query(ELMSession).filter(
                ELMSession.user_id == user_id,
                ELMSession.is_active == True,
            ).first()

            if not elm_session:
                return None

            now = datetime.now(timezone.utc)

            # Check session expiry
            if elm_session.session_expires_at and elm_session.session_expires_at < now:
                elm_session.is_active = False
                session.commit()
                logger.info("elm_session_expired", user_id=user_id, session_id=elm_session.id)
                return None

            # Update last used
            elm_session.last_used_at = now
            session.commit()

            return elm_session

    def get_auth_cookies(self, user_id: str) -> Dict[str, str]:
        """
        Get decrypted auth cookies for HTTP requests.
        Returns empty dict if no active session.
        """
        elm_session = self.get_active_session(user_id)
        if not elm_session:
            return {}

        cookies = {}
        jsession = self._decrypt(elm_session.jsession_id_encrypted or "")
        ltpa = self._decrypt(elm_session.ltpa_token_encrypted or "")

        if jsession:
            cookies["JSESSIONID"] = jsession
        if ltpa:
            cookies["LtpaToken2"] = ltpa

        return cookies

    def get_access_token(self, user_id: str) -> Optional[str]:
        """Get decrypted OIDC access token for Authorization header"""
        elm_session = self.get_active_session(user_id)
        if not elm_session:
            return None

        access_token = self._decrypt(elm_session.access_token_encrypted or "")
        return access_token if access_token else None

    def get_refresh_token(self, user_id: str) -> Optional[str]:
        """Get decrypted OIDC refresh token"""
        elm_session = self.get_active_session(user_id)
        if not elm_session:
            return None

        refresh_token = self._decrypt(elm_session.refresh_token_encrypted or "")
        return refresh_token if refresh_token else None

    def update_tokens(
        self,
        user_id: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> bool:
        """Update tokens after refresh"""
        db = get_database_manager()

        with db.get_session() as session:
            elm_session = session.query(ELMSession).filter(
                ELMSession.user_id == user_id,
                ELMSession.is_active == True,
            ).first()

            if not elm_session:
                return False

            if access_token is not None:
                elm_session.access_token_encrypted = self._encrypt(access_token)
            if refresh_token is not None:
                elm_session.refresh_token_encrypted = self._encrypt(refresh_token)
            if token_expires_at is not None:
                elm_session.token_expires_at = token_expires_at

            elm_session.last_used_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("elm_session_tokens_updated", user_id=user_id)
            return True

    def update_jazz_cookies(
        self,
        user_id: str,
        jsession_id: Optional[str] = None,
        ltpa_token: Optional[str] = None,
    ) -> bool:
        """Update Jazz session cookies"""
        db = get_database_manager()

        with db.get_session() as session:
            elm_session = session.query(ELMSession).filter(
                ELMSession.user_id == user_id,
                ELMSession.is_active == True,
            ).first()

            if not elm_session:
                return False

            if jsession_id is not None:
                elm_session.jsession_id_encrypted = self._encrypt(jsession_id)
            if ltpa_token is not None:
                elm_session.ltpa_token_encrypted = self._encrypt(ltpa_token)

            elm_session.last_used_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("elm_session_cookies_updated", user_id=user_id)
            return True

    def is_token_expired(self, user_id: str, buffer_seconds: int = 300) -> bool:
        """Check if access token is expired or near expiry"""
        elm_session = self.get_active_session(user_id)
        if not elm_session:
            return True

        if not elm_session.token_expires_at:
            return False  # No expiry known, assume valid

        return elm_session.token_expires_at < (datetime.now(timezone.utc) + timedelta(seconds=buffer_seconds))

    def invalidate_session(self, user_id: str) -> bool:
        """Deactivate a user's session (logout)"""
        db = get_database_manager()

        with db.get_session() as session:
            elm_session = session.query(ELMSession).filter(
                ELMSession.user_id == user_id,
                ELMSession.is_active == True,
            ).first()

            if elm_session:
                elm_session.is_active = False
                session.commit()
                logger.info("elm_session_invalidated", user_id=user_id)
                return True

            return False

    def cleanup_expired_sessions(self) -> int:
        """Deactivate all expired sessions. Returns count deactivated."""
        db = get_database_manager()
        now = datetime.now(timezone.utc)

        with db.get_session() as session:
            expired = session.query(ELMSession).filter(
                ELMSession.is_active == True,
                ELMSession.session_expires_at < now,
            ).all()

            count = 0
            for elm_session in expired:
                elm_session.is_active = False
                count += 1

            session.commit()
            logger.info("elm_sessions_cleaned", count=count)
            return count
