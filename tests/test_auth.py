"""
Tests for Authentication System

Tests:
- User registration
- User login
- JWT token verification
- Account lockout
- Password validation
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID

from cortex.security.auth import AuthManager, AuthenticationError, AccountLockedError
from cortex.security.encryption import hash_password, verify_password
from cortex.database import get_database_manager
from cortex.models import User, UserRole


class TestPasswordHashing:
    """Test password hashing"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 50  # Argon2id hashes are long
    
    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert verify_password(hashed, password) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert verify_password(hashed, "WrongPassword123!") is False
    
    def test_verify_password_different_hashes(self):
        """Test that different passwords produce different hashes"""
        password1 = "TestPassword123!"
        password2 = "TestPassword456!"
        
        hash1 = hash_password(password1)
        hash2 = hash_password(password2)
        
        assert hash1 != hash2


class TestUserRegistration:
    """Test user registration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.auth = AuthManager(
            jwt_secret="test-secret-key-for-testing-32-bytes",
            jwt_expiration_minutes=15
        )
    
    def test_register_user_success(self):
        """Test successful user registration"""
        user = self.auth.register(
            email="test@example.com",
            password="TestPassword123!",
            full_name="Test User",
            role="clinician"
        )
        
        assert user is not None
        assert user.email == "test@example.com"
        assert user.role == UserRole.CLINICIAN
        assert user.is_active is True
        assert user.password_hash != "TestPassword123!"  # Should be hashed
    
    def test_register_user_invalid_email(self):
        """Test registration with invalid email"""
        with pytest.raises(Exception):  # Pydantic validation error
            self.auth.register(
                email="invalid-email",
                password="TestPassword123!",
                full_name="Test User",
                role="clinician"
            )
    
    def test_register_user_invalid_role(self):
        """Test registration with invalid role"""
        with pytest.raises(ValueError):
            self.auth.register(
                email="test@example.com",
                password="TestPassword123!",
                full_name="Test User",
                role="invalid_role"
            )
    
    def test_register_user_weak_password(self):
        """Test registration with weak password"""
        with pytest.raises(ValueError):
            self.auth.register(
                email="test@example.com",
                password="weak",  # Too short
                full_name="Test User",
                role="clinician"
            )
    
    def test_register_user_duplicate_email(self):
        """Test registration with duplicate email"""
        # First registration
        self.auth.register(
            email="duplicate@example.com",
            password="TestPassword123!",
            full_name="First User",
            role="clinician"
        )
        
        # Second registration with same email
        with pytest.raises(ValueError):
            self.auth.register(
                email="duplicate@example.com",
                password="TestPassword456!",
                full_name="Second User",
                role="clinician"
            )


class TestUserLogin:
    """Test user login"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.auth = AuthManager(
            jwt_secret="test-secret-key-for-testing-32-bytes",
            jwt_expiration_minutes=15
        )
        
        # Register test user
        self.test_user = self.auth.register(
            email="test@example.com",
            password="TestPassword123!",
            full_name="Test User",
            role="clinician"
        )
    
    def test_login_success(self):
        """Test successful login"""
        tokens = self.auth.login(
            email="test@example.com",
            password="TestPassword123!"
        )
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] > 0
    
    def test_login_invalid_email(self):
        """Test login with invalid email"""
        with pytest.raises(AuthenticationError):
            self.auth.login(
                email="wrong@example.com",
                password="TestPassword123!"
            )
    
    def test_login_invalid_password(self):
        """Test login with invalid password"""
        with pytest.raises(AuthenticationError):
            self.auth.login(
                email="test@example.com",
                password="WrongPassword123!"
            )


class TestJWT:
    """Test JWT token operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.auth = AuthManager(
            jwt_secret="test-secret-key-for-testing-32-bytes",
            jwt_expiration_minutes=15
        )
        
        # Register and login test user
        self.auth.register(
            email="test@example.com",
            password="TestPassword123!",
            full_name="Test User",
            role="clinician"
        )
        
        self.tokens = self.auth.login(
            email="test@example.com",
            password="TestPassword123!"
        )
    
    def test_verify_jwt_success(self):
        """Test JWT verification"""
        payload = self.auth.verify_jwt(self.tokens["access_token"])
        
        assert payload is not None
        assert "sub" in payload
        assert "email" in payload
        assert "role" in payload
        assert "exp" in payload
    
    def test_verify_jwt_invalid_token(self):
        """Test JWT verification with invalid token"""
        with pytest.raises(AuthenticationError):
            self.auth.verify_jwt("invalid_token")
    
    def test_get_current_user(self):
        """Test getting current user from JWT"""
        user = self.auth.get_current_user(self.tokens["access_token"])
        
        assert user is not None
        assert user.email == "test@example.com"
        assert user.role == UserRole.CLINICIAN
    
    def test_refresh_token(self):
        """Test token refresh"""
        new_tokens = self.auth.refresh_access_token(self.tokens["refresh_token"])
        
        assert "access_token" in new_tokens
        assert new_tokens["access_token"] != self.tokens["access_token"]


class TestAccountLockout:
    """Test account lockout"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.auth = AuthManager(
            jwt_secret="test-secret-key-for-testing-32-bytes",
            jwt_expiration_minutes=15,
            max_login_attempts=3,
            lockout_minutes=15
        )
        
        # Register test user
        self.auth.register(
            email="test@example.com",
            password="TestPassword123!",
            full_name="Test User",
            role="clinician"
        )
    
    def test_account_lockout_after_failed_attempts(self):
        """Test account locks after max failed attempts"""
        # Try to login with wrong password 3 times
        for _ in range(3):
            try:
                self.auth.login(
                    email="test@example.com",
                    password="WrongPassword!"
                )
            except AuthenticationError:
                pass
        
        # Next attempt should lock account
        with pytest.raises(AccountLockedError):
            self.auth.login(
                email="test@example.com",
                password="TestPassword123!"  # Even correct password
            )
    
    def test_account_unlock_after_time(self):
        """Test account doesn't unlock immediately"""
        # Lock account
        for _ in range(5):
            try:
                self.auth.login(
                    email="test@example.com",
                    password="WrongPassword!"
                )
            except (AuthenticationError, AccountLockedError):
                pass
        
        # Account should still be locked
        with pytest.raises((AuthenticationError, AccountLockedError)):
            self.auth.login(
                email="test@example.com",
                password="TestPassword123!"
            )


class TestPasswordValidation:
    """Test password validation"""
    
    def test_password_too_short(self):
        """Test password too short"""
        password = "Short1!"
        assert len(password) < 12
        
        auth = AuthManager()
        with pytest.raises(ValueError):
            auth._validate_password(password)
    
    def test_password_no_uppercase(self):
        """Test password without uppercase"""
        password = "lowercase123!"
        with pytest.raises(ValueError):
            AuthManager()._validate_password(password)
    
    def test_password_no_lowercase(self):
        """Test password without lowercase"""
        password = "UPPERCASE123!"
        with pytest.raises(ValueError):
            AuthManager()._validate_password(password)
    
    def test_password_no_number(self):
        """Test password without number"""
        password = "NoNumbersHere!"
        with pytest.raises(ValueError):
            AuthManager()._validate_password(password)
    
    def test_password_no_special(self):
        """Test password without special character"""
        password = "NoSpecialChars123"
        with pytest.raises(ValueError):
            AuthManager()._validate_password(password)
    
    def test_password_valid(self):
        """Test valid password"""
        password = "ValidPassword123!"
        # Should not raise
        AuthManager()._validate_password(password)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])