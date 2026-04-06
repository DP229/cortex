"""
Tests for Security Hardening

Tests:
- Rate limiting
- Input validation
- SQL injection detection
- XSS detection
- Path traversal detection
- Password validation
"""

import pytest
from datetime import datetime, timedelta
import time

from cortex.security.rate_limiter import (
    RateLimiter, RateLimitConfig, RequestRecord,
    get_rate_limiter, rate_limit
)
from cortex.security.validation import (
    SecurityValidator, SecurityHeaders, SQLSafety,
    InputValidationError, validate_and_sanitize,
    check_sql_injection, check_xss
)


class TestRateLimiter:
    """Test RateLimiter class"""
    
    @pytest.fixture
    def limiter(self):
        """Create fresh rate limiter"""
        return RateLimiter()
    
    def test_check_rate_limit_allowed(self, limiter):
        """Test rate limit check when allowed"""
        allowed, retry_after, error = limiter.check_rate_limit(
            endpoint_type="login",
            identifier="192.168.1.1"
        )
        
        assert allowed is True
        assert retry_after is None
        assert error is None
    
    def test_check_rate_limit_exceeded(self, limiter):
        """Test rate limit check when exceeded"""
        config = RateLimitConfig(max_requests=3, window_seconds=60, block_duration_seconds=120)
        
        # Make 3 requests (should be allowed)
        for i in range(3):
            limiter.record_request("login", "192.168.1.1")
        
        # 4th request should be blocked
        allowed, retry_after, error = limiter.check_rate_limit(
            endpoint_type="login",
            identifier="192.168.1.1",
            custom_config=config
        )
        
        assert allowed is False
        assert retry_after == 120
        assert "Rate limit exceeded" in error
    
    def test_rate_limit_with_user(self, limiter):
        """Test rate limit with user-based limiting"""
        # Record requests for user
        for i in range(5):
            limiter.record_request("login", "192.168.1.1", user_id="user123")
        
        # Check user rate limit
        allowed, retry_after, error = limiter.check_rate_limit(
            endpoint_type="login",
            identifier="192.168.1.2",  # Different IP
            user_id="user123"
        )
        
        assert allowed is False
    
    def test_get_remaining_requests(self, limiter):
        """Test getting remaining requests"""
        # Initially should have full limit
        remaining = limiter.get_remaining_requests("login", "192.168.1.1")
        config = limiter.DEFAULT_LIMITS["login"]
        
        assert remaining == config.max_requests
        
        # After some requests
        limiter.record_request("login", "192.168.1.1")
        limiter.record_request("login", "192.168.1.1")
        
        remaining = limiter.get_remaining_requests("login", "192.168.1.1")
        assert remaining == config.max_requests - 2
    
    def test_reset_limits(self, limiter):
        """Test resetting rate limits"""
        # Record some requests
        limiter.record_request("login", "192.168.1.1")
        limiter.record_request("login", "192.168.1.1", user_id="user123")
        
        # Reset limits
        limiter.reset_limits("192.168.1.1", user_id="user123")
        
        # Should have full limit again
        remaining = limiter.get_remaining_requests("login", "192.168.1.1")
        config = limiter.DEFAULT_LIMITS["login"]
        
        assert remaining == config.max_requests
    
    def test_get_block_status(self, limiter):
        """Test getting block status"""
        # No blocks initially
        status = limiter.get_block_status("192.168.1.1")
        assert status["is_blocked"] is False
        
        # Exceed limits to get blocked
        config = RateLimitConfig(max_requests=2, window_seconds=60, block_duration_seconds=120)
        
        for i in range(3):
            limiter.record_request("login", "192.168.1.1")
            limiter.check_rate_limit("login", "192.168.1.1", custom_config=config)
        
        # Check block status
        status = limiter.get_block_status("192.168.1.1")
        assert status["is_blocked"] is True
        assert "login" in status["blocked_endpoints"]
    
    def test_cleanup_old_requests(self, limiter):
        """Test cleanup of old requests"""
        # Record requests
        record = RequestRecord()
        record.timestamps = [time.time() - 100, time.time() - 50, time.time()]
        
        # Cleanup requests older than 60 seconds
        limiter._cleanup_old_requests(record, 60)
        
        # Should only keep recent requests
        assert len(record.timestamps) == 2


