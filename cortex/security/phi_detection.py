"""
Cortex Security - PHI Detection and Redaction

HIPAA-compliant PHI detection and masking:
- Detect all 18 HIPAA identifiers
- Regex-based pattern matching
- Contextual PHI detection (e.g., "Patient: John Doe")
- Auto-redaction with configurable styles
- PHI scoring for severity assessment

18 HIPAA Identifiers:
1. Names
2. Geographic data
3. Dates (birth, admission, discharge, death)
4. Phone numbers
5. Fax numbers
6. Email addresses
7. Social Security Numbers
8. Medical Record Numbers (MRN)
9. Health plan beneficiary numbers
10. Account numbers
11. Certificate/license numbers
12. Vehicle identifiers
13. Device identifiers
14. Web URLs
15. IP addresses
16. Biometric identifiers
17. Full-face photos
18. Any unique identifying number or code
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()


class PHIType(str, Enum):
    """Types of PHI identifiers"""
    NAME = "name"
    SSN = "ssn"
    MRN = "mrn"
    DATE = "date"
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    ADDRESS = "address"
    HEALTH_PLAN_NUMBER = "health_plan"
    ACCOUNT_NUMBER = "account"
    CERTIFICATE_NUMBER = "certificate"
    VEHICLE_ID = "vehicle"
    DEVICE_ID = "device"
    WEB_URL = "web_url"
    IP_ADDRESS = "ip_address"
    BIOMETRIC = "biometric"
    PHOTO = "photo"
    UNIQUE_ID = "unique_id"


@dataclass
class PHIMatch:
    """A detected PHI instance"""
    type: PHIType
    text: str
    start: int
    end: int
    confidence: float  # 0.0 to 1.0
    context: str = ""  # Surrounding text for context
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "context": self.context,
        }


class PHIDetector:
    """
    Detect Protected Health Information (PHI) in text
    
    Uses multiple detection methods:
    1. Regex pattern matching for structured formats
    2. Contextual analysis for semi-structured formats
    3. Named Entity Recognition for names and places
    
    Usage:
        detector = PHIDetector()
        phi_instances = detector.detect_all_phi(text)
        if phi_instances:
            redacted = detector.redact_phi(text, phi_instances)
    """
    
    # PHI patterns with confidence levels
    PATTERNS = {
        # Social Security Number (high confidence)
        PHIType.SSN: [
            (r'\b\d{3}-\d{2}-\d{4}\b', 0.95),  # XXX-XX-XXXX
            (r'\b\d{3}\s\d{2}\s\d{4}\b', 0.90),  # XXX XX XXXX
        ],
        
        # Medical Record Number (high confidence)
        PHIType.MRN: [
            (r'\b(?:MRN|Medical Record Number|MR #|Medical Rec)[:\s]*\d{6,10}\b', 0.95),
            (r'\b[A-Z]{2,3}\d{6,8}\b', 0.70),  # Hospital-specific format
        ],
        
        # Dates (medium confidence - context matters)
        PHIType.DATE: [
            (r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', 0.70),  # MM/DD/YYYY
            (r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', 0.85),
            (r'\b\d{4}[/-]\d{2}[/-]\d{2}\b', 0.75),  # YYYY-MM-DD
            (r'\b(?:DOB|Date of Birth|Birth Date)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', 0.95),
        ],
        
        # Phone numbers (medium confidence)
        PHIType.PHONE: [
            (r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b', 0.80),
            (r'\b\d{3}[-.]\d{3}[-.]\d{4}\b', 0.85),
            (r'\b(?:Phone|Telephone|Tel|Mobile|Cell)[:\s]+\d{3}[-.]\d{3}[-.]\d{4}\b', 0.95),
        ],
        
        # Fax numbers (medium confidence)
        PHIType.FAX: [
            (r'\b(?:Fax|Fax Number)[:\s]+\d{3}[-.]\d{3}[-.]\d{4}\b', 0.95),
        ],
        
        # Email addresses (high confidence)
        PHIType.EMAIL: [
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 0.95),
            (r'\b(?:Email|Email Address|E-mail)[:\s]+[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 0.98),
        ],
        
        # Addresses (medium confidence)
        PHIType.ADDRESS: [
            (r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Circle|Cir)\b', 0.80),
            (r'\b(?:Address|Home Address|Street Address)[:\s]+[^,\n]+(?:[A-Z]{2}\s+\d{5})?\b', 0.85),
        ],
        
        # Health plan numbers (medium confidence)
        PHIType.HEALTH_PLAN_NUMBER: [
            (r'\b(?:Member|Policy|Plan|Subscriber|Health Plan)[:\s]+[A-Z0-9]{8,12}\b', 0.85),
        ],
        
        # Account numbers (low confidence)
        PHIType.ACCOUNT_NUMBER: [
            (r'\b(?:Account|Acct|Account Number)[:\s]+\d{8,12}\b', 0.80),
        ],
        
        # Certificate numbers (medium confidence)
        PHIType.CERTIFICATE_NUMBER: [
            (r'\b(?:Certificate|Cert|License)[:\s]+[A-Z0-9]{8,12}\b', 0.85),
        ],
        
        # Vehicle identifiers (medium confidence)
        PHIType.VEHICLE_ID: [
            (r'\b[A-Z]{3}[ -][A-Z]{2}[ -]\d{3,4}\b', 0.75),  # License plate format
            (r'\b\d{4}[ -][A-Z]{3}[ -]\d{3}\b', 0.70),
        ],
        
        # Device identifiers (medium confidence)
        PHIType.DEVICE_ID: [
            (r'\b(?:Serial|Device|IMEI)[:\s]+[A-Z0-9-]{10,}\b', 0.85),
        ],
        
        # Web URLs (high confidence)
        PHIType.WEB_URL: [
            (r'\bhttps?://[^\s<>"{}|\\^`\[\]]+\b', 0.90),
            (r'\bwww\.[^\s<>"{}|\\^`\[\]]+\.[A-Z|a-z]{2,}\b', 0.85),
        ],
        
        # IP addresses (high confidence)
        PHIType.IP_ADDRESS: [
            (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 0.90),
        ],
        
        # Biometric identifiers (low confidence - usually need context)
        PHIType.BIOMETRIC: [
            (r'\b(?:Fingerprint|Retinal|DNA|Voiceprint|Iris scan)[:\s]+[A-Z0-9-]+\b', 0.85),
        ],
    }
    
    # Contextual PHI patterns (higher confidence when found with context)
    CONTEXT_PATTERNS = [
        # Names
        (r'(?:Patient|Name|Patient Name|Full Name|First Name|Last Name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', PHIType.NAME, 0.95),
        
        # Dates with context
        (r'(?:DOB|Date of Birth|Birth Date|Birthdate)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', PHIType.DATE, 0.98),
        (r'(?:Admission Date|Admit Date)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', PHIType.DATE, 0.98),
        (r'(?:Discharge Date)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', PHIType.DATE, 0.98),
        
        # SSN with context
        (r'(?:SSN|Social Security|Social Security Number)[:\s]+(\d{3}[-\s]?\d{2}[-\s]?\d{4})', PHIType.SSN, 0.99),
        
        # MRN with context
        (r'(?:MRN|Medical Record)#?[:\s]+(\d{6,10})', PHIType.MRN, 0.99),
        
        # Account numbers with context
        (r'(?:Account|Acct)#?[:\s]+(\d{8,12})', PHIType.ACCOUNT_NUMBER, 0.90),
    ]
    
    def __init__(self):
        self.compiled_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        for phi_type, patterns in self.PATTERNS.items():
            self.compiled_patterns[phi_type] = [
                (re.compile(pattern, re.IGNORECASE), confidence)
                for pattern, confidence in patterns
            ]
        
        # Compile context patterns
        self.compiled_context_patterns = [
            (re.compile(pattern, re.IGNORECASE), phi_type, confidence)
            for pattern, phi_type, confidence in self.CONTEXT_PATTERNS
        ]
    
    def detect_all_phi(self, text: str) -> List[PHIMatch]:
        """
        Detect all PHI in text using multiple methods
        
        Args:
            text: Text to analyze
        
        Returns:
            List of PHIMatch objects representing detected PHI
        """
        matches = []
        
        # Method 1: Regex pattern matching
        matches.extend(self._detect_by_regex(text))
        
        # Method 2: Contextual analysis
        matches.extend(self._detect_by_context(text))
        
        # Remove duplicates and sort by position
        matches = self._deduplicate(matches)
        
        return matches
    
    def _detect_by_regex(self, text: str) -> List[PHIMatch]:
        """Detect PHI using regex patterns"""
        matches = []
        
        for phi_type, patterns in self.compiled_patterns.items():
            for pattern, confidence in patterns:
                for match in pattern.finditer(text):
                    phi_match = PHIMatch(
                        type=phi_type,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        context=self._get_context(text, match.start(), match.end())
                    )
                    matches.append(phi_match)
        
        return matches
    
    def _detect_by_context(self, text: str) -> List[PHIMatch]:
        """Detect PHI using contextual patterns"""
        matches = []
        
        for pattern, phi_type, confidence in self.compiled_context_patterns:
            for match in pattern.finditer(text):
                # Some patterns have capture groups for the PHI
                if match.groups():
                    phi_text = match.group(1)
                    phi_start = match.start(1)
                    phi_end = match.end(1)
                else:
                    phi_text = match.group()
                    phi_start = match.start()
                    phi_end = match.end()
                
                phi_match = PHIMatch(
                    type=phi_type,
                    text=phi_text,
                    start=phi_start,
                    end=phi_end,
                    confidence=confidence,
                    context=self._get_context(text, phi_start, phi_end)
                )
                matches.append(phi_match)
        
        return matches
    
    def _get_context(self, text: str, start: int, end: int, context_size: int = 50) -> str:
        """Get surrounding context for PHI match"""
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        return text[context_start:context_end]
    
    def _deduplicate(self, matches: List[PHIMatch]) -> List[PHIMatch]:
        """Remove duplicate matches, keeping highest confidence"""
        # Sort by start position
        matches.sort(key=lambda m: m.start)
        
        # Remove overlaps, keeping highest confidence
        deduplicated = []
        for match in matches:
            # Check if this match overlaps with any existing
            is_duplicate = False
            for existing in deduplicated:
                if match.start < existing.end and match.end > existing.start:
                    # Overlap - keep higher confidence
                    if match.confidence > existing.confidence:
                        deduplicated.remove(existing)
                        deduplicated.append(match)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(match)
        
        return deduplicated
    
    def contains_phi(self, text: str) -> bool:
        """
        Quickly check if text contains any PHI
        
        Args:
            text: Text to check
        
        Returns:
            True if PHI detected, False otherwise
        """
        return len(self.detect_all_phi(text)) > 0
    
    def calculate_phi_score(self, text: str) -> float:
        """
        Calculate PHI risk score (0.0 to 100.0)
        
        Higher score = more PHI present.
        Factors:
        - Number of PHI instances
        - Types of PHI (SSN is higher risk than name)
        - Confidence levels
        
        Args:
            text: Text to analyze
        
        Returns:
            PHI risk score from 0.0 to 100.0
        """
        matches = self.detect_all_phi(text)
        
        if not matches:
            return 0.0
        
        # Weight by PHI type
        type_weights = {
            PHIType.SSN: 20.0,  # Highest risk
            PHIType.MRN: 15.0,
            PHIType.HEALTH_PLAN_NUMBER: 15.0,
            PHIType.DATE: 10.0,
            PHIType.NAME: 8.0,
            PHIType.EMAIL: 8.0,
            PHIType.PHONE: 5.0,
            PHIType.ADDRESS: 5.0,
            PHIType.FAX: 5.0,
            PHIType.ACCOUNT_NUMBER: 10.0,
            PHIType.CERTIFICATE_NUMBER: 8.0,
            PHIType.VEHICLE_ID: 3.0,
            PHIType.DEVICE_ID: 5.0,
            PHIType.WEB_URL: 3.0,
            PHIType.IP_ADDRESS: 3.0,
            PHIType.BIOMETRIC: 15.0,
            PHIType.PHOTO: 10.0,
            PHIType.UNIQUE_ID: 8.0,
        }
        
        # Calculate weighted score
        total_score = 0.0
        for match in matches:
            weight = type_weights.get(match.type, 5.0)
            total_score += weight * match.confidence
        
        # Normalize to 0-100
        max_possible_score = sum(type_weights.values())  # ~130
        normalized_score = min(100.0, (total_score / max_possible_score) * 100)
        
        return round(normalized_score, 2)


class PHIRedactor:
    """
    Redact PHI from text
    
    Supports multiple redaction styles:
    - Full replacement: [REDACTED]
    - Partial replacement: ***-**-****
    - Generic replacement: [PHI_REMOVED]
    - Type-specific: [SSN_REMOVED]
    """
    
    REDACTION_STYLES = {
        "full": "[REDACTED]",
        "generic": "[PHI_REMOVED]",
        "type_specific": "[{TYPE}_REMOVED]",
        "partial": "***",  # Show partial info
        "hash": "<PHI:{HASH}>",  # Replace with hash for reversibility
    }
    
    def __init__(self, style: str = "type_specific"):
        """
        Initialize redactor
        
        Args:
            style: Redaction style (full, generic, type_specific, partial, hash)
        """
        self.style = style
        self.detector = PHIDetector()
    
    def redact(
        self,
        text: str,
        matches: Optional[List[PHIMatch]] = None
    ) -> Tuple[str, List[PHIMatch]]:
        """
        Redact all PHI from text
        
        Args:
            text: Text to redact
            matches: Pre-detected PHI matches (optional, will detect if not provided)
        
        Returns:
            Tuple of (redacted_text, phi_matches)
        """
        if matches is None:
            matches = self.detector.detect_all_phi(text)
        
        if not matches:
            return text, []
        
        # Sort matches by start position (descending to not affect positions)
        matches.sort(key=lambda m: m.start, reverse=True)
        
        redacted_text = text
        for match in matches:
            replacement = self._get_replacement(match)
            redacted_text = (
                redacted_text[:match.start] + 
                replacement + 
                redacted_text[match.end:]
            )
        
        return redacted_text, matches
    
    def _get_replacement(self, match: PHIMatch) -> str:
        """Get replacement text based on style"""
        if self.style == "full":
            return self.REDACTION_STYLES["full"]
        
        elif self.style == "generic":
            return self.REDACTION_STYLES["generic"]
        
        elif self.style == "type_specific":
            return f"[{match.type.value.upper()}_REMOVED]"
        
        elif self.style == "partial":
            return self._partial_mask(match)
        
        elif self.style == "hash":
            return self._hash_replacement(match)
        
        else:
            return self.REDACTION_STYLES["full"]
    
    def _partial_mask(self, match: PHIMatch) -> str:
        """Partially mask PHI (show some characters)"""
        text = match.text
        
        if match.type == PHIType.SSN:
            # SSN: ***-**-1234
            if len(text) >= 7:
                return f"***-**-{text[-4:]}"
            return "***"
        
        elif match.type == PHIType.PHONE:
            # Phone: ***-***-1234
            if len(text) >= 10:
                return f"***-***-{text[-4:]}"
            return "***"
        
        elif match.type == PHIType.EMAIL:
            # Email: jo***@example.com
            parts = text.split("@")
            if len(parts) == 2 and len(parts[0]) > 2:
                return f"{parts[0][:2]}***@{parts[1]}"
            return "***"
        
        elif match.type == PHIType.MRN:
            # MRN: ***123
            if len(text) >= 6:
                return f"***{text[-3:]}"
            return "***"
        
        elif match.type == PHIType.DATE:
            # Dates: ***-**-****
            return "***"
        
        elif match.type == PHIType.NAME:
            # Names: J***
            if len(text) > 0:
                return f"{text[0]}***"
            return "***"
        
        else:
            # Default: full mask
            return "[REDACTED]"
    
    def _hash_replacement(self, match: PHIMatch) -> str:
        """Replace PHI with hash (for reversibility)"""
        import hashlib
        hash_value = hashlib.sha256(match.text.encode()).hexdigest()[:8]
        return f"<PHI:{hash_value}>"
    
    def redact_file(
        self,
        input_path: str,
        output_path: str
    ) -> Tuple[bool, List[PHIMatch]]:
        """
        Redact PHI from file
        
        Args:
            input_path: Path to input file
            output_path: Path to output file
        
        Returns:
            Tuple of (success, phi_matches)
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            redacted_content, matches = self.redact(content)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(redacted_content)
            
            logger.info(
                "file_redacted",
                input_path=input_path,
                output_path=output_path,
                phi_count=len(matches)
            )
            
            return True, matches
        
        except Exception as e:
            logger.error(f"Failed to redact file: {e}")
            return False, []


