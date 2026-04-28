"""
Cortex Security - Role-Based Access Control (RBAC)

EN 50128 Class B / IEC 62443 compliant permission system:
- Role definitions for railway safety compliance
- Permission checking for safety-critical operations
- Asset-based access control (railway traceability)
- Requirement traceability permissions

Usage:
    permission_checker = PermissionManager()

    if permission_checker.has_permission(user, "requirement:write"):
        # Allow access
"""

from typing import List, Dict, Set, Optional
from enum import Enum
from uuid import UUID

import structlog

logger = structlog.get_logger()


class Permission(str, Enum):
    """System permissions for EN 50128 / IEC 62443 RBAC"""

    # Railway Asset permissions
    ASSET_READ = "asset:read"
    ASSET_WRITE = "asset:write"
    ASSET_DELETE = "asset:delete"
    ASSET_CREATE = "asset:create"

    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"

    # Requirement permissions (EN 50128 traceability)
    REQUIREMENT_READ = "requirement:read"
    REQUIREMENT_WRITE = "requirement:write"
    REQUIREMENT_DELETE = "requirement:delete"
    REQUIREMENT_APPROVE = "requirement:approve"

    # SOUP permissions (EN 50128 Section 4.2)
    SOUP_READ = "soup:read"
    SOUP_WRITE = "soup:write"
    SOUP_APPROVE = "soup:approve"

    # Verification/Test permissions (EN 50128 Table A.3)
    TEST_RECORD_READ = "test_record:read"
    TEST_RECORD_WRITE = "test_record:write"

    # Railway Incident permissions
    INCIDENT_READ = "incident:read"
    INCIDENT_WRITE = "incident:write"
    INCIDENT_CREATE = "incident:create"

    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # DRP permissions
    DRP_GENERATE = "drp:generate"

    # User/Admin permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    ROLE_MANAGE = "role:manage"

    # Compliance permissions
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"


# === Railway Safety Roles ===
# Defined in models.py as UserRole enum:
# ADMIN, SAFETY_ENGINEER, REQUIREMENTS_ENGINEER,
# TEST_ENGINEER, AUDITOR, VIEWER

from cortex.models import UserRole


# === Role Permission Mappings ===

ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {
    # ADMIN — full system access
    UserRole.ADMIN.value: {
        Permission.ASSET_READ, Permission.ASSET_WRITE, Permission.ASSET_DELETE, Permission.ASSET_CREATE,
        Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE, Permission.DOCUMENT_DELETE,
        Permission.REQUIREMENT_READ, Permission.REQUIREMENT_WRITE, Permission.REQUIREMENT_DELETE, Permission.REQUIREMENT_APPROVE,
        Permission.SOUP_READ, Permission.SOUP_WRITE, Permission.SOUP_APPROVE,
        Permission.TEST_RECORD_READ, Permission.TEST_RECORD_WRITE,
        Permission.INCIDENT_READ, Permission.INCIDENT_WRITE, Permission.INCIDENT_CREATE,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.DRP_GENERATE,
        Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE, Permission.ROLE_MANAGE,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_WRITE,
    },

    # SAFETY_ENGINEER — manages safety requirements, hazard analysis, IEC 62304 Class B/C
    UserRole.SAFETY_ENGINEER.value: {
        Permission.ASSET_READ, Permission.ASSET_WRITE, Permission.ASSET_CREATE,
        Permission.REQUIREMENT_READ, Permission.REQUIREMENT_WRITE, Permission.REQUIREMENT_APPROVE,
        Permission.SOUP_READ, Permission.SOUP_WRITE, Permission.SOUP_APPROVE,
        Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE,
        Permission.TEST_RECORD_READ, Permission.TEST_RECORD_WRITE,
        Permission.INCIDENT_READ, Permission.INCIDENT_WRITE, Permission.INCIDENT_CREATE,
        Permission.AUDIT_READ,
        Permission.DRP_GENERATE,
        Permission.COMPLIANCE_READ,
    },

    # REQUIREMENTS_ENGINEER — authors and traces EN 50128 requirements
    UserRole.REQUIREMENTS_ENGINEER.value: {
        Permission.ASSET_READ,
        Permission.REQUIREMENT_READ, Permission.REQUIREMENT_WRITE,
        Permission.SOUP_READ,
        Permission.DOCUMENT_READ,
        Permission.AUDIT_READ,
    },

    # TEST_ENGINEER — executes verification (EN 50128 Table A.3)
    UserRole.TEST_ENGINEER.value: {
        Permission.ASSET_READ,
        Permission.REQUIREMENT_READ,
        Permission.TEST_RECORD_READ, Permission.TEST_RECORD_WRITE,
        Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE,
        Permission.AUDIT_READ,
    },

    # AUDITOR — read-only for EN 50128 / IEC 62443 audits
    UserRole.AUDITOR.value: {
        Permission.ASSET_READ,
        Permission.REQUIREMENT_READ,
        Permission.SOUP_READ,
        Permission.DOCUMENT_READ,
        Permission.TEST_RECORD_READ,
        Permission.INCIDENT_READ,
        Permission.AUDIT_READ,
        Permission.COMPLIANCE_READ,
    },

    # VIEWER — read-only for all compliance documents
    UserRole.VIEWER.value: {
        Permission.ASSET_READ,
        Permission.REQUIREMENT_READ,
        Permission.SOUP_READ,
        Permission.DOCUMENT_READ,
        Permission.TEST_RECORD_READ,
        Permission.INCIDENT_READ,
    },
}


