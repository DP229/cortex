"""
Cortex Data Minimization - PII and IP Masking Filters

Phase 3 Enhancement: Heuristic filters to automatically mask Personally
Identifiable Information (PII) and confidential intellectual property
before data is written to logs.

IEC 62443 & GDPR Requirements:
- Data minimization (collect only what's necessary)
- PII protection in logs
- Confidential IP protection
- Right to erasure support

Features:
- Pattern-based PII detection
- Configurable masking rules
- Safe logging wrappers
- IP and file path anonymization
- Audit trail of masked items
"""

import re
import hashlib
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    """Categories of sensitive data"""
    PII_NAME = "pii_name"
    PII_CONTACT = "pii_contact"
    PII_FINANCIAL = "pii_financial"
    PII_HEALTH = "pii_health"
    PII_GOVERNMENT = "pii_government"
    PII_NETWORK = "pii_network"
    CREDENTIAL = "credential"
    IP_CLASSIFIED = "ip_classified"
    PROPRIETARY = "proprietary"


@dataclass
class MaskedValue:
    """A value that has been masked"""
    original_value: str
    masked_value: str
    category: DataCategory
    pattern_match: str
    confidence: float  # 0.0 to 1.0
    hash_for_audit: str  # Hash of original for audit trail


@dataclass
class DataMinimizationConfig:
    """Configuration for data minimization"""
    # PII settings
    mask_pii_names: bool = True
    mask_pii_emails: bool = True
    mask_pii_phones: bool = True
    mask_pii_ssn: bool = True
    mask_pii_credit_cards: bool = True
    mask_pii_dates_of_birth: bool = True
    
    # Network/IT settings
    mask_ip_addresses: bool = True
    mask_mac_addresses: bool = True
    mask_hostnames: bool = True
    mask_urls: bool = False  # URLs often needed for debugging
    
    # Credential settings
    mask_passwords: bool = True
    mask_api_keys: bool = True
    mask_tokens: bool = True
    mask_secrets: bool = True
    
    # IP/Proprietary settings
    mask_internal_ips: bool = True
    mask_file_paths: bool = False  # File paths often needed
    mask_internal_domains: bool = True
    
    # Confidence threshold
    confidence_threshold: float = 0.7
    
    # Custom patterns
    custom_patterns: Dict[str, str] = field(default_factory=dict)


