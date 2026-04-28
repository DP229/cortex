"""
Cortex Authentication API Endpoints

FastAPI endpoints for authentication:
- User registration
- User login
- Token refresh
- Logout
- User management

All endpoints log to audit trail for EN 50128 compliance.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
import structlog

from cortex.security.auth import (
    AuthManager,
    get_auth_manager,
    get_current_user,
    get_current_active_user,
    AuthenticationError,
    AccountLockedError,
    TokenExpiredError,
)
from cortex.database import get_session, get_database_manager
from cortex.models import User, UserRole, AuditLog
from cortex.security.encryption import EncryptionManager

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])

# === Pydantic Models ===

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    full_name: str
    role: str = "clinician"
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain number')
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError('Password must contain special character')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = [r.value for r in UserRole]
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {valid_roles}')
        return v


class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: str


class UserResponse(BaseModel):
    """User response"""
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain number')
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError('Password must contain special character')
        return v


# === Helper Functions ===

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def encrypt_user_name(full_name: str) -> str:
    """Encrypt user's full name (PHI)"""
    import os
    encryption_key = os.getenv("ENCRYPTION_KEY")
    encryption = EncryptionManager(encryption_key.encode() if encryption_key else None)
    encrypted = encryption.encrypt(full_name)
    # Store both ciphertext and nonce (joined by ':') for proper decryption
    return f"{encrypted['ciphertext']}:{encrypted['nonce']}"


def decrypt_user_name(encrypted_name: str) -> str:
    """Decrypt user's full name"""
    import os
    encryption_key = os.getenv("ENCRYPTION_KEY")
    encryption = EncryptionManager(encryption_key.encode() if encryption_key else None)
    parts = encrypted_name.split(":")
    if len(parts) != 2:
        return "[Redacted]"  # Legacy format or invalid
    return encryption.decrypt({"ciphertext": parts[0], "nonce": parts[1]})


