"""
Cortex Security Utilities - Input Validation & Sanitization

EN 50128 / IEC 62443 compliant security utilities:
- Input validation and sanitization
- SQL injection prevention
- XSS prevention
- Path traversal prevention
- Security headers for railway safety systems
"""

import re
import html
from typing import Optional, List, Any, Dict
from datetime import datetime
from uuid import UUID
import structlog

logger = structlog.get_logger()


class InputValidationError(Exception):
    """Input validation error"""
    pass


class SecurityValidator:
    """Security input validation and sanitization"""
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    # SQL injection patterns (case-insensitive)
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b)", re.IGNORECASE),
        re.compile(r"(\b(UNION|INTERSECT|EXCEPT)\b)", re.IGNORECASE),
        re.compile(r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"(;\s*--)", re.IGNORECASE),
        re.compile(r"(\/\*.*\*\/)", re.IGNORECASE),
        re.compile(r"(\b(EXEC|EXECUTE)\b)", re.IGNORECASE),
        re.compile(r"(xp_cmdshell)", re.IGNORECASE),
        re.compile(r"(CONCAT\s*\()", re.IGNORECASE),
        re.compile(r"(CHAR\s*\()", re.IGNORECASE),
        re.compile(r"('\s*(OR|AND)\s*')", re.IGNORECASE),
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        re.compile(r"<script", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"onerror\s*=", re.IGNORECASE),
        re.compile(r"onload\s*=", re.IGNORECASE),
        re.compile(r"onclick\s*=", re.IGNORECASE),
        re.compile(r"<iframe", re.IGNORECASE),
        re.compile(r"<object", re.IGNORECASE),
        re.compile(r"<embed", re.IGNORECASE),
        re.compile(r"<form", re.IGNORECASE),
        re.compile(r"<input", re.IGNORECASE),
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        re.compile(r"\.\./"),
        re.compile(r"\.\.\\"),
        re.compile(r"%2e%2e", re.IGNORECASE),
        re.compile(r"%252e", re.IGNORECASE),
        re.compile(r"\.\."),
    ]
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not email or len(email) > 255:
            return False
        return bool(SecurityValidator.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_uuid(uuid_str: str) -> bool:
        """Validate UUID format"""
        if not uuid_str:
            return False
        try:
            UUID(uuid_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def sanitize_string(
        value: str,
        max_length: int = 1000,
        allow_html: bool = False,
        allow_special_chars: bool = True
    ) -> str:
        """
        Sanitize string input
        
        Args:
            value: Input string
            max_length: Maximum allowed length
            allow_html: Allow HTML tags (will be escaped)
            allow_special_chars: Allow special characters
            
        Returns:
            Sanitized string
            
        Raises:
            InputValidationError: If input is invalid
        """
        if not value:
            return ""
        
        # Check length
        if len(value) > max_length:
            raise InputValidationError(f"Input exceeds maximum length of {max_length} characters")
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Escape HTML if not allowed
        if not allow_html:
            value = html.escape(value)
        
        # Remove control characters except newlines and tabs
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t\r')
        
        return value.strip()
    
    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """
        Detect potential SQL injection
        
        Args:
            value: Input string
            
        Returns:
            True if SQL injection detected
        """
        if not value:
            return False
        
        for pattern in SecurityValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning(
                    "sql_injection_detected",
                    pattern=pattern.pattern,
                    value_preview=value[:50]
                )
                return True
        
        return False
    
    @staticmethod
    def detect_xss(value: str) -> bool:
        """
        Detect potential XSS attack
        
        Args:
            value: Input string
            
        Returns:
            True if XSS detected
        """
        if not value:
            return False
        
        for pattern in SecurityValidator.XSS_PATTERNS:
            if pattern.search(value):
                logger.warning(
                    "xss_detected",
                    pattern=pattern.pattern,
                    value_preview=value[:50]
                )
                return True
        
        return False
    
    @staticmethod
    def detect_path_traversal(value: str) -> bool:
        """
        Detect path traversal attempt
        
        Args:
            value: Input string
            
        Returns:
            True if path traversal detected
        """
        if not value:
            return False
        
        for pattern in SecurityValidator.PATH_TRAVERSAL_PATTERNS:
            if pattern.search(value):
                logger.warning(
                    "path_traversal_detected",
                    pattern=pattern.pattern,
                    value_preview=value[:50]
                )
                return True
        
        return False
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength (EN 50128 / IEC 62443 requirements)
        
        Requirements:
        - Minimum 12 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number
        - At least 1 special character
        
        Args:
            password: Password to validate
            
        Returns:
            (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"
        
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        
        if len(password) > 128:
            return False, "Password must not exceed 128 characters"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            return False, "Password must contain at least one special character"
        
        # Check for common patterns
        common_passwords = [
            'password', 'password123', 'qwerty', 'abc123', '123456',
            'admin', 'letmein', 'welcome', 'monkey', 'dragon'
        ]
        
        password_lower = password.lower()
        for common in common_passwords:
            if common in password_lower:
                return False, f"Password contains common pattern '{common}'"
        
        return True, None
    
    @staticmethod
    def sanitize_dict(
        data: Dict[str, Any],
        max_depth: int = 10,
        max_keys: int = 100,
        max_string_length: int = 10000
    ) -> Dict[str, Any]:
        """
        Sanitize dictionary input
        
        Args:
            data: Input dictionary
            max_depth: Maximum nesting depth
            max_keys: Maximum number of keys
            max_string_length: Maximum string length
            
        Returns:
            Sanitized dictionary
            
        Raises:
            InputValidationError: If input is invalid
        """
        if not isinstance(data, dict):
            raise InputValidationError("Input must be a dictionary")
        
        if len(data) > max_keys:
            raise InputValidationError(f"Dictionary exceeds maximum of {max_keys} keys")
        
        def sanitize_value(value: Any, depth: int) -> Any:
            """Recursively sanitize values"""
            if depth > max_depth:
                raise InputValidationError(f"Nesting depth exceeds maximum of {max_depth}")
            
            if isinstance(value, str):
                return SecurityValidator.sanitize_string(value, max_string_length)
            
            elif isinstance(value, dict):
                if len(value) > max_keys:
                    raise InputValidationError(f"Dictionary exceeds maximum of {max_keys} keys")
                return {k: sanitize_value(v, depth + 1) for k, v in value.items()}
            
            elif isinstance(value, list):
                return [sanitize_value(item, depth + 1) for item in value]
            
            elif isinstance(value, (int, float, bool)):
                return value
            
            elif value is None:
                return None
            
            else:
                # Convert to string and sanitize
                return SecurityValidator.sanitize_string(str(value), max_string_length)
        
        return {k: sanitize_value(v, 0) for k, v in data.items()}
    
    @staticmethod
    def validate_file_upload(
        filename: str,
        allowed_extensions: List[str],
        max_filename_length: int = 255
    ) -> tuple[bool, Optional[str]]:
        """
        Validate file upload
        
        Args:
            filename: Filename
            allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.jpg'])
            max_filename_length: Maximum filename length
            
        Returns:
            (is_valid, error_message)
        """
        if not filename:
            return False, "Filename is required"
        
        if len(filename) > max_filename_length:
            return False, f"Filename exceeds maximum length of {max_filename_length}"
        
        # Check for path traversal
        if SecurityValidator.detect_path_traversal(filename):
            return False, "Invalid filename (path traversal detected)"
        
        # Check extension
        ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        if ext.lower() not in [e.lower() for e in allowed_extensions]:
            return False, f"File extension not allowed. Allowed: {', '.join(allowed_extensions)}"
        
        # Check for dangerous extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
            '.vbs', '.js', '.jar', '.php', '.asp', '.aspx',
            '.sh', '.bash', '.ps1', '.psm1'
        ]
        
        if ext.lower() in dangerous_extensions:
            return False, f"File extension '{ext}' is not allowed for security reasons"
        
        return True, None
    
    @staticmethod
    def validate_date_range(
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        max_days: int = 365
    ) -> tuple[bool, Optional[str]]:
        """
        Validate date range
        
        Args:
            start_date: Start date
            end_date: End date
            max_days: Maximum days in range
            
        Returns:
            (is_valid, error_message)
        """
        if not start_date and not end_date:
            return True, None
        
        if start_date and end_date:
            if start_date > end_date:
                return False, "Start date must be before end date"
            
            delta = (end_date - start_date).days
            if delta > max_days:
                return False, f"Date range exceeds maximum of {max_days} days"
        
        return True, None
    
    @staticmethod
    def validate_integer(
        value: Any,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Validate integer value
        
        Args:
            value: Value to validate
            min_val: Minimum value
            max_val: Maximum value
            
        Returns:
            (is_valid, parsed_value, error_message)
        """
        try:
            int_val = int(value)
        except (ValueError, TypeError):
            return False, None, "Value must be an integer"
        
        if min_val is not None and int_val < min_val:
            return False, None, f"Value must be at least {min_val}"
        
        if max_val is not None and int_val > max_val:
            return False, None, f"Value must not exceed {max_val}"
        
        return True, int_val, None


class SecurityHeaders:
    """Security headers configuration"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Prevent MIME sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'",
            
            # HSTS (if using HTTPS)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Permissions Policy
            "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
        }
    
    @staticmethod
    def get_csp_report_only() -> str:
        """Get CSP for report-only mode (testing)"""
        return "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; report-uri /csp-report"


class SQLSafety:
    """SQL injection prevention utilities"""
    
    @staticmethod
    def is_safe_identifier(identifier: str) -> bool:
        """
        Check if identifier is safe for SQL (table/column names)
        
        Args:
            identifier: SQL identifier
            
        Returns:
            True if safe
        """
        if not identifier:
            return False
        
        # Only alphanumeric and underscore
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            return False
        
        # Check against reserved words
        reserved_words = {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'TABLE', 'INDEX', 'DATABASE', 'USER', 'PASSWORD',
            'FROM', 'WHERE', 'JOIN', 'UNION', 'AND', 'OR', 'NOT', 'NULL',
            'TRUE', 'FALSE', 'DEFAULT', 'PRIMARY', 'KEY', 'FOREIGN',
            'REFERENCES', 'CONSTRAINT', 'UNIQUE', 'CHECK', 'CASCADE'
        }
        
        if identifier.upper() in reserved_words:
            return False
        
        return True
    
    @staticmethod
    def sanitize_order_by(order_by: str) -> Optional[str]:
        """
        Sanitize ORDER BY clause
        
        Args:
            order_by: Column name for ordering
            
        Returns:
            Sanitized column name or None
        """
        if not order_by:
            return None
        
        # Remove whitespace
        order_by = order_by.strip()
        
        # Split on space for direction
        parts = order_by.split()
        
        if len(parts) > 2:
            return None
        
        column = parts[0]
        direction = parts[1].upper() if len(parts) == 2 else 'ASC'
        
        # Validate column name
        if not SQLSafety.is_safe_identifier(column):
            return None
        
        # Validate direction
        if direction not in ('ASC', 'DESC'):
            return None
        
        return f"{column} {direction}"


# Convenience functions for FastAPI

def validate_and_sanitize(
    data: Dict[str, Any],
    max_depth: int = 10,
    max_keys: int = 100
) -> Dict[str, Any]:
    """
    Validate and sanitize dictionary input
    
    Args:
        data: Input data
        max_depth: Maximum nesting depth
        max_keys: Maximum number of keys
        
    Returns:
        Sanitized data
        
    Raises:
        InputValidationError: If input is invalid
    """
    return SecurityValidator.sanitize_dict(data, max_depth, max_keys)


def check_sql_injection(value: str) -> None:
    """
    Check for SQL injection and raise error if detected
    
    Args:
        value: Value to check
        
    Raises:
        InputValidationError: If SQL injection detected
    """
    if SecurityValidator.detect_sql_injection(value):
        raise InputValidationError("Potential SQL injection detected")


def check_xss(value: str) -> None:
    """
    Check for XSS and raise error if detected
    
    Args:
        value: Value to check
        
    Raises:
        InputValidationError: If XSS detected
    """
    if SecurityValidator.detect_xss(value):
        raise InputValidationError("Potential XSS attack detected")