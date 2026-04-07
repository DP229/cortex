"""
Cortex Deterministic Quoting - Hallucination Prevention Layer

Phase 1 Compliance Enhancement: Post-processing validation that ensures
LLM outputs are verifiable against source documents.

Key Features:
- Citation extraction and validation
- Exact text matching against source documents
- Hallucination detection and flagging
- Source attribution tracking
- Safety-class-aware thresholds (high safety = stricter matching)
- Proper punctuation/number handling

For safety-critical industries (IEC 62304, EN 50128), this layer
provides the traceability required for regulatory compliance.
"""

import re
import hashlib
from typing import List, Optional, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY-CLASS THRESHOLD CONFIGURATION
# =============================================================================

class ThresholdConfig:
    """
    Dynamic threshold configuration based on safety class.
    
    IEC 62304 Safety Classes:
    - Class A: Software that could contribute to hazard (strictest)
    - Class B: Software whose failure could result in serious injury
    - Class C: Software whose failure could result in death
    
    Higher safety class = stricter verification required.
    """
    
    # Safety class to threshold mapping
    DEFAULT_THRESHOLDS = {
        "critical": 0.98,   # Class A - death, near-exact match required
        "high": 0.95,       # Class B - serious injury
        "medium": 0.85,     # Standard requirements
        "low": 0.70,        # Informational content
        "unknown": 0.80,    # Default when safety class unknown
    }
    
    def __init__(self, custom_thresholds: Optional[Dict[str, float]] = None):
        self._thresholds = {**self.DEFAULT_THRESHOLDS}
        if custom_thresholds:
            self._thresholds.update(custom_thresholds)
    
    def get_threshold(self, safety_class: str) -> float:
        """Get threshold for a given safety class"""
        return self._thresholds.get(
            safety_class.lower(),
            self._thresholds["unknown"]
        )
    
    def is_strict_mode(self, safety_class: str) -> bool:
        """Check if strict mode is required for safety class"""
        return safety_class.lower() in ("critical", "high")


# =============================================================================
# CITATION DATA CLASSES
# =============================================================================

@dataclass
class Citation:
    """A verified citation from source document"""
    source_path: str
    source_title: str
    quote: str
    start_offset: int
    end_offset: int
    verification_status: str  # "verified", "modified", "not_found", "partial"
    similarity_score: float = 1.0
    context_before: str = ""
    context_after: str = ""
    hash: str = ""
    safety_class: str = "unknown"  # Safety class of the requirement
    citation_format: str = "unknown"  # Format detected (markdown, superscript, author_year, etc.)
    
    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.sha256(self.quote.encode()).hexdigest()[:16]


@dataclass
class ValidatedOutput:
    """Output with verified citations"""
    content: str
    citations: List[Citation]
    hallucination_flags: List[Dict[str, Any]]
    verification_score: float  # 0.0 to 1.0
    is_compliant: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """Convert to markdown with verified citations"""
        output = self.content
        output += "\n\n---\n\n## Sources\n\n"
        
        for i, cite in enumerate(self.citations, 1):
            status_icon = "✅" if cite.verification_status == "verified" else "⚠️"
            output += f"{i}. {status_icon} [{cite.source_title}]({cite.source_path})\n"
            if cite.verification_status != "verified":
                output += f"   - Status: {cite.verification_status}\n"
                output += f"   - Similarity: {cite.similarity_score:.2%}\n"
        
        if self.hallucination_flags:
            output += "\n### ⚠️ Hallucination Flags\n\n"
            for flag in self.hallucination_flags:
                output += f"- **{flag['type']}**: {flag['text'][:100]}...\n"
        
        return output


# =============================================================================
# CITATION EXTRACTOR (EXPANDED FORMAT SUPPORT)
# =============================================================================