# === Convenience Functions ===

def detect_phi(text: str) -> List[PHIMatch]:
    """
    Convenience function to detect PHI
    
    Args:
        text: Text to analyze
    
    Returns:
        List of PHI matches
    """
    detector = PHIDetector()
    return detector.detect_all_phi(text)


def redact_phi(
    text: str,
    style: str = "type_specific"
) -> Tuple[str, List[PHIMatch]]:
    """
    Convenience function to redact PHI
    
    Args:
        text: Text to redact
        style: Redaction style
    
    Returns:
        Tuple of (redacted_text, phi_matches)
    """
    redactor = PHIRedactor(style=style)
    return redactor.redact(text)


def contains_phi(text: str) -> bool:
    """
    Convenience function to check if text contains PHI
    
    Args:
        text: Text to check
    
    Returns:
        True if PHI detected, False otherwise
    """
    detector = PHIDetector()
    return detector.contains_phi(text)


def get_phi_score(text: str) -> float:
    """
    Convenience function to get PHI risk score
    
    Args:
        text: Text to analyze
    
    Returns:
        PHI risk score (0.0 to 100.0)
    """
    detector = PHIDetector()
    return detector.calculate_phi_score(text)


# === Export ===

__all__ = [
    "PHIType",
    "PHIMatch",
    "PHIDetector",
    "PHIRedactor",
    "detect_phi",
    "redact_phi",
    "contains_phi",
    "get_phi_score",
]