class DataMinimizer:
    """
    Data minimization and masking engine.
    
    Uses pattern matching and heuristics to detect and mask
    sensitive data before it reaches logs or audit trails.
    """
    
    # Pre-compiled regex patterns for PII detection
    PATTERNS = {
        # Government IDs
        DataCategory.PII_GOVERNMENT: {
            'ssn': re.compile(r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b'),
            'itin': re.compile(r'\b[0-9]{2}-[0-9]{2}-[0-9]{4}\b'),
            'ein': re.compile(r'\b[0-9]{2}-[0-9]{7}\b'),
        },
        # Financial
        DataCategory.PII_FINANCIAL: {
            'credit_card': re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
            'cvv': re.compile(r'\b[0-9]{3,4}\b'),
            'bank_account': re.compile(r'\b[0-9]{8,17}\b'),  # IBAN-ish
        },
        # Contact
        DataCategory.PII_CONTACT: {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone_us': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            'phone_intl': re.compile(r'\b\+[1-9]\d{1,14}\b'),
        },
        # Network identifiers
        DataCategory.PII_NETWORK: {
            'ipv4': re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
            'ipv6': re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'),
            'mac_address': re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'),
            'hostname': re.compile(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'),
        },
        # Credentials
        DataCategory.CREDENTIAL: {
            'password': re.compile(r'(?:password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
            'api_key': re.compile(r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', re.IGNORECASE),
            'bearer_token': re.compile(r'(?:bearer\s+)?token\s*[:=]\s*["\']?([a-zA-Z0-9_.-]{20,})', re.IGNORECASE),
            'aws_key': re.compile(r'(?:AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'),
            'secret_key': re.compile(r'(?:secret[_-]?key|client[_-]?secret)\s*[:=]\s*["\']?([^"\'\s]{16,})', re.IGNORECASE),
        },
    }
    
    def __init__(self, config: Optional[DataMinimizationConfig] = None):
        self.config = config or DataMinimizationConfig()
        self._masking_rules: List[Tuple[re.Pattern, str, DataCategory, float]] = []
        self._setup_default_rules()
        self._setup_custom_rules()
        
        # Audit trail of masked items (just counts, not actual values)
        self._masking_stats: Dict[DataCategory, int] = {}
    
    def _setup_default_rules(self) -> None:
        """Set up default masking rules based on config"""
        # SSN
        if self.config.mask_pii_ssn:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_GOVERNMENT]['ssn'],
                'XXX-XX-XXXX',
                DataCategory.PII_GOVERNMENT,
                0.95
            ))
        
        # Email
        if self.config.mask_pii_emails:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_CONTACT]['email'],
                '[EMAIL_MASKED]',
                DataCategory.PII_CONTACT,
                0.9
            ))
        
        # Phone
        if self.config.mask_pii_phones:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_CONTACT]['phone_us'],
                '[PHONE_MASKED]',
                DataCategory.PII_CONTACT,
                0.85
            ))
        
        # Credit Card
        if self.config.mask_pii_credit_cards:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_FINANCIAL]['credit_card'],
                '[CC_MASKED]',
                DataCategory.PII_FINANCIAL,
                0.98
            ))
        
        # IP Addresses
        if self.config.mask_ip_addresses:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_NETWORK]['ipv4'],
                '[IP_MASKED]',
                DataCategory.PII_NETWORK,
                0.9
            ))
        
        # MAC Addresses
        if self.config.mask_mac_addresses:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.PII_NETWORK]['mac_address'],
                '[MAC_MASKED]',
                DataCategory.PII_NETWORK,
                0.95
            ))
        
        # Passwords
        if self.config.mask_passwords:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.CREDENTIAL]['password'],
                'password=[REDACTED]',
                DataCategory.CREDENTIAL,
                0.95
            ))
        
        # API Keys
        if self.config.mask_api_keys:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.CREDENTIAL]['api_key'],
                'api_key=[REDACTED]',
                DataCategory.CREDENTIAL,
                0.9
            ))
        
        # Bearer Tokens
        if self.config.mask_tokens:
            self._masking_rules.append((
                self.PATTERNS[DataCategory.CREDENTIAL]['bearer_token'],
                'token=[REDACTED]',
                DataCategory.CREDENTIAL,
                0.9
            ))
        
        # AWS Keys
        self._masking_rules.append((
            self.PATTERNS[DataCategory.CREDENTIAL]['aws_key'],
            '[AWS_KEY_MASKED]',
            DataCategory.CREDENTIAL,
            0.98
        ))
    
    def _setup_custom_rules(self) -> None:
        """Set up custom masking rules from config"""
        for name, pattern in self.config.custom_patterns.items():
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._masking_rules.append((
                    compiled,
                    f'[{name.upper()}_MASKED]',
                    DataCategory.IP_CLASSIFIED,
                    0.8
                ))
            except re.error as e:
                logger.warning(f"Invalid custom pattern '{name}': {e}")
    
    def mask(self, text: str, context: Optional[str] = None) -> Tuple[str, List[MaskedValue]]:
        """
        Mask sensitive data in text.
        
        Args:
            text: Text to process
            context: Optional context hint (e.g., "log", "audit", "debug")
        
        Returns:
            Tuple of (masked_text, list_of_masked_items)
        """
        masked_items = []
        result = text
        
        for pattern, replacement, category, confidence in self._masking_rules:
            if confidence < self.config.confidence_threshold:
                continue
            
            for match in pattern.finditer(result):
                original = match.group(0)
                
                # Skip if already masked
                if '[MASKED]' in original or '[REDACTED]' in original:
                    continue
                
                # Create masked value record
                masked_value = MaskedValue(
                    original_value=original,
                    masked_value=replacement,
                    category=category,
                    pattern_match=pattern.pattern[:50],
                    confidence=confidence,
                    hash_for_audit=self._hash_for_audit(original)
                )
                masked_items.append(masked_value)
                
                # Update stats
                self._masking_stats[category] = self._masking_stats.get(category, 0) + 1
                
                # Replace in text
                result = result.replace(original, replacement, 1)
        
        # Additional contextual masking
        if context:
            result = self._apply_contextual_masking(result, context)
        
        return result, masked_items
    
    def _apply_contextual_masking(self, text: str, context: str) -> str:
        """Apply context-specific masking rules"""
        context = context.lower()
        
        # For logs, mask more aggressively
        if context in ('log', 'audit', 'structured'):
            # Mask internal IP ranges
            if self.config.mask_internal_ips:
                text = self._mask_internal_ips(text)
            
            # Mask internal hostnames
            if self.config.mask_internal_domains:
                text = self._mask_internal_domains(text)
        
        # For debug, preserve more
        if context == 'debug':
            # Only mask the most sensitive items
            pass
        
        return text
    
    def _mask_internal_ips(self, text: str) -> str:
        """Mask internal/private IP addresses"""
        # Common internal ranges
        internal_patterns = [
            (r'10\.\d+\.\d+\.\d+', '[INTERNAL_IP_10]'),
            (r'172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+', '[INTERNAL_IP_172]'),
            (r'192\.168\.\d+\.\d+', '[INTERNAL_IP_192]'),
            (r'127\.\d+\.\d+\.\d+', '[LOCALHOST]'),
            (r'localhost', '[LOCALHOST]'),
        ]
        
        for pattern, replacement in internal_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def _mask_internal_domains(self, text: str) -> str:
        """Mask internal domain names"""
        internal_domains = [
            r'\b[A-Za-z0-9-]+\.(local|internal|corp|intranet|private)\b',
            r'\b[A-Za-z0-9-]+\.example\.(com|org|net)\b',
        ]
        
        for pattern in internal_domains:
            text = re.sub(pattern, '[INTERNAL_DOMAIN]', text)
        
        return text
    
    def _hash_for_audit(self, value: str) -> str:
        """Create a hash of the original value for audit purposes"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    def mask_dict(
        self,
        data: Dict[str, Any],
        keys_to_mask: Optional[List[str]] = None,
        depth: int = 0,
        max_depth: int = 10,
    ) -> Tuple[Dict[str, Any], List[MaskedValue]]:
        """
        Recursively mask sensitive data in a dictionary.
        
        Args:
            data: Dictionary to process
            keys_to_mask: List of key names that should always be masked
            depth: Current recursion depth
            max_depth: Maximum recursion depth
        
        Returns:
            Tuple of (masked_dict, list_of_masked_items)
        """
        if depth > max_depth:
            return data, []
        
        masked_items = []
        result = {}
        
        # Default sensitive keys
        sensitive_keys = {
            'password', 'passwd', 'pwd', 'secret', 'token', 'api_key',
            'apikey', 'auth', 'authorization', 'credential', 'private_key',
            'access_key', 'session_token', 'jwt', 'bearer',
        }
        
        if keys_to_mask:
            sensitive_keys.update(keys_to_mask)
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key is sensitive
            if any(s in key_lower for s in sensitive_keys):
                masked_items.append(MaskedValue(
                    original_value=str(value)[:100],
                    masked_value='[REDACTED]',
                    category=DataCategory.CREDENTIAL,
                    pattern_match=f'key:{key}',
                    confidence=1.0,
                    hash_for_audit=self._hash_for_audit(str(value))
                ))
                result[key] = '[REDACTED]'
            
            elif isinstance(value, dict):
                masked_dict, items = self.mask_dict(
                    value, keys_to_mask, depth + 1, max_depth
                )
                result[key] = masked_dict
                masked_items.extend(items)
            
            elif isinstance(value, list):
                masked_list, items = self.mask_list(value, keys_to_mask, depth + 1, max_depth)
                result[key] = masked_list
                masked_items.extend(items)
            
            elif isinstance(value, str):
                masked_text, items = self.mask(value)
                result[key] = masked_text
                masked_items.extend(items)
            
            else:
                result[key] = value
        
        return result, masked_items
    
    def mask_list(
        self,
        data: List[Any],
        keys_to_mask: Optional[List[str]] = None,
        depth: int = 0,
        max_depth: int = 10,
    ) -> Tuple[List[Any], List[MaskedValue]]:
        """Recursively mask sensitive data in a list."""
        masked_items = []
        result = []
        
        for item in data:
            if isinstance(item, dict):
                masked_item, items = self.mask_dict(item, keys_to_mask, depth + 1, max_depth)
                result.append(masked_item)
                masked_items.extend(items)
            elif isinstance(item, list):
                masked_item, items = self.mask_list(item, keys_to_mask, depth + 1, max_depth)
                result.append(masked_item)
                masked_items.extend(items)
            elif isinstance(item, str):
                masked_text, items = self.mask(item)
                result.append(masked_text)
                masked_items.extend(items)
            else:
                result.append(item)
        
        return result, masked_items
    
    def get_stats(self) -> Dict[str, int]:
        """Get masking statistics"""
        return dict(self._masking_stats)
    
    def reset_stats(self) -> None:
        """Reset masking statistics"""
        self._masking_stats = {}


# === Safe Logging Wrappers ===

class SafeLogger:
    """
    Safe logging wrapper that automatically masks sensitive data.
    """
    
    def __init__(self, minimizer: Optional[DataMinimizer] = None):
        self.minimizer = minimizer or DataMinimizer()
        self.logger = logging.getLogger("cortex.safe_logging")
    
    def _format_message(self, message: str, context: str = "log") -> str:
        """Format message with masking"""
        masked, items = self.minimizer.mask(message, context)
        return masked
    
    def info(self, message: str, **kwargs) -> None:
        """Log info level message with masking"""
        masked = self._format_message(message, kwargs.get('_context', 'log'))
        self.logger.info(masked, **{k: v for k, v in kwargs.items() if not k.startswith('_')})
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning level message with masking"""
        masked = self._format_message(message, kwargs.get('_context', 'log'))
        self.logger.warning(masked, **{k: v for k, v in kwargs.items() if not k.startswith('_')})
    
    def error(self, message: str, **kwargs) -> None:
        """Log error level message with masking"""
        masked = self._format_message(message, kwargs.get('_context', 'log'))
        self.logger.error(masked, **{k: v for k, v in kwargs.items() if not k.startswith('_')})
    
    def audit(self, message: str, **kwargs) -> None:
        """Log audit message with masking"""
        masked = self._format_message(message, 'audit')
        self.logger.info(f"[AUDIT] {masked}", **{k: v for k, v in kwargs.items() if not k.startswith('_')})


