"""
Tests for RBAC Permission System

Tests:
- Permission checking
- Role permissions
- Compliance access control
- Role info retrieval
"""

import pytest
from uuid import UUID, uuid4

from cortex.security.rbac import (
    Permission,
    PermissionManager,
    ROLE_PERMISSIONS,
    PermissionDenied,
)
from cortex.models import User, UserRole


class TestPermissionManager:
    """Test permission checking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_admin_has_all_permissions(self):
        """Test admin has all permissions"""
        admin = User(
            email="admin@railway.com",
            role=UserRole.ADMIN.value,
            is_active=True
        )
        
        # Check various permissions
        assert self.perm_manager.has_permission(admin, Permission.ASSET_READ.value)
        assert self.perm_manager.has_permission(admin, Permission.REQUIREMENT_WRITE.value)
        assert self.perm_manager.has_permission(admin, Permission.USER_DELETE.value)
        assert self.perm_manager.has_permission(admin, Permission.DRP_GENERATE.value)
    
    def test_safety_engineer_has_permissions(self):
        """Test safety engineer has safety and requirement permissions"""
        safety_eng = User(
            email="safety@railway.com",
            role=UserRole.SAFETY_ENGINEER.value,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(safety_eng, Permission.REQUIREMENT_WRITE.value)
        assert self.perm_manager.has_permission(safety_eng, Permission.DRP_GENERATE.value)
        assert self.perm_manager.has_permission(safety_eng, Permission.SOUP_APPROVE.value)
        assert self.perm_manager.has_permission(safety_eng, Permission.DOCUMENT_WRITE.value)
        
        # Should NOT have these
        assert not self.perm_manager.has_permission(safety_eng, Permission.USER_DELETE.value)
        assert not self.perm_manager.has_permission(safety_eng, Permission.ROLE_MANAGE.value)
    
    def test_requirements_engineer_has_limited_permissions(self):
        """Test requirements engineer has limited permissions"""
        req_eng = User(
            email="requirements@railway.com",
            role=UserRole.REQUIREMENTS_ENGINEER.value,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(req_eng, Permission.REQUIREMENT_READ.value)
        assert self.perm_manager.has_permission(req_eng, Permission.REQUIREMENT_WRITE.value)
        assert self.perm_manager.has_permission(req_eng, Permission.DOCUMENT_READ.value)
        
        # Should NOT have approve/delete/admin/generate permissions
        assert not self.perm_manager.has_permission(req_eng, Permission.REQUIREMENT_APPROVE.value)
        assert not self.perm_manager.has_permission(req_eng, Permission.DRP_GENERATE.value)
        assert not self.perm_manager.has_permission(req_eng, Permission.SOUP_APPROVE.value)
    
    def test_auditor_has_readonly_permissions(self):
        """Test auditor has read-only permissions"""
        auditor = User(
            email="auditor@railway.com",
            role=UserRole.AUDITOR.value,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(auditor, Permission.AUDIT_READ.value)
        assert self.perm_manager.has_permission(auditor, Permission.COMPLIANCE_READ.value)
        assert self.perm_manager.has_permission(auditor, Permission.DOCUMENT_READ.value)
        
        # Should NOT have write/approve permissions
        assert not self.perm_manager.has_permission(auditor, Permission.REQUIREMENT_WRITE.value)
        assert not self.perm_manager.has_permission(auditor, Permission.SOUP_APPROVE.value)
    
    def test_has_any_permission(self):
        """Test checking any of multiple permissions"""
        safety_eng = User(
            email="safety@railway.com",
            role=UserRole.SAFETY_ENGINEER.value,
            is_active=True
        )
        
        # Should pass with at least one permission
        assert self.perm_manager.has_any_permission(
            safety_eng,
            [Permission.REQUIREMENT_WRITE.value, Permission.ROLE_MANAGE.value]
        )
        
        # Should fail with no permissions
        assert not self.perm_manager.has_any_permission(
            safety_eng,
            [Permission.USER_DELETE.value, Permission.ROLE_MANAGE.value]
        )
    
    def test_has_all_permissions(self):
        """Test checking all permissions"""
        safety_eng = User(
            email="safety@railway.com",
            role=UserRole.SAFETY_ENGINEER.value,
            is_active=True
        )
        
        # Should pass with all permissions
        assert self.perm_manager.has_all_permissions(
            safety_eng,
            [Permission.REQUIREMENT_WRITE.value, Permission.DRP_GENERATE.value]
        )
        
        # Should fail when missing one
        assert not self.perm_manager.has_all_permissions(
            safety_eng,
            [Permission.REQUIREMENT_WRITE.value, Permission.ROLE_MANAGE.value]
        )
    
    def test_get_permissions(self):
        """Test getting all permissions for role"""
        # Admin should have many permissions
        admin_perms = self.perm_manager.get_permissions(UserRole.ADMIN.value)
        assert len(admin_perms) >= 20
        
        # Requirements engineer should have few permissions
        req_perms = self.perm_manager.get_permissions(UserRole.REQUIREMENTS_ENGINEER.value)
        assert len(req_perms) < 10


class TestRoleInfo:
    """Test role information retrieval"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_get_role_info_admin(self):
        """Test getting admin role info"""
        info = self.perm_manager.get_role_info(UserRole.ADMIN.value)
        
        assert info["role"] == "admin"
        assert len(info["permissions"]) >= 20
    
    def test_get_role_info_safety_engineer(self):
        """Test getting safety engineer role info"""
        info = self.perm_manager.get_role_info(UserRole.SAFETY_ENGINEER.value)
        
        assert info["role"] == "safety_engineer"
        assert Permission.REQUIREMENT_WRITE.value in info["permissions"]
    
    def test_get_role_info_viewer(self):
        """Test getting viewer role info"""
        info = self.perm_manager.get_role_info(UserRole.VIEWER.value)
        
        assert info["role"] == "viewer"
        assert Permission.REQUIREMENT_WRITE.value not in info["permissions"]


class TestInvalidPermissions:
    """Test invalid permission handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_invalid_permission_string(self):
        """Test handling invalid permission string"""
        user = User(
            email="safety@railway.com",
            role=UserRole.SAFETY_ENGINEER.value,
            is_active=True
        )
        
        # Should return False for invalid permission
        assert self.perm_manager.has_permission(user, "invalid_permission") is False
    
    def test_inactive_user(self):
        """Test inactive user permissions"""
        inactive_user = User(
            email="inactive@railway.com",
            role=UserRole.SAFETY_ENGINEER.value,
            is_active=False
        )
        
        # Inactive user should still be checkable
        assert self.perm_manager.has_permission(inactive_user, Permission.REQUIREMENT_WRITE.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])