class PermissionManager:
    """
    EN 50128 Class B compliant permission manager.

    Features:
    - Check if user has permission
    - Get all permissions for role
    - Railway asset-based access control
    - Audit permission checks
    """

    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS

    def has_permission(self, user, permission: str) -> bool:
        """
        Check if user has specific permission.

        Args:
            user: User object
            permission: Permission string (e.g., "requirement:read")

        Returns:
            True if user has permission, False otherwise
        """
        # Admin has all permissions
        if user.role == UserRole.ADMIN.value:
            return True

        permissions = self.role_permissions.get(user.role, set())

        try:
            perm = Permission(permission)
            return perm in permissions
        except ValueError:
            logger.warning(f"Invalid permission string: {permission}")
            return False

    def has_any_permission(self, user, permissions: List[str]) -> bool:
        """Check if user has ANY of the specified permissions"""
        return any(self.has_permission(user, perm) for perm in permissions)

    def has_all_permissions(self, user, permissions: List[str]) -> bool:
        """Check if user has ALL of the specified permissions"""
        return all(self.has_permission(user, perm) for perm in permissions)

    def get_permissions(self, role: str) -> List[str]:
        """Get all permissions for a role"""
        permissions = self.role_permissions.get(role, set())
        return [perm.value for perm in permissions]

    def get_role_info(self, role: str) -> Dict:
        """Get detailed information about a role"""
        role_descriptions = {
            UserRole.ADMIN.value: "Administrator with full system access",
            UserRole.SAFETY_ENGINEER.value: "Safety engineer — manages safety requirements, hazard analysis, IEC 62304 Class B/C compliance",
            UserRole.REQUIREMENTS_ENGINEER.value: "Requirements engineer — authors and traces EN 50128 requirements",
            UserRole.TEST_ENGINEER.value: "Test engineer — executes verification (EN 50128 Table A.3)",
            UserRole.AUDITOR.value: "Compliance auditor — read-only access for EN 50128 / IEC 62443 audits",
            UserRole.VIEWER.value: "Read-only viewer for all compliance documents",
        }

        return {
            "role": role,
            "description": role_descriptions.get(role, ""),
            "permissions": self.get_permissions(role),
        }


# === FastAPI Dependency ===

class PermissionDenied(Exception):
    """Raised when user doesn't have required permission"""
    pass


def require_permission(permission: str):
    """
    FastAPI dependency for permission checking.

    Usage:
        @app.get("/requirements/{req_id}")
        async def get_requirement(
            req_id: UUID,
            user: User = Depends(require_permission("requirement:read"))
        ):
            # User has permission, proceed
            ...
    """
    from cortex.security.auth import get_current_active_user

    async def permission_checker(current_user=Depends(get_current_active_user)):
        permission_manager = PermissionManager()

        if not permission_manager.has_permission(current_user, permission):
            logger.warning(
                "permission_denied",
                user_id=str(current_user.id),
                user_role=current_user.role,
                required_permission=permission,
            )
            raise PermissionDenied(
                f"Permission denied: {permission} required. "
                f"Your role ({current_user.role}) does not have this permission."
            )

        logger.info(
            "permission_granted",
            user_id=str(current_user.id),
            permission=permission,
        )
        return current_user

    return permission_checker