# === Decorator for Safe Function Logging ===

def log_safe(logger: Optional[SafeLogger] = None, context: str = "log"):
    """
    Decorator to automatically mask sensitive data in function arguments.
    
    Usage:
        @log_safe()
        def process_user_data(user_data, password):
            # password will be masked in logs
            pass
    """
    _logger = logger or SafeLogger()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Mask arguments
            masked_args = []
            for arg in args:
                if isinstance(arg, (dict, list, str)):
                    masked, _ = _logger.minimizer.mask(str(arg), context)
                    masked_args.append(masked)
                else:
                    masked_args.append(arg)
            
            masked_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, (dict, list, str)):
                    masked, _ = _logger.minimizer.mask(str(v), context)
                    masked_kwargs[k] = masked
                else:
                    masked_kwargs[k] = v
            
            _logger.logger.debug(f"Calling {func.__name__}", args=masked_args, kwargs=masked_kwargs)
            
            try:
                result = func(*args, **kwargs)
                _logger.logger.debug(f"{func.__name__} completed")
                return result
            except Exception as e:
                _logger.logger.error(f"{func.__name__} failed: {str(e)}")
                raise
        
        return wrapper
    
    return decorator


# === Global instances ===

_global_minimizer: Optional[DataMinimizer] = None
_global_safe_logger: Optional[SafeLogger] = None


def get_data_minimizer() -> DataMinimizer:
    """Get global data minimizer instance"""
    global _global_minimizer
    if _global_minimizer is None:
        _global_minimizer = DataMinimizer()
    return _global_minimizer


def get_safe_logger() -> SafeLogger:
    """Get global safe logger instance"""
    global _global_safe_logger
    if _global_safe_logger is None:
        _global_safe_logger = SafeLogger(get_data_minimizer())
    return _global_safe_logger


def mask_for_logging(text: str, context: str = "log") -> str:
    """Quick function to mask text for logging"""
    minimizer = get_data_minimizer()
    masked, _ = minimizer.mask(text, context)
    return masked


def mask_dict_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """Quick function to mask dictionary for logging"""
    minimizer = get_data_minimizer()
    masked, _ = minimizer.mask_dict(data)
    return masked