class TestSecurityValidator:
    """Test SecurityValidator class"""
    
    def test_validate_email(self):
        """Test email validation"""
        assert SecurityValidator.validate_email("user@example.com") is True
        assert SecurityValidator.validate_email("user+tag@example.com") is True
        assert SecurityValidator.validate_email("invalid-email") is False
        assert SecurityValidator.validate_email("@example.com") is False
        assert SecurityValidator.validate_email("user@") is False
    
    def test_validate_uuid(self):
        """Test UUID validation"""
        assert SecurityValidator.validate_uuid("123e4567-e89b-12d3-a456-426614174000") is True
        assert SecurityValidator.validate_uuid("invalid-uuid") is False
        assert SecurityValidator.validate_uuid("") is False
    
    def test_sanitize_string(self):
        """Test string sanitization"""
        # Basic sanitization
        result = SecurityValidator.sanitize_string("Hello World")
        assert result == "Hello World"
        
        # HTML escaping
        result = SecurityValidator.sanitize_string("<script>alert('xss')</script>", allow_html=False)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        
        # Length limit
        with pytest.raises(InputValidationError):
            SecurityValidator.sanitize_string("a" * 2000, max_length=100)
        
        # Null byte removal
        result = SecurityValidator.sanitize_string("hello\x00world")
        assert "\x00" not in result
    
    def test_detect_sql_injection(self):
        """Test SQL injection detection"""
        # Valid input
        assert SecurityValidator.detect_sql_injection("Hello World") is False
        
        # SQL patterns
        assert SecurityValidator.detect_sql_injection("SELECT * FROM users") is True
        assert SecurityValidator.detect_sql_injection("1' OR '1'='1") is True
        assert SecurityValidator.detect_sql_injection("admin'; --") is True
        assert SecurityValidator.detect_sql_injection("UNION SELECT") is True
        assert SecurityValidator.detect_sql_injection("<script>") is False  # Not SQL
    
    def test_detect_xss(self):
        """Test XSS detection"""
        # Valid input
        assert SecurityValidator.detect_xss("Hello World") is False
        
        # XSS patterns
        assert SecurityValidator.detect_xss("<script>alert('xss')</script>") is True
        assert SecurityValidator.detect_xss("<img onerror='alert(1)'>") is True
        assert SecurityValidator.detect_xss("javascript:alert(1)") is True
        assert SecurityValidator.detect_xss("<iframe src='evil.com'>") is True
        assert SecurityValidator.detect_xss("SELECT * FROM users") is False  # SQL not XSS
    
    def test_detect_path_traversal(self):
        """Test path traversal detection"""
        # Valid input
        assert SecurityValidator.detect_path_traversal("filename.txt") is False
        
        # Path traversal patterns
        assert SecurityValidator.detect_path_traversal("../../../etc/passwd") is True
        assert SecurityValidator.detect_path_traversal("..\\windows\\system32") is True
        assert SecurityValidator.detect_path_traversal("%2e%2e/etc/passwd") is True
    
    def test_validate_password_strength(self):
        """Test password validation"""
        # Valid password
        is_valid, error = SecurityValidator.validate_password_strength("SecureP@ss123")
        assert is_valid is True
        assert error is None
        
        # Too short
        is_valid, error = SecurityValidator.validate_password_strength("Short1!")
        assert is_valid is False
        assert "at least 12 characters" in error
        
        # No uppercase
        is_valid, error = SecurityValidator.validate_password_strength("securepass123!")
        assert is_valid is False
        assert "uppercase" in error
        
        # No lowercase
        is_valid, error = SecurityValidator.validate_password_strength("SECUREPASS123!")
        assert is_valid is False
        assert "lowercase" in error
        
        # No number
        is_valid, error = SecurityValidator.validate_password_strength("SecurePassword!")
        assert is_valid is False
        assert "number" in error
        
        # No special char
        is_valid, error = SecurityValidator.validate_password_strength("SecurePassword123")
        assert is_valid is False
        assert "special character" in error
        
        # Common password
        is_valid, error = SecurityValidator.validate_password_strength("password123!A")
        assert is_valid is False
        assert "common pattern" in error
    
    def test_sanitize_dict(self):
        """Test dictionary sanitization"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "active": True,
            "tags": ["tag1", "tag2"]
        }
        
        result = SecurityValidator.sanitize_dict(data)
        
        assert result["name"] == "John Doe"
        assert result["age"] == 30
        assert result["active"] is True
        assert result["tags"] == ["tag1", "tag2"]
    
    def test_sanitize_dict_with_html(self):
        """Test dictionary sanitization with HTML"""
        data = {
            "name": "<script>alert('xss')</script>",
            "description": "This is <b>bold</b>"
        }
        
        result = SecurityValidator.sanitize_dict(data)
        
        assert "<script>" not in result["name"]
        assert "&lt;script&gt;" in result["name"]
    
    def test_sanitize_dict_max_depth(self):
        """Test dictionary sanitization with max depth"""
        # Deep nesting
        data = {"level1": {"level2": {"level3": {"level4": {"level5": "value"}}}}}
        
        with pytest.raises(InputValidationError):
            SecurityValidator.sanitize_dict(data, max_depth=3)
    
    def test_sanitize_dict_max_keys(self):
        """Test dictionary sanitization with max keys"""
        # Too many keys
        data = {f"key{i}": i for i in range(150)}
        
        with pytest.raises(InputValidationError):
            SecurityValidator.sanitize_dict(data, max_keys=100)
    
    def test_validate_file_upload(self):
        """Test file upload validation"""
        # Valid file
        is_valid, error = SecurityValidator.validate_file_upload(
            "document.pdf",
            [".pdf", ".doc", ".docx"]
        )
        assert is_valid is True
        assert error is None
        
        # Invalid extension
        is_valid, error = SecurityValidator.validate_file_upload(
            "malware.exe",
            [".pdf", ".doc"]
        )
        assert is_valid is False
        assert "not allowed" in error
        
        # Dangerous extension
        is_valid, error = SecurityValidator.validate_file_upload(
            "script.sh",
            [".sh", ".pdf"]
        )
        assert is_valid is False
        assert "not allowed" in error
        
        # Path traversal
        is_valid, error = SecurityValidator.validate_file_upload(
            "../../../etc/passwd.pdf",
            [".pdf"]
        )
        assert is_valid is False
        assert "path traversal" in error
    
    def test_validate_date_range(self):
        """Test date range validation"""
        now = datetime.utcnow()
        
        # Valid range
        is_valid, error = SecurityValidator.validate_date_range(
            now,
            now + timedelta(days=30)
        )
        assert is_valid is True
        
        # Invalid range (start > end)
        is_valid, error = SecurityValidator.validate_date_range(
            now + timedelta(days=30),
            now
        )
        assert is_valid is False
        assert "before" in error
        
        # Range too large
        is_valid, error = SecurityValidator.validate_date_range(
            now,
            now + timedelta(days=400),
            max_days=365
        )
        assert is_valid is False
        assert "exceeds" in error
    
    def test_validate_integer(self):
        """Test integer validation"""
        # Valid integer
        is_valid, value, error = SecurityValidator.validate_integer(42)
        assert is_valid is True
        assert value == 42
        
        # With min/max
        is_valid, value, error = SecurityValidator.validate_integer(50, min_val=10, max_val=100)
        assert is_valid is True
        assert value == 50
        
        # Below minimum
        is_valid, value, error = SecurityValidator.validate_integer(5, min_val=10)
        assert is_valid is False
        assert "at least" in error
        
        # Above maximum
        is_valid, value, error = SecurityValidator.validate_integer(150, max_val=100)
        assert is_valid is False
        assert "exceed" in error
        
        # Invalid integer
        is_valid, value, error = SecurityValidator.validate_integer("not a number")
        assert is_valid is False
        assert "integer" in error


class TestSecurityHeaders:
    """Test SecurityHeaders class"""
    
    def test_get_security_headers(self):
        """Test getting security headers"""
        headers = SecurityHeaders.get_security_headers()
        
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        
        assert "Content-Security-Policy" in headers
        assert "Strict-Transport-Security" in headers
    
    def test_get_csp_report_only(self):
        """Test getting CSP report-only"""
        csp = SecurityHeaders.get_csp_report_only()
        
        assert "report-uri" in csp
        assert "default-src 'self'" in csp


class TestSQLSafety:
    """Test SQLSafety class"""
    
    def test_is_safe_identifier(self):
        """Test SQL identifier safety"""
        # Valid identifiers
        assert SQLSafety.is_safe_identifier("users") is True
        assert SQLSafety.is_safe_identifier("user_name") is True
        assert SQLSafety.is_safe_identifier("table123") is True
        
        # Invalid identifiers
        assert SQLSafety.is_safe_identifier("SELECT") is False  # Reserved word
        assert SQLSafety.is_safe_identifier("user-name") is False  # Hyphen
        assert SQLSafety.is_safe_identifier("123table") is False  # Starts with number
        assert SQLSafety.is_safe_identifier("") is False  # Empty
        assert SQLSafety.is_safe_identifier("DROP TABLE") is False  # SQL
    
    def test_sanitize_order_by(self):
        """Test ORDER BY sanitization"""
        # Valid ORDER BY
        result = SQLSafety.sanitize_order_by("created_at DESC")
        assert result == "created_at DESC"
        
        result = SQLSafety.sanitize_order_by("name ASC")
        assert result == "name ASC"
        
        result = SQLSafety.sanitize_order_by("id")
        assert result == "id ASC"
        
        # Invalid ORDER BY
        result = SQLSafety.sanitize_order_by("id; DROP TABLE users")
        assert result is None
        
        result = SQLSafety.sanitize_order_by("SELECT * FROM users")
        assert result is None
        
        result = SQLSafety.sanitize_order_by("")
        assert result is None


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_validate_and_sanitize(self):
        """Test validate_and_sanitize function"""
        data = {
            "name": "John Doe",
            "email": "john@example.com"
        }
        
        result = validate_and_sanitize(data)
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
    
    def test_check_sql_injection_valid(self):
        """Test check_sql_injection with valid input"""
        # Should not raise
        check_sql_injection("Hello World")
    
    def test_check_sql_injection_invalid(self):
        """Test check_sql_injection with invalid input"""
        with pytest.raises(InputValidationError):
            check_sql_injection("SELECT * FROM users")
    
    def test_check_xss_valid(self):
        """Test check_xss with valid input"""
        # Should not raise
        check_xss("Hello World")
    
    def test_check_xss_invalid(self):
        """Test check_xss with invalid input"""
        with pytest.raises(InputValidationError):
            check_xss("<script>alert('xss')</script>")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])