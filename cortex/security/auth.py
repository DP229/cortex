"""
Cortex Security - Authentication Manager

JWT-based authentication for Healthcare Compliance Agent:
- User registration
- Login with rate limiting
- JWT token generation
- Refresh token management
- Session management

HIPAA compliant:
- Argon2id password hashing
- 15-minute token expiry
- Account lockout after failed attempts
- Audit logging for all auth events
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from fastapi import HTTPException, status
import structlog

from cortex.database import get_database_manager
from cortex.models import User, Session, AuditLog, UserRole
from cortex.security.encryption import hash_password, verify_password

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
    Authentication manager with JWT tokens
    
    Features:
    - User registration with password hashing
    - Login with account lockout protection
    - JWT token generation (15-minute expiry)
    - Refresh token management (7-day expiry)
    - Session tracking
    
    Usage:
        auth = AuthManager()
        
        # Register user
        user = auth.register("user@hospital.com", "password123", "John Doe", "clinician")
        
        # Login
        tokens = auth.login("user@hospital.com", "password123")
        
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
        Initialize authentication manager
        
        Args:
            jwt_secret: Secret key for JWT signing (from env or generate)
            jwt_algorithm: JWT algorithm (default: HS256)
            jwt_expiration_minutes: Access token expiry (default: 15 min)
            jwt_refresh_expiration_days: Refresh token expiry (default: 7 days)
            max_login_attempts: Max failed attempts before lockout (default: 5)
            lockout_minutes: Lockout duration in minutes (default: 15)
        """
        self.jwt_secret = jwt_secret or os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
        self.jwt_algorithm = jwt_algorithm
        self.jwt_expiration_minutes = jwt_expiration_minutes
        self.jwt_refresh_expiration_days = jwt_refresh_expiration_days
        self.max_login_attempts = max_login_attempts
        self.lockout_minutes = lockout_minutes
        
        # Validate secret
        if not self.jwt_secret or len(self.jwt_secret) < 32:
            logger.warning("JWT_SECRET is too short or missing - using generated secret (not recommended for production)")
    
    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = "clinician"
    ) -> User:
        """
        Register new user
        
        Args:
            email: User email
            password: Plain text password
            full_name: User's full name
            role: User role (admin, clinician, researcher, auditor)
        
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
            
            # Validate role
            valid_roles = [UserRole.ADMIN, UserRole.CLINICIAN, UserRole.RESEARCHER, UserRole.AUDITOR]
            if role not in [r.value for r in valid_roles]:
                raise ValueError(f"Invalid role: {role}. Must be one of {[r.value for r in valid_roles]}")
            
            # Validate password complexity
            self._validate_password(password)
            
            # Hash password
            password_hash = hash_password(password)
            
            # Encrypt full name (PHI)
            encryption_key = os.getenv("ENCRYPTION_KEY")
            encryption = EncryptionManager(encryption_key.encode() if encryption_key else None)
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
            # Expunge so detached objects don't cause session errors on access
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
        Login user and generate tokens
        
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
            # Find user
            user = session.query(User).filter(User.email == email).first()
            
            if not user:
                # Audit log failed attempt
                self._audit_log(
                    session,
                    user_id=None,
                    action="login_failed_user_not_found",
                    resource_type="user",
                    details={"email": email},
                    ip_address=ip_address
                )
                raise AuthenticationError("Invalid credentials")
            
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.utcnow():
                remaining = (user.locked_until - datetime.utcnow()).total_seconds() / 60
                raise AccountLockedError(
                    f"Account locked. Try again in {int(remaining)} minutes."
                )
            
            # Verify password
            if not verify_password(user.password_hash, password):
                # Increment failed attempts
                user.failed_login_attempts += 1
                
                # Lock account if max attempts reached
                if user.failed_login_attempts >= self.max_login_attempts:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=self.lockout_minutes)
                    
                    # Audit log lockout
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
                
                # Audit log failed attempt
                self._audit_log(
                    session,
                    user_id=user.id,
                    action="login_failed_invalid_password",
                    resource_type="user",
                    resource_id=user.id,
                    ip_address=ip_address
                )
                
                raise AuthenticationError("Invalid credentials")
            
            # Check if user is active
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
            
            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            
            # Generate tokens
            access_token = self._generate_access_token(user)
            refresh_token = self._generate_refresh_token()
            
            # Create session
            session_record = Session(
                user_id=user.id,
                refresh_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(days=self.jwt_refresh_expiration_days),
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            session.add(session_record)
            
            # Audit log successful login
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
        """
        Logout user by invalidating session
        
        Args:
            user_id: User ID
            refresh_token: Refresh token to invalidate (optional)
        
        Returns:
            True if logout successful
        """
        db = get_database_manager()
        
        with db.get_session() as session:
            # Invalidate refresh token
            if refresh_token:
                session_obj = session.query(Session).filter(
                    Session.user_id == user_id,
                    Session.refresh_token == refresh_token
                ).first()
                
                if session_obj:
                    session.delete(session_obj)
            
            # Audit log
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
        """
        Generate new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            Dictionary with new access_token
        
        Raises:
            AuthenticationError: Invalid or expired refresh token
        """
        db = get_database_manager()
        
        with db.get_session() as session:
            # Find session
            session_obj = session.query(Session).filter(
                Session.refresh_token == refresh_token
            ).first()
            
            if not session_obj:
                raise AuthenticationError("Invalid refresh token")
            
            # Check if expired
            if session_obj.expires_at < datetime.utcnow():
                session.delete(session_obj)
                session.commit()
                raise AuthenticationError("Refresh token expired")
            
            # Get user
            user = session.query(User).filter(User.id == session_obj.user_id).first()
            
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Generate new access token
            access_token = self._generate_access_token(user)
            
            # Audit log
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
        """
        Verify JWT token and return payload
        
        Args:
            token: JWT token string
        
        Returns:
            Dictionary with token payload
        
        Raises:
            TokenExpiredError: Token has expired
            AuthenticationError: Invalid token
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            # Validate fields
            if "sub" not in payload or "exp" not in payload:
                raise AuthenticationError("Invalid token payload")
            
            # Check expiration
            if datetime.utcfromtimestamp(payload["exp"]) < datetime.utcnow():
                raise TokenExpiredError("Token has expired")
            
            return payload
        
        except ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    def get_current_user(self, token: str) -> User:
        """
        Get current user from JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            User object
        
        Raises:
            AuthenticationError: Invalid token or user not found
        """
        # Verify token
        payload = self.verify_jwt(token)
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")
        
        # Get user
        db = get_database_manager()
        
        with db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise AuthenticationError("User not found")
            
            if not user.is_active:
                raise AuthenticationError("User is inactive")
            
            # Return user without session binding
            session.expunge(user)
            return user
    
    # Private methods
    
    def _generate_access_token(self, user: User) -> str:
        """Generate JWT access token"""
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=self.jwt_expiration_minutes)
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "iat": int(now.timestamp()),
            "exp": int(expiry.timestamp()),
            "type": "access"
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _generate_refresh_token(self) -> str:
        """Generate random refresh token"""
        return secrets.token_urlsafe(64)
    
    def _validate_password(self, password: str):
        """Validate password complexity"""
        min_length = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
        require_upper = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
        require_lower = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
        require_number = os.getenv("PASSWORD_REQUIRE_NUMBER", "true").lower() == "true"
        require_special = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
        
        errors = []
        
        if len(password) < min_length:
            errors.append(f"Password must be at least {min_length} characters")
        
        if require_upper and not any(c.isupper() for c in password):
            errors.append("Password must contain uppercase letter")
        
        if require_lower and not any(c.islower() for c in password):
            errors.append("Password must contain lowercase letter")
        
        if require_number and not any(c.isdigit() for c in password):
            errors.append("Password must contain number")
        
        if require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain special character")
        
        if errors:
            raise ValueError("\n".join(errors))
    
    def _audit_log(
        self,
        session,
        user_id: Optional[UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        ip_address: str = None,
        details: Dict[str, Any] = None
    ):
        """Create audit log entry"""
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details or {}
        )
        
        session.add(audit_entry)


# === Global instance ===

_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get global authentication manager instance"""
    global _auth_manager
    
    if _auth_manager is None:
        _auth_manager = AuthManager()
    
    return _auth_manager


# === FastAPI dependencies ===

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to get current user from JWT token
    
    Usage:
        @app.post("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": str(user.id)}
    
    Raises:
        HTTPException: 401 if invalid token
    """
    try:
        auth = get_auth_manager()
        token = credentials.credentials
        user = auth.get_current_user(token)
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active"""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return user


# === Export ===

__all__ = [
    "AuthManager",
    "AuthenticationError",
    "AccountLockedError",
    "TokenExpiredError",
    "get_auth_manager",
    "get_current_user",
    "get_current_active_user",
]