class CitationExtractor:
    """
    Extracts citations from LLM output in multiple standard formats.
    
    Supported formats:
    - Markdown links: [text](path.md)
    - Wikilinks: [[path|alias]] or [[path]]
    - Superscript: text¹, text², text⁳
    - Bracketed numbers: [1], [2], [123]
    - Author-year: (Smith, 2024), (Jones et al., 2023)
    - Numeric with footnote markers: [Note 1], [Ref 5]
    - Explicit source: "quote" (source: path)
    - Academic numbered: [1] Author Name, Title, etc.
    """
    
    # Patterns for different citation formats
    CITATION_PATTERNS = [
        # 1. Markdown links with context: "text [link text](path.md) more text"
        (
            r'([^.!?]*?)\s*\[([^\]]+)\]\(([^)]+\.(?:md|markdown|txt))\)',
            'markdown_link',
        ),
        
        # 2. Wikilinks: [[path]] or [[path|display text]]
        (
            r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]',
            'wikilink',
        ),
        
        # 3. Superscript citations: text¹, text², text⁳, textᴺ
        #    Unicode superscript numbers: ⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ
        (
            r'([^\s⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ]*?)([⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ]+)',
            'superscript',
        ),
        
        # 4. Bracketed numbers: [1], [2], [123]
        (
            r'\[([1-9][0-9]{0,3})\]',
            'bracketed_number',
        ),
        
        # 5. Author-year citations: (Smith, 2024), (Jones et al., 2023)
        (
            r'\(([A-Z][a-z]+(?:\s+(?:et\s+al\.|and\s+[A-Z][a-z]+))?),?\s+(?:19|20)\d{2}[a-z]?\)',
            'author_year',
        ),
        
        # 6. Explicit quotes with source: "quote" (source: path)
        (
            r'"([^"]+)"\s*\([^)]*source:\s*([^)]+)\)',
            'explicit_source',
        ),
        
        # 7. References section entries: [1] Title, Path
        (
            r'\[([1-9][0-9]{0,3})\]\s*\[\[([^\]]+)\]\]',
            'ref_wikilink',
        ),
        
        # 8. Footnote-style: [Note 1], [Ref 5], [Citation 2]
        (
            r'\[(?:Note|Ref|Citation|Source)\s+([1-9][0-9]{0,3})\]',
            'footnote_style',
        ),
    ]
    
    # Unicode superscript to digit mapping
    SUPERSCRIPT_MAP = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
        'ⁿ': 'n',  # n represents any number
    }
    
    def __init__(self):
        self._compiled_patterns: List[Tuple[Any, str]] = []
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency"""
        for pattern, format_type in self.CITATION_PATTERNS:
            try:
                compiled = re.compile(pattern, re.MULTILINE | re.DOTALL)
                self._compiled_patterns.append((compiled, format_type))
            except re.error as e:
                logger.warning(f"citation_pattern_compile_failed: {e}")
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract all citations from text.
        
        Returns list of dicts with:
        - source_path: Path or reference number
        - quote: The text being cited
        - format: Type of citation detected
        - position: Char offset in text
        - context: Surrounding text for disambiguation
        """
        citations = []
        seen_refs: Set[str] = set()  # Avoid duplicates
        
        for pattern, format_type in self._compiled_patterns:
            for match in pattern.finditer(text):
                citation = self._parse_match(match, format_type, text)
                if citation:
                    # Deduplicate by source_ref
                    ref_key = f"{citation['source_ref']}:{citation['quote'][:50]}"
                    if ref_key not in seen_refs:
                        seen_refs.add(ref_key)
                        citations.append(citation)
        
        # Sort by position in text
        citations.sort(key=lambda x: x['position'])
        
        return citations
    
    def _parse_match(self, match: re.Match, format_type: str, text: str) -> Optional[Dict[str, Any]]:
        """Parse a regex match into a citation dict"""
        try:
            span = match.span()
            context_start = max(0, span[0] - 200)
            context_end = min(len(text), span[1] + 200)
            
            if format_type == 'markdown_link':
                context, link_text, source_path = match.groups()
                return {
                    'source_ref': source_path,
                    'quote': (context.strip() + " " + link_text).strip()[:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'wikilink':
                source_path = match.group(1)
                if not source_path.endswith(('.md', '.markdown', '.txt')):
                    source_path += '.md'
                return {
                    'source_ref': source_path,
                    'quote': text[context_start:context_end][:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'superscript':
                # text followed by superscript number
                prefix_text, superscript_chars = match.groups()
                ref_num = self._decode_superscript(superscript_chars)
                return {
                    'source_ref': f"REF_{ref_num}",
                    'quote': (prefix_text + superscript_chars).strip()[:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'bracketed_number':
                ref_num = match.group(1)
                return {
                    'source_ref': f"REF_{ref_num}",
                    'quote': text[max(0, span[0] - 100):min(len(text), span[1] + 100)][:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'author_year':
                author, year = match.groups()
                return {
                    'source_ref': f"{author}_{year}",
                    'quote': match.group(0)[:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'explicit_source':
                quote, source_path = match.groups()
                return {
                    'source_ref': source_path.strip(),
                    'quote': quote,
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'ref_wikilink':
                ref_num, source_path = match.groups()
                return {
                    'source_ref': source_path,
                    'quote': text[max(0, span[0] - 50):min(len(text), span[1] + 50)][:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
            
            elif format_type == 'footnote_style':
                ref_num = match.group(1)
                return {
                    'source_ref': f"REF_{ref_num}",
                    'quote': text[max(0, span[0] - 100):min(len(text), span[1] + 100)][:500],
                    'format': format_type,
                    'position': span[0],
                    'context': text[context_start:context_end],
                }
        
        except Exception as e:
            logger.debug(f"citation_parse_failed: {e}")
        
        return None
    
    def _decode_superscript(self, superscript_chars: str) -> str:
        """Decode Unicode superscript characters to digit string"""
        result = []
        for char in superscript_chars:
            if char in self.SUPERSCRIPT_MAP:
                result.append(self.SUPERSCRIPT_MAP[char])
            else:
                # Unknown superscript, use the char itself
                result.append(char)
        return ''.join(result)


# =============================================================================
# TEXT NORMALIZER (FIXED - PRESERVES SEMANTIC MEANING)
# =============================================================================

class TextNormalizer:
    """
    Normalizes text for comparison while preserving semantic meaning.
    
    CRITICAL FIXES from v1:
    1. DOES NOT strip decimal points (3.14 stays 3.14)
    2. DOES NOT strip hyphens in compound words
    3. DOES preserve case for single-char identifiers
    4. DOES preserve version numbers (v1.2.3)
    5. DOES preserve ratios and percentages
    
    The old approach stripped ALL punctuation, which destroyed:
    - Decimals: "IEC 62304" → "IEC62304" (correct)
    - BUT: "3.14" → "314" (WRONG - semantic change)
    - AND: "v1.2" → "v12" (WRONG)
    """
    
    # Words that should be treated as case-insensitive
    CASE_INSENSITIVE = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can',
    }
    
    # Patterns to preserve exactly (don't touch these)
    PRESERVE_PATTERNS = [
        r'\d+\.\d+',           # Decimals: 3.14, 1.5, etc.
        r'\d+\.\d+\.\d+',      # Version numbers: 1.2.3
        r'v\d+\.\d+',          # Version prefixes: v1.2
        r'\d+%',               # Percentages: 95%
        r'\d+:[0-9]+',         # Ratios: 16:9
        r'[A-Z]{2,}',          # Acronyms: IEC, FDA, WHO
        r'[a-z]+\.[a-z]+\.',   # Initials: J.F. Smith
        r'U\.S\.',             # Common abbreviations
        r'e\.g\.',             # Latin abbreviations
        r'i\.e\.',
        r'etc\.',
    ]
    
    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive
        self._preserve_regex = re.compile('|'.join(self.PRESERVE_PATTERNS))
        
        # Build normalization regex
        # Only remove punctuation that's truly noise
        self._noise_punctuation = re.compile(r'["\'""''`]+')  # Only quote marks
    
    def _normalize_preserved(self, text: str) -> str:
        """Replace preserved patterns with placeholders"""
        placeholders: Dict[str, str] = {}
        
        def replacer(match):
            key = f"__PRESERVE_{len(placeholders)}__"
            placeholders[key] = match.group(0)
            return key
        
        protected_text = self._preserve_regex.sub(replacer, text)
        return protected_text, placeholders
    
    def _restore_preserved(self, text: str, placeholders: Dict[str, str]) -> str:
        """Restore preserved patterns from placeholders"""
        result = text
        for key, value in sorted(placeholders.items()):
            result = result.replace(key, value)
        return result
    
    def normalize(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Preserves:
        - Decimals (3.14 stays as marker that can be matched)
        - Version numbers (v1.2.3)
        - Percentages (95%)
        - Acronyms (IEC, FDA)
        
        Normalizes:
        - Extra whitespace → single space
        - Quote marks → removed
        - Case (unless case_sensitive=True)
        """
        if not text:
            return ""
        
        # Step 1: Protect preserved patterns
        protected_text, placeholders = self._normalize_preserved(text)
        
        # Step 2: Lowercase only case-insensitive words
        if not self.case_sensitive:
            protected_text = self._lowercase_respectful(protected_text)
        
        # Step 3: Remove noise punctuation (just quotes)
        protected_text = self._noise_punctuation.sub('', protected_text)
        
        # Step 4: Normalize whitespace
        protected_text = ' '.join(protected_text.split())
        
        # Step 5: Restore preserved patterns
        result = self._restore_preserved(protected_text, placeholders)
        
        return result
    
    def _lowercase_respectful(self, text: str) -> str:
        """
        Lowercase text while respecting word boundaries.
        
        Words that are all-caps (acronyms) or single letters are preserved.
        """
        words = text.split()
        result = []
        
        for word in words:
            stripped = word.strip('.,;:!?()[]{}')
            core = word
            
            # Check if this is an acronym (all caps, 2+ chars)
            if stripped.isupper() and len(stripped) >= 2:
                result.append(word)
            # Single capital letter (likely an initial)
            elif stripped.isupper() and len(stripped) == 1:
                result.append(word)
            else:
                result.append(word.lower())
        
        return ' '.join(result)
    
    def normalize_for_exact_match(self, text: str) -> str:
        """
        Normalize for exact substring matching.
        
        More aggressive - preserves less but finds more matches.
        """
        if not text:
            return ""
        
        # Protect decimals first
        protected_text, placeholders = self._normalize_preserved(text)
        
        # Remove punctuation except periods in decimals (handled by placeholders)
        protected_text = re.sub(r'[^\w\s.]', '', protected_text)
        
        # Normalize whitespace
        protected_text = ' '.join(protected_text.split())
        
        return self._restore_preserved(protected_text, placeholders)


# =============================================================================
# DETERMINISTIC QUOTER (REFACTORED)
# =============================================================================

class DeterministicQuoter:
    """
    Validates LLM outputs against source documents.
    
    Refactored to fix:
    1. Normalization destroys decimals/semantic meaning
    2. Hardcoded 85% threshold ignores safety class
    3. Citation formats incomplete
    
    This is the core compliance layer for safety-critical industries.
    Every claim in the output must be traceable to a source document.
    """
    
    def __init__(
        self,
        knowledgebase,
        strict_mode: bool = True,
        threshold_config: Optional[ThresholdConfig] = None,
        context_window: int = 100,
    ):
        self.kb = knowledgebase
        self.strict_mode = strict_mode
        self.threshold_config = threshold_config or ThresholdConfig()
        self.context_window = context_window
        
        # Initialize components
        self._extractor = CitationExtractor()
        self._normalizer = TextNormalizer()
    
    def validate(
        self,
        llm_output: str,
        max_sources: int = 10,
        safety_class: str = "unknown",
    ) -> ValidatedOutput:
        """
        Validate LLM output against knowledge base.
        
        Args:
            llm_output: The text output from the LLM
            max_sources: Maximum citations to verify
            safety_class: Safety class for threshold determination
            
        Returns:
            ValidatedOutput with citations, flags, and compliance status
        """
        citations = []
        hallucination_flags = []
        
        # Get threshold for this safety class
        threshold = self.threshold_config.get_threshold(safety_class)
        
        # Extract citations
        potential_citations = self._extractor.extract(llm_output)
        
        for cite_data in potential_citations[:max_sources]:
            citation = self._verify_citation(
                cite_data['source_ref'],
                cite_data['quote'],
                cite_data['format'],
                safety_class,
            )
            if citation:
                citations.append(citation)
        
        # Detect hallucinations
        hallucination_flags = self._detect_hallucinations(llm_output, citations, safety_class)
        
        # Calculate score with safety-class-aware threshold
        verification_score = self._calculate_score(citations, hallucination_flags, threshold)
        
        # Determine compliance
        is_compliant = self._check_compliance(
            verification_score,
            hallucination_flags,
            threshold,
            safety_class,
        )
        
        return ValidatedOutput(
            content=llm_output,
            citations=citations,
            hallucination_flags=hallucination_flags,
            verification_score=verification_score,
            is_compliant=is_compliant,
            metadata={
                "strict_mode": self.strict_mode,
                "safety_class": safety_class,
                "threshold_used": threshold,
                "total_citations": len(citations),
                "verified_citations": sum(1 for c in citations if c.verification_status == "verified"),
            }
        )
    
    def _verify_citation(
        self,
        source_ref: str,
        claimed_content: str,
        citation_format: str,
        safety_class: str,
    ) -> Optional[Citation]:
        """
        Verify a citation against source documents.
        
        Uses safety-class-aware threshold for matching.
        """
        # Resolve source reference to actual path
        source_path = self._resolve_source_ref(source_ref)
        
        # Load source article
        article = self.kb.get_article(source_path)
        if not article:
            return Citation(
                source_path=source_path,
                source_title=source_path,
                quote=claimed_content[:500],
                start_offset=0,
                end_offset=len(claimed_content),
                verification_status="not_found",
                similarity_score=0.0,
                safety_class=safety_class,
                citation_format=citation_format,
            )
        
        source_text = article.content
        
        # Get threshold for this safety class
        threshold = self.threshold_config.get_threshold(safety_class)
        
        # Try exact match first
        exact_match = self._try_exact_match(claimed_content, source_text, source_path, article, citation_format, safety_class)
        if exact_match:
            return exact_match
        
        # Try sentence-level matching
        sentence_match = self._try_sentence_match(claimed_content, source_text, source_path, article, citation_format, safety_class)
        if sentence_match:
            return sentence_match
        
        # Fuzzy match with safety-class-aware threshold
        fuzzy_match = self._try_fuzzy_match(claimed_content, source_text, source_path, article, citation_format, safety_class, threshold)
        if fuzzy_match:
            return fuzzy_match
        
        # Not found
        return Citation(
            source_path=source_path,
            source_title=article.title,
            quote=claimed_content[:500],
            start_offset=0,
            end_offset=len(claimed_content),
            verification_status="not_found",
            similarity_score=0.0,
            safety_class=safety_class,
            citation_format=citation_format,
        )
    
    def _resolve_source_ref(self, source_ref: str) -> str:
        """Resolve citation reference to actual path"""
        # Already a path
        if source_ref.endswith(('.md', '.markdown', '.txt')):
            return source_ref
        
        # Reference number (REF_123)
        if source_ref.startswith('REF_'):
            # Would need references section mapping
            return f"references/ref_{source_ref[4:]}.md"
        
        # Author-year (Smith_2024)
        if '_' in source_ref:
            author, year = source_ref.rsplit('_', 1)
            return f"references/{author.lower()}_{year}.md"
        
        # Try as-is with .md extension
        return source_ref + '.md'
    
    def _try_exact_match(
        self,
        claimed: str,
        source: str,
        source_path: str,
        article,
        citation_format: str,
        safety_class: str,
    ) -> Optional[Citation]:
        """Try exact substring match"""
        # Normalize for exact match
        norm_claim = self._normalizer.normalize_for_exact_match(claimed)
        norm_source = self._normalizer.normalize_for_exact_match(source)
        
        if norm_claim in norm_source:
            start_idx = norm_source.find(norm_claim)
            end_idx = start_idx + len(norm_claim)
            
            context_before = source[max(0, start_idx - self.context_window):start_idx]
            context_after = source[end_idx:min(len(source), end_idx + self.context_window)]
            
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed[:500],
                start_offset=start_idx,
                end_offset=end_idx,
                verification_status="verified",
                similarity_score=1.0,
                context_before=context_before,
                context_after=context_after,
                safety_class=safety_class,
                citation_format=citation_format,
            )
        
        return None
    
    def _try_sentence_match(
        self,
        claimed: str,
        source: str,
        source_path: str,
        article,
        citation_format: str,
        safety_class: str,
    ) -> Optional[Citation]:
        """Try matching at sentence level"""
        # Split into sentences
        claim_sentences = self._split_into_sentences(claimed)
        
        # Filter to substantial sentences (20+ chars)
        claim_sentences = [s for s in claim_sentences if len(s) >= 20]
        
        if not claim_sentences:
            return None
        
        # Find matching sentences in source
        norm_source = self._normalizer.normalize(source)
        matched_sentences = 0
        best_match_start = 0
        
        for sentence in claim_sentences:
            norm_sentence = self._normalizer.normalize_for_exact_match(sentence)
            if norm_sentence in norm_source:
                matched_sentences += 1
                best_match_start = norm_source.find(norm_sentence)
        
        if matched_sentences == 0:
            return None
        
        match_ratio = matched_sentences / len(claim_sentences)
        
        # For high safety classes, require higher sentence match ratio
        min_required = 0.9 if safety_class in ("critical", "high") else 0.7
        
        if match_ratio >= min_required:
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed[:500],
                start_offset=best_match_start,
                end_offset=best_match_start + len(claimed),
                verification_status="verified",
                similarity_score=match_ratio,
                safety_class=safety_class,
                citation_format=citation_format,
            )
        
        return None
    
    def _try_fuzzy_match(
        self,
        claimed: str,
        source: str,
        source_path: str,
        article,
        citation_format: str,
        safety_class: str,
        threshold: float,
    ) -> Optional[Citation]:
        """Try fuzzy word-overlap match with threshold"""
        norm_claim = self._normalizer.normalize(claimed)
        norm_source = self._normalizer.normalize(source)
        
        similarity = self._calculate_similarity(norm_claim, norm_source)
        
        # Determine status based on similarity vs threshold
        if similarity >= threshold:
            status = "verified" if similarity >= 0.99 else "partial"
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed[:500],
                start_offset=0,
                end_offset=len(claimed),
                verification_status=status,
                similarity_score=similarity,
                safety_class=safety_class,
                citation_format=citation_format,
            )
        elif similarity >= 0.5:
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed[:500],
                start_offset=0,
                end_offset=len(claimed),
                verification_status="modified",
                similarity_score=similarity,
                safety_class=safety_class,
                citation_format=citation_format,
            )
        
        return None
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences, preserving abbreviations"""
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate word-level Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _detect_hallucinations(
        self,
        output: str,
        citations: List[Citation],
        safety_class: str,
    ) -> List[Dict[str, Any]]:
        """
        Detect potential hallucinations.
        
        Safety-class-aware: higher safety classes = stricter detection.
        """
        flags = []
        
        # Threshold for flagging
        threshold = self.threshold_config.get_threshold(safety_class)
        
        # Pattern 1: Specific numbers/specifications without citation
        # CRITICAL: Don't flag decimals as hallucination
        number_pattern = r'(\d+(?:\.\d+)?)\s*(%|ms|seconds?|minutes?|hours?|days?|years?|MB|GB|TB|GB/s|MHz|GHz|W|V|A|kB/s|m/s|kg|m²|ft|lbs)'
        for match in re.finditer(number_pattern, output):
            context_start = max(0, match.start() - 200)
            context_end = min(len(output), match.end() + 200)
            context = output[context_start:context_end]
            
            # Check for any citation format nearby
            has_citation = any([
                re.search(r'\[[^\]]+\]\([^)]+\)', context),  # Markdown link
                re.search(r'\[\[[^\]]+\]\]', context),        # Wikilink
                re.search(r'\[\d+\]', context),               # [1], [2]
                re.search(r'\([^)]*source:[^)]*\)', context, re.IGNORECASE),  # (source:)
            ])
            
            if not has_citation:
                flags.append({
                    "type": "unverified_specification",
                    "text": match.group(0),
                    "position": match.start(),
                    "message": "Specific measurement or specification without citation",
                })
        
        # Pattern 2: Definitive claims without hedging
        # Relaxed pattern - only flag substantial claims
        definitive_pattern = r'(?:^|\.\s)([A-Z][^.]{30,100}\.)'
        for match in re.finditer(definitive_pattern, output):
            sentence = match.group(1)
            
            # Skip if it contains any citation
            if re.search(r'\[[^\]]+\]', sentence):
                continue
            
            # Skip if it contains hedge words
            if re.search(r'\b(may|might|could|appears|seems|likely|possibly|approximately|about)\b', sentence, re.IGNORECASE):
                continue
            
            # Skip common non-claims
            skip_phrases = ['Table ', 'Figure ', 'Note that', 'As shown', 'As described']
            if any(s in sentence for s in skip_phrases):
                continue
            
            flags.append({
                "type": "uncited_claim",
                "text": sentence[:100],
                "position": match.start(),
                "message": "Definitive claim without citation",
            })
        
        # Pattern 3: Unverified citations from verification
        for cite in citations:
            if cite.verification_status in ("not_found", "modified"):
                flags.append({
                    "type": "unverified_citation",
                    "text": cite.quote[:100],
                    "source": cite.source_path,
                    "status": cite.verification_status,
                    "similarity": cite.similarity_score,
                    "message": f"Citation {cite.verification_status} (similarity: {cite.similarity_score:.0%})",
                })
        
        return flags
    
    def _calculate_score(
        self,
        citations: List[Citation],
        flags: List[Dict],
        threshold: float,
    ) -> float:
        """Calculate verification score"""
        if not citations and not flags:
            return 0.5  # Neutral
        
        if citations:
            verified = sum(1 for c in citations if c.verification_status == "verified")
            partial = sum(1 for c in citations if c.verification_status == "partial")
            modified = sum(1 for c in citations if c.verification_status == "modified")
            not_found = sum(1 for c in citations if c.verification_status == "not_found")
            
            # Weighted scoring
            citation_score = (
                verified * 1.0 +
                partial * 0.8 +
                modified * 0.4 +
                not_found * 0.0
            ) / len(citations)
        else:
            citation_score = 0.0
        
        # Penalty from hallucination flags
        flag_penalty = len(flags) * 0.1
        flag_penalty = min(flag_penalty, 0.4)
        
        return max(0.0, citation_score - flag_penalty)
    
    def _check_compliance(
        self,
        score: float,
        flags: List[Dict],
        threshold: float,
        safety_class: str,
    ) -> bool:
        """Check if output meets compliance requirements"""
        if not self.strict_mode:
            return score >= 0.6
        
        # High safety classes require verified citations
        if safety_class in ("critical", "high"):
            has_verified = any(c.verification_status == "verified" for c in self.citations if hasattr(self, 'citations'))
            has_citations = len(self.citations) > 0 if hasattr(self, 'citations') else False
            
            return (
                score >= threshold and
                has_verified and
                has_citations and
                len(flags) == 0
            )
        
        return score >= threshold and len(flags) == 0


# =============================================================================
# INTEGRATION & UTILITIES
# =============================================================================

def validate_query_result(result, quoter: DeterministicQuoter, safety_class: str = "unknown") -> ValidatedOutput:
    """
    Validate a QueryAgent result.
    
    Args:
        result: QueryAgent result with .answer attribute
        quoter: DeterministicQuoter instance
        safety_class: Safety classification for threshold
    """
    return quoter.validate(result.answer, safety_class=safety_class)


def generate_compliance_report(output: ValidatedOutput) -> str:
    """Generate a human-readable compliance report"""
    lines = [
        "# Citation Compliance Report",
        "",
        f"**Verification Score:** {output.verification_score:.0%}",
        f"**Status:** {'✅ Compliant' if output.is_compliant else '⚠️ Non-Compliant'}",
        "",
        f"**Safety Class:** {output.metadata.get('safety_class', 'unknown')}",
        f"**Threshold Used:** {output.metadata.get('threshold_used', 0.80):.0%}",
        "",
        "## Citations",
        "",
    ]
    
    for i, cite in enumerate(output.citations, 1):
        icon = "✅" if cite.verification_status == "verified" else "⚠️" if cite.verification_status == "partial" else "❌"
        lines.append(f"### {i}. {icon} {cite.source_title}")
        lines.append(f"- **Path:** `{cite.source_path}`")
        lines.append(f"- **Status:** {cite.verification_status}")
        lines.append(f"- **Similarity:** {cite.similarity_score:.0%}")
        lines.append(f"- **Format:** {cite.citation_format}")
        lines.append(f"- **Safety Class:** {cite.safety_class}")
        lines.append(f"- **Quote:** \"{cite.quote[:100]}...\"")
        lines.append("")
    
    if output.hallucination_flags:
        lines.append("## Hallucination Flags")
        lines.append("")
        for flag in output.hallucination_flags:
            lines.append(f"- **{flag['type']}:** {flag['message']}")
            lines.append(f"  - Text: \"{flag['text'][:80]}...\"")
            lines.append("")
    
    lines.append("---")
    lines.append(f"_Generated by Cortex Compliance Layer_")
    
    return "\n".join(lines)