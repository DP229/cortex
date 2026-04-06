"""
Cortex Security - Role-Based Access Control (RBAC)

HIPAA-compliant permission system:
- Role definitions (admin, clinician, researcher, auditor)
- Permission checking
- Resource-based access control
- PHI access restrictions

Usage:
    permission_checker = PermissionManager()
    
    # Check permission
    if permission_checker.has_permission(user, "patient:read"):
        # Allow access
"""

import os
from typing import List, Dict, Set, Optional
from enum import Enum
from uuid import UUID

import structlog

from cortex.models import User, UserRole

logger = structlog.get_logger()


# === Permission Definitions ===

class Permission(str, Enum):
    """System permissions for RBAC"""
    
    # Patient permissions
    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    PATIENT_DELETE = "patient:delete"
    PATIENT_CREATE = "patient:create"
    
    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    
    # Note permissions
    NOTE_READ = "note:read"
    NOTE_WRITE = "note:write"
    NOTE_DELETE = "note:delete"
    
    # Agent permissions
    AGENT_RUN = "agent:run"
    AGENT_ADMIN = "agent:admin"
    
    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    
    # Knowledge base permissions
    KB_READ = "kb:read"
    KB_WRITE = "kb:write"
    KB_ADMIN = "kb:admin"
    
    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    
    # Consent permissions
    CONSENT_READ = "consent:read"
    CONSENT_WRITE = "consent:write"
    CONSENT_CREATE = "consent:create"
    CONSENT_REVOKE = "consent:revoke"
    
    # Team permissions
    TEAM_READ = "team:read"
    TEAM_WRITE = "team:write"
    TEAM_ADMIN = "team:admin"
    
    # Admin permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    ROLE_MANAGE = "role:manage"
    
    # Compliance permissions
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"
    BREACH_MANAGE = "breach:manage"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"


# === Role Permission Mappings ===

ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: {
        # Admin has ALL permissions
        Permission.SYSTEM_ADMIN,
        # Explicitly list all permissions
        Permission.PATIENT_READ,
        Permission.PATIENT_WRITE,
        Permission.PATIENT_DELETE,
        Permission.PATIENT_CREATE,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.NOTE_READ,
        Permission.NOTE_WRITE,
        Permission.NOTE_DELETE,
        Permission.AGENT_RUN,
        Permission.AGENT_ADMIN,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.MEMORY_DELETE,
        Permission.KB_READ,
        Permission.KB_WRITE,
        Permission.KB_ADMIN,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.CONSENT_READ,
        Permission.CONSENT_WRITE,
        Permission.CONSENT_CREATE,
        Permission.CONSENT_REVOKE,
        Permission.TEAM_READ,
        Permission.TEAM_WRITE,
        Permission.TEAM_ADMIN,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        Permission.ROLE_MANAGE,
        Permission.COMPLIANCE_READ,
        Permission.COMPLIANCE_WRITE,
        Permission.BREACH_MANAGE,
        Permission.SYSTEM_CONFIG,
    },
    
    UserRole.CLINICIAN: {
        # Clinician can access PHI
        Permission.PATIENT_READ,
        Permission.PATIENT_WRITE,
        Permission.PATIENT_CREATE,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.NOTE_READ,
        Permission.NOTE_WRITE,
        Permission.NOTE_DELETE,
        Permission.AGENT_RUN,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.KB_READ,
        Permission.KB_WRITE,
        Permission.AUDIT_READ,  # Can read own audit logs
        Permission.CONSENT_READ,
        Permission.CONSENT_WRITE,
        Permission.CONSENT_CREATE,
        Permission.CONSENT_REVOKE,
        Permission.TEAM_READ,
        Permission.TEAM_WRITE,
        Permission.COMPLIANCE_READ,
    },
    
    UserRole.RESEARCHER: {
        # Researcher can only access anonymized data
        Permission.DOCUMENT_READ,  # Anonymized only
        Permission.AGENT_RUN,  # Anonymized queries only
        Permission.MEMORY_READ,  # Anonymized only
        Permission.KB_READ,  # Anonymized only
        # NO patient:read - Cannot access PHI
        # NO note:read - Cannot access clinical notes
        Permission.COMPLIANCE_READ,  # Can view compliance reports
    },
    
    UserRole.AUDITOR: {
        # Auditor has read-only access for compliance
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.COMPLIANCE_READ,
        Permission.USER_READ,  # Can view user list for audit
        Permission.BREACH_MANAGE,  # Can manage breach notifications
    },
}


