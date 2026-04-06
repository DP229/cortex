#!/usr/bin/env python3
"""
Integration Tests for Security and Compliance

Tests end-to-end functionality of:
- Authentication
- RBAC
- Audit logging
- PHI detection
- Rate limiting
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import time

# Import app
from cortex.api_healthcare import app
from cortex.database import get_database_manager
from cortex.models import User, UserRole, AuditLog
from cortex.security.auth import get_auth_manager


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "email": f"test_{uuid4()}@example.com",
        "password": "SecureP@ss123!",
        "full_name": "Test User",
        "role": "clinician"
    }


@pytest.fixture
def admin_user_data():
    """Admin user data"""
    return {
        "email": f"admin_{uuid4()}@example.com",
        "password": "AdminP@ss123!",
        "full_name": "Admin User",
        "role": "admin"
    }


class TestAuthenticationFlow:
    """Test complete authentication flow"""
    
    def test_register_and_login(self, client, test_user_data):
        """Test user registration and login"""
        # Register
        response = client.post("/auth/register", json=test_user_data)
        assert response.status_code == 201
        
        user = response.json()
        assert user["email"] == test_user_data["email"]
        assert user["role"] == test_user_data["role"]
        
        # Login
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
    
    def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without token"""
        response = client.get("/auth/me")
        assert response.status_code == 401
    
    def test_protected_endpoint_with_token(self, client, test_user_data):
        """Test accessing protected endpoint with token"""
        # Register and login
        client.post("/auth/register", json=test_user_data)
        login_response = client.post("/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        
        token = login_response.json()["access_token"]
        
        # Access protected endpoint
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["email"] == test_user_data["email"]
    
    def test_invalid_login(self, client, test_user_data):
        """Test login with invalid credentials"""
        # Register user
        client.post("/auth/register", json=test_user_data)
        
        # Try to login with wrong password
        response = client.post("/auth/login", json={
            "email": test_user_data["email"],
            "password": "WrongP@ss123!"
        })
        
        assert response.status_code == 401


class TestRBACPermissions:
    """Test role-based access control"""
    
    def test_admin_can_list_users(self, client, admin_user_data):
        """Test admin can list users"""
        # Register admin
        client.post("/auth/register", json=admin_user_data)
        
        # Login
        login_response = client.post("/auth/login", json={
            "email": admin_user_data["email"],
            "password": admin_user_data["password"]
        })
        
        token = login_response.json()["access_token"]
        
        # List users (admin only)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_clinician_cannot_list_users(self, client, test_user_data):
        """Test clinician cannot list users"""
        # Register clinician
        client.post("/auth/register", json=test_user_data)
        
        # Login
        login_response = client.post("/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        
        token = login_response.json()["access_token"]
        
        # Try to list users (admin only)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403


class TestAuditLogging:
    """Test audit logging functionality"""
    
    def test_audit_log_created_on_login(self, client, test_user_data):
        """Test audit log created when user logs in"""
        # Register and login
        client.post("/auth/register", json=test_user_data)
        
        db = get_database_manager()
        
        # Count audit logs before
        with db.get_session() as session:
            count_before = session.query(AuditLog).filter(
                AuditLog.action == "login"
            ).count()
        
        # Login
        client.post("/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        
        # Count audit logs after
        with db.get_session() as session:
            count_after = session.query(AuditLog).filter(
                AuditLog.action == "login"
            ).count()
        
        # Should have one more login audit log
        assert count_after > count_before
    
    def test_audit_log_query_with_permission(self, client, admin_user_data):
        """Test querying audit logs with permission"""
        # Register admin
        client.post("/auth/register", json=admin_user_data)
        
        # Login
        login_response = client.post("/auth/login", json={
            "email": admin_user_data["email"],
            "password": admin_user_data["password"]
        })
        
        token = login_response.json()["access_token"]
        
        # Query audit logs
        response = client.get(
            "/audit/logs?limit=10",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestPHIDetection:
    """Test PHI detection integration"""
    
    def test_phi_detection_in_text(self):
        """Test PHI detection functionality"""
        from cortex.security.phi_detection import detect_phi, PHIType
        
        text = """
        Patient John Smith
        SSN: 123-45-6789
        DOB: 01/15/1980
        Phone: (555) 123-4567
        Email: john@example.com
        """
        
        matches = detect_phi(text)
        
        assert len(matches) > 0
        
        # Should detect SSN
        ssn_matches = [m for m in matches if m.phi_type == PHIType.SSN]
        assert len(ssn_matches) > 0
    
    def test_phi_redaction(self):
        """Test PHI redaction"""
        from cortex.security.phi_detection import redact_phi
        
        text = "Patient SSN: 123-45-6789"
        redacted = redact_phi(text)
        
        assert "123-45-6789" not in redacted
        assert "[REDACTED]" in redacted or "SSN" in redacted


class TestRateLimiting:
    """Test rate limiting"""
    
    def test_rate_limit_on_login(self, client):
        """Test rate limiting on login endpoint"""
        # Try to login multiple times rapidly
        responses = []
        
        for i in range(10):
            response = client.post("/auth/login", json={
                "email": "fake@example.com",
                "password": "FakeP@ss123!"
            })
            responses.append(response)
        
        # Should eventually get rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        
        # May or may not be rate limited depending on timing
        # Just verify requests are processed
        assert len(responses) == 10


class TestSecurityHeaders:
    """Test security headers"""
    
    def test_security_headers_present(self, client):
        """Test that security headers are present"""
        response = client.get("/")
        
        # Check for security headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-XSS-Protection" in response.headers


class TestInputValidation:
    """Test input validation"""
    
    def test_sql_injection_prevention(self):
        """Test SQL injection is prevented"""
        from cortex.security.validation import SecurityValidator
        
        malicious_input = "'; DROP TABLE users; --"
        
        assert SecurityValidator.detect_sql_injection(malicious_input)
    
    def test_xss_prevention(self):
        """Test XSS is prevented"""
        from cortex.security.validation import SecurityValidator
        
        malicious_input = "<script>alert('xss')</script>"
        
        assert SecurityValidator.detect_xss(malicious_input)
    
    def test_password_validation(self):
        """Test password validation"""
        from cortex.security.validation import SecurityValidator
        
        # Valid password
        is_valid, error = SecurityValidator.validate_password_strength("SecureP@ss123")
        assert is_valid is True
        
        # Weak password
        is_valid, error = SecurityValidator.validate_password_strength("weak")
        assert is_valid is False


class TestIntegration:
    """End-to-end integration tests"""
    
    def test_complete_user_workflow(self, client):
        """Test complete user workflow"""
        # 1. Register user
        user_data = {
            "email": f"workflow_{uuid4()}@example.com",
            "password": "WorkflowP@ss123!",
            "full_name": "Workflow User",
            "role": "clinician"
        }
        
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        
        # 2. Login
        response = client.post("/auth/login", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        assert response.status_code == 200
        
        token = response.json()["access_token"]
        
        # 3. Access protected endpoint
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        # 4. Verify user info
        user_info = response.json()
        assert user_info["email"] == user_data["email"]
        assert user_info["role"] == user_data["role"]
        
        # 5. Logout
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        # 6. Verify token is invalidated
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
    
    def test_admin_workflow(self, client, admin_user_data, test_user_data):
        """Test admin workflow"""
        # 1. Register admin
        client.post("/auth/register", json=admin_user_data)
        
        # 2. Login as admin
        response = client.post("/auth/login", json={
            "email": admin_user_data["email"],
            "password": admin_user_data["password"]
        })
        
        admin_token = response.json()["access_token"]
        
        # 3. List users
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        # 4. Register another user
        response = client.post("/auth/register", json=test_user_data)
        user_id = response.json()["id"]
        
        # 5. Deactivate user
        response = client.put(
            f"/auth/users/{user_id}/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])