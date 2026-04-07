"""
Cortex Deterministic Quoting - Hallucination Prevention Layer

Phase 1 Compliance Enhancement: Post-processing validation that ensures
LLM outputs are verifiable against source documents.

Key Features:
- Citation extraction and validation
- Exact text matching against source documents
- Hallucination detection and flagging
- Source attribution tracking

For safety-critical industries (IEC 62304, EN 50128), this layer
provides the traceability required for regulatory compliance.
"""

import re
import hashlib
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


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


class DeterministicQuoter:
    """
    Validates LLM outputs against source documents.
    
    This is the core compliance layer for safety-critical industries.
    Every claim in the output must be traceable to a source document.
    """
    
    def __init__(
        self,
        knowledgebase,
        strict_mode: bool = True,
        fuzzy_threshold: float = 0.85,
        context_window: int = 100,
    ):
        self.kb = knowledgebase
        self.strict_mode = strict_mode  # If True, reject outputs with unverified citations
        self.fuzzy_threshold = fuzzy_threshold
        self.context_window = context_window
    
    def validate(
        self,
        llm_output: str,
        max_sources: int = 10,
    ) -> ValidatedOutput:
        """
        Validate LLM output against knowledge base.
        
        1. Extract citations from output
        2. Verify each citation against source
        3. Flag hallucinations (unverified claims)
        4. Calculate compliance score
        """
        citations = []
        hallucination_flags = []
        
        # Extract potential citations
        potential_citations = self._extract_citations(llm_output)
        
        for source_ref, quote in potential_citations[:max_sources]:
            citation = self._verify_citation(source_ref, quote)
            if citation:
                citations.append(citation)
        
        # Check for hallucinations (claims without citations)
        hallucination_flags = self._detect_hallucinations(llm_output, citations)
        
        # Calculate verification score
        verification_score = self._calculate_score(citations, hallucination_flags)
        
        # Determine compliance
        is_compliant = (
            verification_score >= 0.8 and
            len(hallucination_flags) == 0
        ) if self.strict_mode else verification_score >= 0.6
        
        return ValidatedOutput(
            content=llm_output,
            citations=citations,
            hallucination_flags=hallucination_flags,
            verification_score=verification_score,
            is_compliant=is_compliant,
            metadata={
                "strict_mode": self.strict_mode,
                "fuzzy_threshold": self.fuzzy_threshold,
                "total_citations": len(citations),
                "verified_citations": sum(1 for c in citations if c.verification_status == "verified"),
            }
        )
    
    def _extract_citations(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract citations from LLM output.
        
        Supports multiple citation formats:
        - Markdown links: [text](path.md)
        - Wikilinks: [[path]]
        - Explicit quotes: "..." (Source: path)
        - Numbered references: [1], [2] with references section
        """
        citations = []
        
        # Pattern 1: Markdown links with context
        pattern1 = r'([^.!?]*?)\s*\[([^\]]+)\]\(([^)]+\.md)\)'
        for match in re.finditer(pattern1, text, re.DOTALL):
            context, link_text, source_path = match.groups()
            citations.append((source_path, context.strip()[:500] + " " + link_text))
        
        # Pattern 2: Wikilinks
        pattern2 = r'\[\[([^\]]+)\]\]'
        for match in re.finditer(pattern2, text):
            source_path = match.group(1)
            if not source_path.endswith('.md'):
                source_path += '.md'
            # Get surrounding context as quote
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            citations.append((source_path, text[start:end]))
        
        # Pattern 3: Explicit quotes with source attribution
        pattern3 = r'"([^"]+)"\s*\([^)]*source:\s*([^)]+)\)'
        for match in re.finditer(pattern3, text, re.IGNORECASE):
            quote, source_path = match.groups()
            citations.append((source_path.strip(), quote))
        
        # Pattern 4: References section
        ref_pattern = r'\[([0-9]+\])\s*([^[]*?)\s*\[([^\]]+)\]\(([^)]+\.md)\)'
        in_refs = False
        refs_section = re.search(r'##\s*(References|Sources)\s*\n(.*)', text, re.IGNORECASE | re.DOTALL)
        if refs_section:
            for match in re.finditer(ref_pattern, refs_section.group(2)):
                ref_num, description, link_text, source_path = match.groups()
                citations.append((source_path, description.strip()))
        
        return citations
    
    def _verify_citation(self, source_path: str, claimed_content: str) -> Optional[Citation]:
        """
        Verify a citation against the source document.
        
        Returns Citation with verification status.
        """
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
            )
        
        source_text = article.content
        
        # Normalize texts for comparison
        normalized_claim = self._normalize(claimed_content)
        normalized_source = self._normalize(source_text)
        
        # Try exact match first
        if normalized_claim in normalized_source:
            start_idx = normalized_source.find(normalized_claim)
            end_idx = start_idx + len(normalized_claim)
            
            # Get context from original text
            context_before = source_text[max(0, start_idx - self.context_window):start_idx]
            context_after = source_text[end_idx:min(len(source_text), end_idx + self.context_window)]
            
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed_content[:500],
                start_offset=start_idx,
                end_offset=end_idx,
                verification_status="verified",
                similarity_score=1.0,
                context_before=context_before,
                context_after=context_after,
            )
        
        # Try sentence-level matching
        claim_sentences = [s.strip() for s in normalized_claim.split('.') if len(s.strip()) > 20]
        matched_count = 0
        
        for sentence in claim_sentences:
            if sentence in normalized_source:
                matched_count += 1
        
        if claim_sentences and matched_count / len(claim_sentences) >= self.fuzzy_threshold:
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed_content[:500],
                start_offset=0,
                end_offset=len(claimed_content),
                verification_status="verified",
                similarity_score=matched_count / len(claim_sentences),
            )
        
        # Fuzzy match using word overlap
        similarity = self._calculate_similarity(normalized_claim, normalized_source)
        
        if similarity >= self.fuzzy_threshold:
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed_content[:500],
                start_offset=0,
                end_offset=len(claimed_content),
                verification_status="partial",
                similarity_score=similarity,
            )
        
        # Check if significant content is modified
        if similarity >= 0.5:
            return Citation(
                source_path=source_path,
                source_title=article.title,
                quote=claimed_content[:500],
                start_offset=0,
                end_offset=len(claimed_content),
                verification_status="modified",
                similarity_score=similarity,
            )
        
        return Citation(
            source_path=source_path,
            source_title=article.title,
            quote=claimed_content[:500],
            start_offset=0,
            end_offset=len(claimed_content),
            verification_status="not_found",
            similarity_score=similarity,
        )
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison"""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove punctuation for fuzzy matching
        text = re.sub(r'[^\w\s]', '', text)
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate word-level similarity between texts"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _detect_hallucinations(self, output: str, citations: List[Citation]) -> List[Dict[str, Any]]:
        """
        Detect potential hallucinations in output.
        
        Flags:
        - Uncited factual claims
        - Specific numbers/dates without sources
        - Direct quotes without attribution
        - Technical specifications without verification
        """
        flags = []
        
        # Pattern 1: Specific numbers without citation nearby
        number_pattern = r'(\d+(?:\.\d+)?)\s*(%|ms|seconds?|minutes?|hours?|days?|years?|MB|GB|TB|GB/s|MHz|GHz|W|V|A)'
        for match in re.finditer(number_pattern, output):
            # Check if there's a citation within 200 chars
            context_start = max(0, match.start() - 200)
            context_end = min(len(output), match.end() + 200)
            context = output[context_start:context_end]
            
            if not re.search(r'\[[^\]]+\]\([^)]+\.md\)', context):
                flags.append({
                    "type": "unverified_specification",
                    "text": match.group(0),
                    "position": match.start(),
                    "message": "Specific measurement without nearby citation",
                })
        
        # Pattern 2: Definitive claims without hedge words
        definitive_pattern = r'(^|\. )(The|This|It|There)\s+(is|are|was|will|must|should|requires)\s+[^.]*[^.]'
        for match in re.finditer(definitive_pattern, output, re.MULTILINE):
            sentence = match.group(0)
            
            # Skip if it contains a citation
            if re.search(r'\[[^\]]+\]\([^)]+\.md\)', sentence):
                continue
            
            # Skip if it contains hedge words
            if re.search(r'\b(may|might|could|appears|seems|likely|possibly)\b', sentence, re.IGNORECASE):
                continue
            
            # This might be an uncited claim
            if len(sentence) > 50:  # Only flag substantial claims
                flags.append({
                    "type": "uncited_claim",
                    "text": sentence[:100],
                    "position": match.start(),
                    "message": "Definitive claim without citation",
                })
        
        # Pattern 3: Check for unverified citations
        for cite in citations:
            if cite.verification_status in ("not_found", "modified"):
                flags.append({
                    "type": "unverified_citation",
                    "text": cite.quote[:100],
                    "source": cite.source_path,
                    "status": cite.verification_status,
                    "message": f"Citation {cite.verification_status} in source",
                })
        
        return flags
    
    def _calculate_score(self, citations: List[Citation], flags: List[Dict]) -> float:
        """Calculate overall verification score"""
        if not citations and not flags:
            return 0.5  # No citations to verify, neutral score
        
        # Base score from citation verification
        if citations:
            verified = sum(1 for c in citations if c.verification_status == "verified")
            partial = sum(1 for c in citations if c.verification_status == "partial")
            modified = sum(1 for c in citations if c.verification_status == "modified")
            not_found = sum(1 for c in citations if c.verification_status == "not_found")
            
            citation_score = (
                verified * 1.0 +
                partial * 0.7 +
                modified * 0.5 +
                not_found * 0.0
            ) / len(citations)
        else:
            citation_score = 0.0
        
        # Penalty from hallucination flags
        flag_penalty = len(flags) * 0.1
        flag_penalty = min(flag_penalty, 0.5)  # Cap at 0.5
        
        return max(0.0, citation_score - flag_penalty)


# === Integration with QueryAgent ===

def validate_query_result(result, quoter: DeterministicQuoter) -> ValidatedOutput:
    """
    Validate a QueryAgent result.
    
    Usage:
        quoter = DeterministicQuoter(kb)
        validated = validate_query_result(query_result, quoter)
        
        if not validated.is_compliant:
            print(f"Warning: Output failed validation ({validated.verification_score:.0%})")
    """
    return quoter.validate(result.answer)


# === Compliance Report Generation ===

def generate_compliance_report(output: ValidatedOutput) -> str:
    """Generate a human-readable compliance report"""
    lines = [
        "# Citation Compliance Report",
        "",
        f"**Verification Score:** {output.verification_score:.0%}",
        f"**Status:** {'✅ Compliant' if output.is_compliant else '⚠️ Non-Compliant'}",
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