class PermissionManager:
    """
    Manage permissions for RBAC
    
    Features:
    - Check if user has permission
    - Get all permissions for role
    - Check PHI access
    - Audit permission checks
    """
    
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS
    
    def has_permission(self, user: User, permission: str) -> bool:
        """
        Check if user has specific permission
        
        Args:
            user: User object
            permission: Permission string (e.g., "patient:read")
        
        Returns:
            True if user has permission, False otherwise
        """
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Get permissions for user role
        permissions = self.role_permissions.get(user.role, set())
        
        # Handle wildcard permissions
        if Permission.SYSTEM_ADMIN in permissions:
            return True
        
        # Check specific permission
        try:
            perm = Permission(permission)
            return perm in permissions
        except ValueError:
            # Invalid permission string
            logger.warning(f"Invalid permission string: {permission}")
            return False
    
    def has_any_permission(self, user: User, permissions: List[str]) -> bool:
        """
        Check if user has ANY of the specified permissions
        
        Args:
            user: User object
            permissions: List of permission strings
        
        Returns:
            True if user has any permission, False otherwise
        """
        return any(self.has_permission(user, perm) for perm in permissions)
    
    def has_all_permissions(self, user: User, permissions: List[str]) -> bool:
        """
        Check if user has ALL of the specified permissions
        
        Args:
            user: User object
            permissions: List of permission strings
        
        Returns:
            True if user has all permissions, False otherwise
        """
        return all(self.has_permission(user, perm) for perm in permissions)
    
    def get_permissions(self, role: UserRole) -> List[str]:
        """
        Get all permissions for a role
        
        Args:
            role: UserRole enum value
        
        Returns:
            List of permission strings
        """
        permissions = self.role_permissions.get(role, set())
        return [perm.value for perm in permissions]
    
    def can_access_phi(self, user: User) -> bool:
        """
        Check if user can access Protected Health Information (PHI)
        
        Only clinicians and admins can access PHI.
        
        Args:
            user: User object
        
        Returns:
            True if user can access PHI, False otherwise
        """
        phi_roles = {UserRole.ADMIN, UserRole.CLINICIAN}
        return user.role in phi_roles
    
    def get_role_info(self, role: UserRole) -> Dict[str, any]:
        """
        Get detailed information about a role
        
        Args:
            role: UserRole enum value
        
        Returns:
            Dictionary with role information
        """
        role_descriptions = {
            UserRole.ADMIN: "Administrator with full access to all features",
            UserRole.CLINICIAN: "Clinical staff with access to PHI for patient care",
            UserRole.RESEARCHER: "Research staff with access to anonymized data only",
            UserRole.AUDITOR: "Compliance auditor with read-only access to audit logs",
        }
        
        return {
            "role": role.value,
            "description": role_descriptions.get(role, ""),
            "permissions": self.get_permissions(role),
            "can_access_phi": role in {UserRole.ADMIN, UserRole.CLINICIAN},
        }


# === FastAPI Dependency ===

class PermissionDenied(Exception):
    """Raised when user doesn't have required permission"""
    pass


def require_permission(permission: str):
    """
    FastAPI dependency for permission checking
    
    Usage:
        @app.get("/patients/{patient_id}")
        async def get_patient(
            patient_id: UUID,
            user: User = Depends(require_permission("patient:read"))
        ):
            # User has permission, proceed
            ...
    
    Args:
        permission: Required permission string
    
    Returns:
        Dependency function that verifies permission
    """
    from cortex.security.auth import get_current_active_user
    
    async def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        permission_manager = PermissionManager()
        
        if not permission_manager.has_permission(current_user, permission):
            # Log denied access
            logger.warning(
                "permission_denied",
                user_id=str(current_user.id),
                user_role=current_user.role.value,
                required_permission=permission,
            )
            
            raise PermissionDenied(
                f"Permission denied: {permission} required. "
                f"Your role ({current_user.role.value}) does not have this permission."
            )
        
        # Log granted access
        logger.info(
            "permission_granted",
            user_id=str(current_user.id),
            permission=permission,
        )
        
        return current_user
    
    return permission_checker