# === Endpoints ===

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    req: UserRegisterRequest
):
    """
    Register new user
    
    **Roles:**
    - admin: Full access
    - clinician: PHI access (doctors, nurses)
    - researcher: Anonymized data only
    - auditor: Read-only audit access
    
    **Password Requirements:**
    - Minimum 12 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    try:
        auth = get_auth_manager()
        
        # Get client info for audit
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Register user
        user = auth.register(
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            role=req.role
        )
        
        logger.info(
            "user_registered",
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            ip_address=client_ip
        )
        
        # Decrypt name for response
        full_name = decrypt_user_name(user.full_name_encrypted)
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=full_name,
            role=user.role,
            is_active=user.is_active,
            last_login=user.last_login
        )
        
    except ValueError as e:
        logger.warning("registration_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("registration_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    req: UserLoginRequest
):
    """
    Login and get access token
    
    **Returns:**
    - access_token: JWT token (15-minute expiry)
    - refresh_token: Refresh token (7-day expiry)
    - expires_in: Token expiry in seconds
    
    **Account Lockout:**
    After 5 failed login attempts, account is locked for 15 minutes.
    """
    try:
        auth = get_auth_manager()
        
        # Get client info
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Login
        tokens = auth.login(
            email=req.email,
            password=req.password,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        logger.info(
            "user_login",
            user_id=tokens["user_id"],
            email=req.email,
            ip_address=client_ip
        )
        
        return TokenResponse(**tokens)
        
    except AccountLockedError as e:
        logger.warning(
            "account_locked",
            email=req.email,
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(e)
        )
        
    except AuthenticationError as e:
        logger.warning(
            "login_failed",
            email=req.email,
            ip_address=client_ip,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
        
    except Exception as e:
        logger.error("login_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: TokenRefreshRequest):
    """
    Refresh access token using refresh token
    
    **Usage:**
    Use the refresh_token from /auth/login to get a new access_token
    when your current token expires (after 15 minutes).
    """
    try:
        auth = get_auth_manager()
        
        tokens = auth.refresh_access_token(req.refresh_token)
        
        logger.info("token_refreshed")
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=req.refresh_token,
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
            user_id="",  # Not included in refresh response
            role=""      # Not included in refresh response
        )
        
    except AuthenticationError as e:
        logger.warning("token_refresh_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout and invalidate session
    
    **Audit:** This action is logged in the audit trail
    """
    try:
        auth = get_auth_manager()
        auth.logout(user_id=current_user.id)
        
        logger.info("user_logout", user_id=str(current_user.id))
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error("logout_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information
    
    **Requires:** Valid JWT token in Authorization header
    """
    try:
        # Decrypt name
        full_name = decrypt_user_name(current_user.full_name_encrypted)
        
        return UserResponse(
            id=str(current_user.id),
            email=current_user.email,
            full_name=full_name,
            role=current_user.role,
            is_active=current_user.is_active,
            last_login=current_user.last_login
        )
    except Exception as e:
        logger.error("get_me_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@router.post("/change-password")
async def change_password(
    request: Request,
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Change user password
    
    **Password Requirements:**
    - Minimum 12 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter  
    - At least 1 number
    - At least 1 special character
    """
    from cortex.security.encryption import verify_password, hash_password
    
    try:
        # Verify old password
        if not verify_password(current_user.password_hash, req.old_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid old password"
            )
        
        # Validate new password
        if req.old_password == req.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from old password"
            )
        
        # Hash new password
        new_hash = hash_password(req.new_password)
        
        # Update password
        db = get_database_manager()
        with db.get_session() as session:
            user = session.query(User).filter(User.id == current_user.id).first()
            user.password_hash = new_hash
            
            # Audit log
            audit = AuditLog(
                user_id=user.id,
                action="password_changed",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request),
                details={"user_email": user.email}
            )
            session.add(audit)
            
            session.commit()
        
        logger.info("password_changed", user_id=str(current_user.id))
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("change_password_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


# === Admin Endpoints ===

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List users (admin only)
    
    **Query Parameters:**
    - role: Filter by role (admin, clinician, researcher, auditor)
    - is_active: Filter by active status
    - limit: Maximum results (default 50)
    - offset: Pagination offset
    """
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        db = get_database_manager()
        
        with db.get_session() as session:
            query = session.query(User)
            
            if role:
                query = query.filter(User.role == role)
            
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            
            users = query.offset(offset).limit(limit).all()
            
            # Decrypt names
            users_response = []
            for user in users:
                full_name = decrypt_user_name(user.full_name_encrypted)
                users_response.append(UserResponse(
                    id=str(user.id),
                    email=user.email,
                    full_name=full_name,
                    role=user.role,
                    is_active=user.is_active,
                    last_login=user.last_login
                ))
            
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="list_users",
                resource_type="user",
                ip_address=get_client_ip(request),
                details={"role_filter": role, "is_active_filter": is_active, "count": len(users)}
            )
            session.add(audit)
            session.commit()
            
            return users_response
            
    except Exception as e:
        logger.error("list_users_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Deactivate user account (admin only)
    
    **Note:** This does not delete the user, only marks as inactive.
    User data is retained for audit purposes (EN 50128 requirement — minimum 10 years).
    """
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        db = get_database_manager()
        
        with db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            if user.id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate yourself"
                )
            
            user.is_active = False
            
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="user_deactivated",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request),
                details={"deactivated_user": user.email}
            )
            session.add(audit)
            
            session.commit()
            
            logger.info(
                "user_deactivated",
                admin_id=str(current_user.id),
                deactivated_id=str(user_id)
            )
            
            return {"message": f"User {user.email} deactivated successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("deactivate_user_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Activate user account (admin only)"""
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        db = get_database_manager()
        
        with db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="user_activated",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request),
                details={"activated_user": user.email}
            )
            session.add(audit)
            
            session.commit()
            
            logger.info(
                "user_activated",
                admin_id=str(current_user.id),
                activated_id=str(user_id)
            )
            
            return {"message": f"User {user.email} activated successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("activate_user_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )


# === Health Check ===

@router.get("/health")
async def auth_health():
    """Authentication service health check"""
    return {"status": "healthy", "service": "authentication"}