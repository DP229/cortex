"""
Tests for RBAC Permission System

Tests:
- Permission checking
- Role permissions
- PHI access control
- Resource-based access control
"""

import pytest
from uuid import UUID, uuid4

from cortex.security.rbac import (
    Permission,
    PermissionManager,
    ROLE_PERMISSIONS,
    PermissionDenied,
    ResourceAccessControl,
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
            email="admin@hospital.com",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        # Check various permissions
        assert self.perm_manager.has_permission(admin, Permission.PATIENT_READ)
        assert self.perm_manager.has_permission(admin, Permission.PATIENT_WRITE)
        assert self.perm_manager.has_permission(admin, Permission.USER_DELETE)
        assert self.perm_manager.has_permission(admin, Permission.SYSTEM_ADMIN)
    
    def test_clinician_has_phi_permissions(self):
        """Test clinician has PHI-related permissions"""
        clinician = User(
            email="clincian@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(clinician, Permission.PATIENT_READ)
        assert self.perm_manager.has_permission(clinician, Permission.PATIENT_WRITE)
        assert self.perm_manager.has_permission(clinician, Permission.AGENT_RUN)
        assert self.perm_manager.has_permission(clinician, Permission.NOTE_WRITE)
        
        # Should NOT have these
        assert not self.perm_manager.has_permission(clinician, Permission.USER_DELETE)
        assert not self.perm_manager.has_permission(clinician, Permission.SYSTEM_ADMIN)
    
    def test_researcher_has_limited_permissions(self):
        """Test researcher has limited permissions"""
        researcher = User(
            email="researcher@hospital.com",
            role=UserRole.RESEARCHER,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(researcher, Permission.DOCUMENT_READ)
        assert self.perm_manager.has_permission(researcher, Permission.AGENT_RUN)
        assert self.perm_manager.has_permission(researcher, Permission.MEMORY_READ)
        
        # Should NOT have PHI access
        assert not self.perm_manager.has_permission(researcher, Permission.PATIENT_READ)
        assert not self.perm_manager.has_permission(researcher, Permission.NOTE_WRITE)
    
    def test_auditor_has_readonly_permissions(self):
        """Test auditor has read-only permissions"""
        auditor = User(
            email="auditor@hospital.com",
            role=UserRole.AUDITOR,
            is_active=True
        )
        
        # Should have these
        assert self.perm_manager.has_permission(auditor, Permission.AUDIT_READ)
        assert self.perm_manager.has_permission(auditor, Permission.COMPLIANCE_READ)
        assert self.perm_manager.has_permission(auditor, Permission.USER_READ)
        
        # Should NOT have write permissions
        assert not self.perm_manager.has_permission(auditor, Permission.PATIENT_WRITE)
        assert not self.perm_manager.has_permission(auditor, Permission.NOTE_WRITE)
    
    def test_has_any_permission(self):
        """Test checking any of multiple permissions"""
        clinician = User(
            email="clinician@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=True
        )
        
        # Should pass with at least one permission
        assert self.perm_manager.has_any_permission(
            clinician,
            [Permission.PATIENT_READ, Permission.SYSTEM_ADMIN]
        )
        
        # Should fail with no permissions
        assert not self.perm_manager.has_any_permission(
            clinician,
            [Permission.USER_DELETE, Permission.SYSTEM_ADMIN]
        )
    
    def test_has_all_permissions(self):
        """Test checking all permissions"""
        clinician = User(
            email="clinician@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=True
        )
        
        # Should pass with all permissions
        assert self.perm_manager.has_all_permissions(
            clinician,
            [Permission.PATIENT_READ, Permission.PATIENT_WRITE]
        )
        
        # Should fail when missing one
        assert not self.perm_manager.has_all_permissions(
            clinician,
            [Permission.PATIENT_READ, Permission.SYSTEM_ADMIN]
        )
    
    def test_get_permissions(self):
        """Test getting all permissions for role"""
        # Admin should have many permissions
        admin_perms = self.perm_manager.get_permissions(UserRole.ADMIN)
        assert len(admin_perms) > 30  # Admin has most permissions
        
        # Researcher should have few permissions
        researcher_perms = self.perm_manager.get_permissions(UserRole.RESEARCHER)
        assert len(researcher_perms) < 10


class TestPHIAccess:
    """Test PHI access control"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_admin_can_access_phi(self):
        """Test admin can access PHI"""
        admin = User(
            email="admin@hospital.com",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        assert self.perm_manager.can_access_phi(admin) is True
    
    def test_clinician_can_access_phi(self):
        """Test clinician can access PHI"""
        clinician = User(
            email="clinician@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=True
        )
        
        assert self.perm_manager.can_access_phi(clinician) is True
    
    def test_researcher_cannot_access_phi(self):
        """Test researcher cannot access PHI"""
        researcher = User(
            email="researcher@hospital.com",
            role=UserRole.RESEARCHER,
            is_active=True
        )
        
        assert self.perm_manager.can_access_phi(researcher) is False
    
    def test_auditor_cannot_access_phi(self):
        """Test auditor cannot access PHI"""
        auditor = User(
            email="auditor@hospital.com",
            role=UserRole.AUDITOR,
            is_active=True
        )
        
        assert self.perm_manager.can_access_phi(auditor) is False


class TestRoleInfo:
    """Test role information retrieval"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_get_role_info_admin(self):
        """Test getting admin role info"""
        info = self.perm_manager.get_role_info(UserRole.ADMIN)
        
        assert info["role"] == "admin"
        assert len(info["permissions"]) > 30
        assert info["can_access_phi"] is True
    
    def test_get_role_info_clinician(self):
        """Test getting clinician role info"""
        info = self.perm_manager.get_role_info(UserRole.CLINICIAN)
        
        assert info["role"] == "clinician"
        assert Permission.PATIENT_READ.value in info["permissions"]
        assert info["can_access_phi"] is True
    
    def test_get_role_info_researcher(self):
        """Test getting researcher role info"""
        info = self.perm_manager.get_role_info(UserRole.RESEARCHER)
        
        assert info["role"] == "researcher"
        assert Permission.PATIENT_READ.value not in info["permissions"]
        assert info["can_access_phi"] is False


class TestInvalidPermissions:
    """Test invalid permission handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.perm_manager = PermissionManager()
    
    def test_invalid_permission_string(self):
        """Test handling invalid permission string"""
        user = User(
            email="user@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=True
        )
        
        # Should return False for invalid permission
        assert self.perm_manager.has_permission(user, "invalid_permission") is False
    
    def test_inactive_user(self):
        """Test inactive user permissions"""
        inactive_user = User(
            email="inactive@hospital.com",
            role=UserRole.CLINICIAN,
            is_active=False
        )
        
        # Inactive user should still be checkable
        assert self.perm_manager.has_permission(inactive_user, Permission.PATIENT_READ)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])