def require_phi_access():
    """
    FastAPI dependency for PHI access checking
    
    Usage:
        @app.get("/patients/{patient_id}")
        async def get_patient_phi(
            patient_id: UUID,
            user: User = Depends(require_phi_access())
        ):
            # User has PHI access, proceed
            ...
    
    Returns:
        Dependency function that verifies PHI access
    """
    from cortex.security.auth import get_current_active_user
    
    async def phi_access_checker(current_user: User = Depends(get_current_active_user)) -> User:
        permission_manager = PermissionManager()
        
        if not permission_manager.can_access_phi(current_user):
            # Log denied PHI access
            logger.warning(
                "phi_access_denied",
                user_id=str(current_user.id),
                user_role=current_user.role.value,
            )
            
            raise PermissionDenied(
                f"PHI access denied. Your role ({current_user.role.value}) does not "
                f"have permission to access Protected Health Information."
            )
        
        # Log granted PHI access
        logger.info(
            "phi_access_granted",
            user_id=str(current_user.id),
            user_role=current_user.role.value,
        )
        
        return current_user
    
    return phi_access_checker


# === Resource-Based Access Control ===

class ResourceAccessControl:
    """
    Resource-based access control for specific resources
    
    Provides fine-grained access control beyond simple permissions:
    - Check if user owns resource
    - Check if user is in care team
    - Check if user has role-based access
    """
    
    def can_access_patient(self, user: User, patient_id: UUID, db_session) -> bool:
        """
        Check if user can access specific patient record
        
        Users can access patient if:
        1. They are admin (full access)
        2. They are clinician AND in patient's care team
        3. They are researcher (anonymized data only - checked elsewhere)
        
        Args:
            user: User object
            patient_id: Patient UUID
            db_session: Database session
        
        Returns:
            True if user can access patient, False otherwise
        """
        from cortex.models import CareTeamMember
        
        # Admin has full access
        if user.role == UserRole.ADMIN:
            return True
        
        # Clinician must be in care team
        if user.role == UserRole.CLINICIAN:
            # Check if user is in patient's care team
            care_team_member = db_session.query(CareTeamMember).join(
                CareTeamMember.team
            ).filter(
                CareTeamMember.user_id == user.id,
                CareTeam.patient_id == patient_id,
                CareTeamMember.is_active == True
            ).first()
            
            if care_team_member:
                return True
        
        # Researcher can access anonymized data only (not implemented here)
        # Auditor can read audit logs but not direct patient data
        
        return False
    
    def can_modify_patient(self, user: User, patient_id: UUID, db_session) -> bool:
        """
        Check if user can modify specific patient record
        
        Only admins and assigned clinicians can modify patient data.
        
        Args:
            user: User object
            patient_id: Patient UUID
            db_session: Database session
        
        Returns:
            True if user can modify patient, False otherwise
        """
        from cortex.models import CareTeamMember
        
        # Admin can modify any patient
        if user.role == UserRole.ADMIN:
            return True
        
        # Clinician must be in care team
        if user.role == UserRole.CLINICIAN:
            care_team_member = db_session.query(CareTeamMember).join(
                CareTeamMember.team
            ).filter(
                CareTeamMember.user_id == user.id,
                CareTeam.patient_id == patient_id,
                CareTeamMember.is_active == True
            ).first()
            
            if care_team_member:
                return True
        
        return False


# === Export ===

__all__ = [
    "Permission",
    "PermissionManager",
    "PermissionDenied",
    "require_permission",
    "require_phi_access",
    "ResourceAccessControl",
    "ROLE_PERMISSIONS",
]