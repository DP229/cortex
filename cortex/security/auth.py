"""
Cortex Security - Authentication Manager

EN 50128 / IEC 62443 compliant JWT-based authentication:
- User registration with Argon2id password hashing
- Login with rate limiting and account lockout
- JWT token generation (15-minute expiry)
- Refresh token management (7-day expiry)
- Session management with audit logging
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from cortex.database import get_database_manager
from cortex.models import User, Session, AuditLog, UserRole
from cortex.security.encryption import (
    hash_password,
    verify_password,
    get_key_manager,
)

logger = structlog.get_logger()


class AuthenticationError(Exception):
    """Authentication failed"""
    pass


class AccountLockedError(AuthenticationError):
    """Account is locked due to too many failed login attempts"""
    pass


class TokenExpiredError(AuthenticationError):
    """Token has expired"""
    pass


class AuthManager:
    """
    Authentication manager with JWT tokens.

    Features:
    - User registration with Argon2id password hashing
    - Login with account lockout protection (EN 50128 Class B)
    - JWT token generation (15-minute expiry)
    - Refresh token management (7-day expiry)
    - Session tracking with audit logging

    Usage:
        auth = AuthManager()

        # Register user
        user = auth.register("engineer@railway.com", "password123", "Jane Smith", "safety_engineer")

        # Login
        tokens = auth.login("engineer@railway.com", "password123")

        # Verify token
        payload = auth.verify_jwt(tokens["access_token"])
    """

    def __init__(
        self,
        jwt_secret: str = None,
        jwt_algorithm: str = "HS256",
        jwt_expiration_minutes: int = 15,
        jwt_refresh_expiration_days: int = 7,
        max_login_attempts: int = 5,
        lockout_minutes: int = 15
    ):
        """
        Initialize authentication manager.

        Args:
            jwt_secret: Secret key for JWT signing (from env or ~/.cortex/keys/jwt.key)
            jwt_algorithm: JWT algorithm (default: HS256)
            jwt_expiration_minutes: Access token expiry (default: 15 min)
            jwt_refresh_expiration_days: Refresh token expiry (default: 7 days)
            max_login_attempts: Max failed attempts before lockout (default: 5)
            lockout_minutes: Lockout duration in minutes (default: 15)
        """
        self.jwt_secret = jwt_secret or self._load_jwt_secret()
        self.jwt_algorithm = jwt_algorithm
        self.jwt_expiration_minutes = jwt_expiration_minutes
        self.jwt_refresh_expiration_days = jwt_refresh_expiration_days
        self.max_login_attempts = max_login_attempts
        self.lockout_minutes = lockout_minutes

        # Validate secret
        if not self.jwt_secret or len(self.jwt_secret) < 32:
            import structlog
            logger2 = structlog.get_logger()
            logger2.warning("JWT_SECRET is too short or missing - using generated secret (not recommended for production)")

    def _load_jwt_secret(self) -> str:
        """Load JWT secret from env or persist to ~/.cortex/keys/jwt.key"""
        # Env var takes priority (for containers/CI)
        env_secret = os.getenv("JWT_SECRET")
        if env_secret and len(env_secret) >= 32:
            return env_secret

        # Try file-based secret
        jwt_key_file = os.path.expanduser("~/.cortex/keys/jwt.key")
        if os.path.exists(jwt_key_file):
            try:
                with open(jwt_key_file, "r") as f:
                    secret = f.read().strip()
                if len(secret) >= 32:
                    return secret
            except Exception:
                pass

        # Generate and persist new secret
        new_secret = secrets.token_urlsafe(48)
        try:
            key_dir = os.path.dirname(jwt_key_file)
            os.makedirs(key_dir, mode=0o700, exist_ok=True)
            with open(jwt_key_file, "w") as f:
                f.write(new_secret)
            os.chmod(jwt_key_file, 0o600)
        except Exception:
            pass

        return new_secret

    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = "safety_engineer"
    ) -> User:
        """
        Register new user.

        Args:
            email: User email
            password: Plain text password
            full_name: User's full name
            role: User role (admin, safety_engineer, operations, compliance_officer, auditor, maintenance_technician)

        Returns:
            Created User object

        Raises:
            ValueError: If user already exists or invalid data
        """
        from cortex.security.encryption import EncryptionManager

        db = get_database_manager()

        with db.get_session() as session:
            # Check if user exists
            existing = session.query(User).filter(User.email == email).first()
            if existing:
                raise ValueError(f"User with email {email} already exists")

            # Validate role against enum
            valid_roles = [r.value for r in UserRole]
            if role not in valid_roles:
                raise ValueError(f"Invalid role: {role}. Must be one of {valid_roles}")

            # Validate password complexity
            self._validate_password(password)

            # Hash password
            password_hash = hash_password(password)

            # Encrypt full name (key NEVER logged — EN 50128 Class B requirement)
            key_manager = get_key_manager()
            encryption = EncryptionManager(key_manager.get_encryption_key())
            encrypted_name = encryption.encrypt(full_name)

            # Create user
            user = User(
                email=email,
                password_hash=password_hash,
                full_name_encrypted=encrypted_name["ciphertext"],
                role=role,
                is_active=True
            )

            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            session.expunge_all()

            # Audit log
            self._audit_log(
                session,
                user_id=None,
                action="user_registered",
                resource_type="user",
                resource_id=user.id,
                details={"email": email, "role": role}
            )

            logger.info(f"User registered: {email} with role {role}")

            return user

    def login(
        self,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> Dict[str, Any]:
        """
        Login user and generate tokens.

        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP address (for audit)
            user_agent: Client user agent (for audit)

        Returns:
            Dictionary with access_token and refresh_token

        Raises:
            AuthenticationError: Invalid credentials
            AccountLockedError: Account is locked
        """
        db = get_database_manager()

        with db.get_session() as session:
            user = session.query(User).filter(User.email == email).first()

            if not user:
                self._audit_log(
                    session,
                    user_id=None,
                    action="login_failed_user_not_found",
                    resource_type="user",
                    details={"email": email},
                    ip_address=ip_address
                )
                raise AuthenticationError("Invalid credentials")

            if user.locked_until and user.locked_until > datetime.utcnow():
                remaining = (user.locked_until - datetime.utcnow()).total_seconds() / 60
                raise AccountLockedError(
                    f"Account locked. Try again in {int(remaining)} minutes."
                )

            if not verify_password(user.password_hash, password):
                user.failed_login_attempts += 1

                if user.failed_login_attempts >= self.max_login_attempts:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=self.lockout_minutes)

                    self._audit_log(
                        session,
                        user_id=user.id,
                        action="account_locked",
                        resource_type="user",
                        resource_id=user.id,
                        ip_address=ip_address,
                        details={"reason": "max_failed_attempts"}
                    )

                    logger.warning(f"Account locked for user {email}")

                session.commit()

                self._audit_log(
                    session,
                    user_id=user.id,
                    action="login_failed_invalid_password",
                    resource_type="user",
                    resource_id=user.id,
                    ip_address=ip_address
                )

                raise AuthenticationError("Invalid credentials")

            if not user.is_active:
                self._audit_log(
                    session,
                    user_id=user.id,
                    action="login_failed_inactive",
                    resource_type="user",
                    resource_id=user.id,
                    ip_address=ip_address
                )
                raise AuthenticationError("Account is inactive")

            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()

            access_token = self._generate_access_token(user)
            refresh_token = self._generate_refresh_token()

            session_record = Session(
                user_id=user.id,
                refresh_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(days=self.jwt_refresh_expiration_days),
                ip_address=ip_address,
                user_agent=user_agent
            )

            session.add(session_record)

            self._audit_log(
                session,
                user_id=user.id,
                action="login_success",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address,
                details={"user_agent": user_agent}
            )

            session.commit()

            logger.info(f"User logged in: {email}")

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.jwt_expiration_minutes * 60,
                "user_id": str(user.id),
                "role": user.role
            }

    def logout(self, user_id: UUID, refresh_token: str = None) -> bool:
        """Logout user by invalidating session."""
        db = get_database_manager()

        with db.get_session() as session:
            if refresh_token:
                session_obj = session.query(Session).filter(
                    Session.user_id == user_id,
                    Session.refresh_token == refresh_token
                ).first()

                if session_obj:
                    session.delete(session_obj)

            self._audit_log(
                session,
                user_id=user_id,
                action="logout",
                resource_type="user",
                resource_id=user_id
            )

            session.commit()

            logger.info(f"User logged out: {user_id}")

            return True

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """Generate new access token using refresh token."""
        db = get_database_manager()

        with db.get_session() as session:
            session_obj = session.query(Session).filter(
                Session.refresh_token == refresh_token
            ).first()

            if not session_obj:
                raise AuthenticationError("Invalid refresh token")

            if session_obj.expires_at < datetime.utcnow():
                session.delete(session_obj)
                session.commit()
                raise AuthenticationError("Refresh token expired")

            user = session.query(User).filter(User.id == session_obj.user_id).first()

            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            access_token = self._generate_access_token(user)

            self._audit_log(
                session,
                user_id=user.id,
                action="token_refresh",
                resource_type="user",
                resource_id=user.id
            )

            session.commit()

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": self.jwt_expiration_minutes * 60
            }

    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )

            if "sub" not in payload or "exp" not in payload:
                raise AuthenticationError("Invalid token payload")

            if datetime.utcfromtimestamp(payload["exp"]) < datetime.utcnow():
                raise TokenExpiredError("Token has expired")

            return payload

        except ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")

        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}")

    def get_current_user(self, token: str) -> User:
        """Get current user from JWT token."""
        payload = self.verify_jwt(token)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")

        db = get_database_manager()

        with db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()

            if not user:
                raise AuthenticationError("User not found")

            if not user.is_active:
                raise AuthenticationError("User is inactive")

            session.expunge(user)
            return user

    # === Private Methods ===

    def _generate_access_token(self, user: User) -> str:
        """Generate JWT access token"""
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=self.jwt_expiration_minutes)

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "iat": now,
            "exp": expiry,
            "type": "access"
        }

        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def _generate_refresh_token(self) -> str:
        """Generate refresh token"""
        return secrets.token_urlsafe(32)

    def _validate_password(self, password: str) -> None:
        """
        Validate password meets EN 50128 complexity requirements.

        Requirements:
        - Minimum 12 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number
        - At least 1 special character
        """
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least 1 uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least 1 lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least 1 number")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            raise ValueError("Password must contain at least 1 special character")

    def _audit_log(
        self,
        session,
        user_id: Optional[UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Write audit log entry."""
        try:
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                details=details
            )
            session.add(audit_entry)
        except Exception as e:
            logger.error("audit_log_failed", error=str(e), action=action)


# === FastAPI Dependencies ===

def get_auth_manager() -> AuthManager:
    """Get or create AuthManager singleton."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


_auth_manager_instance: Optional[AuthManager] = None


async def get_current_user(credentials) -> User:
    """
    FastAPI dependency to get current authenticated user.

    Args:
        credentials: HTTPAuthorizationCredentials from FastAPI Security

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    credentials_obj = HTTPAuthorizationCredentials(**credentials)

    auth = get_auth_manager()
    try:
        user = auth.get_current_user(credentials_obj.credentials)
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
