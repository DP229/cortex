"""
Cortex Hybrid Search - BM25 + Vector with Reciprocal Rank Fusion

Phase 1 Compliance Enhancement: Combines semantic vector search with
exact-token lexical search for deterministic retrieval.

Key Features:
- BM25 lexical ranking (industry standard for exact matching)
- Vector embedding search (semantic understanding)
- Reciprocal Rank Fusion (RRF) for unified ranking
- Configurable weight tuning
- Query expansion for better recall

For safety-critical industries, this ensures:
- No relevant documents are missed due to embedding blind spots
- Exact technical terms are matched precisely
- Results are reproducible and auditable
"""

import math
import re
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from collections import Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A unified search result"""
    path: str
    title: str
    chunk_text: str
    parent_text: str  # Full parent document
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rank_vector: int = 0
    rank_bm25: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BM25Indexer:
    """
    BM25 implementation for lexical search.
    
    BM25 (Best Matching 25) is a probabilistic ranking function
    used for information retrieval. It's the industry standard
    for keyword-based search.
    """
    
    def __init__(
        self,
        k1: float = 1.5,  # Term frequency saturation
        b: float = 0.75,  # Document length normalization
        avg_doc_len: float = 1000.0,
    ):
        self.k1 = k1
        self.b = b
        self.avg_doc_len = avg_doc_len
        self.doc_freq: Dict[str, int] = {}  # Term -> number of docs containing it
        self.doc_lengths: Dict[str, int] = {}  # Doc -> length
        self.doc_count = 0
        self.corpus: Dict[str, str] = {}  # Doc ID -> content
    
    def index(self, documents: Dict[str, Tuple[str, str]]) -> None:
        """
        Index documents for BM25 search.
        
        Args:
            documents: Dict of {doc_id: (title, content)}
        """
        self.corpus = {}
        self.doc_freq = Counter()
        self.doc_lengths = {}
        self.doc_count = len(documents)
        
        for doc_id, (title, content) in documents.items():
            self.corpus[doc_id] = content
            tokens = self._tokenize(content)
            self.doc_lengths[doc_id] = len(tokens)
            
            # Count document frequency
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freq[token] += 1
        
        # Calculate average document length
        if self.doc_lengths:
            self.avg_doc_len = sum(self.doc_lengths.values()) / len(self.doc_lengths)
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms"""
        # Lowercase
        text = text.lower()
        # Split on non-alphanumeric
        tokens = re.findall(r'\w+', text)
        # Remove very short tokens
        tokens = [t for t in tokens if len(t) >= 2]
        return tokens
    
    def search(self, query: str, limit: int = 20) -> List[Tuple[str, float]]:
        """
        Search using BM25.
        
        Returns list of (doc_id, score) tuples.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        scores: Dict[str, float] = {}
        
        for doc_id, content in self.corpus.items():
            doc_tokens = self._tokenize(content)
            doc_len = self.doc_lengths.get(doc_id, len(doc_tokens))
            doc_tf = Counter(doc_tokens)
            
            score = 0.0
            for q_token in query_tokens:
                if q_token not in self.doc_freq:
                    continue
                
                # Term frequency component
                tf = doc_tf.get(q_token, 0)
                tf_component = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                )
                
                # IDF component (inverse document frequency)
                df = self.doc_freq[q_token]
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
                
                score += tf_component * idf
            
            if score > 0:
                scores[doc_id] = score
        
        # Sort by score descending
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:limit]
    
    def get_scores(self, query: str) -> Dict[str, float]:
        """Get BM25 scores for all documents (for fusion)"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return {}
        
        scores: Dict[str, float] = {}
        
        for doc_id, content in self.corpus.items():
            doc_tokens = self._tokenize(content)
            doc_len = self.doc_lengths.get(doc_id, len(doc_tokens))
            doc_tf = Counter(doc_tokens)
            
            score = 0.0
            for q_token in query_tokens:
                if q_token not in self.doc_freq:
                    continue
                
                tf = doc_tf.get(q_token, 0)
                tf_component = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                )
                
                df = self.doc_freq[q_token]
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
                
                score += tf_component * idf
            
            scores[doc_id] = score
        
        return scores


class HybridSearch:
    """
    Hybrid search combining BM25 and vector search with RRF.
    
    Reciprocal Rank Fusion (RRF) formula:
    RRF_score(d) = Σ 1/(k + rank_i(d))
    
    where k is a constant (typically 60) and rank_i is the rank
    of document d in the i-th result set.
    """
    
    def __init__(
        self,
        knowledgebase,
        embedder,
        rrf_k: int = 60,  # RRF smoothing parameter
        vector_weight: float = 0.5,  # Weight for vector scores
        bm25_weight: float = 0.5,    # Weight for BM25 scores
    ):
        self.kb = knowledgebase
        self.embedder = embedder
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        
        self.bm25_indexer = BM25Indexer()
        self._indexed = False
    
    def ensure_index(self) -> None:
        """Build BM25 index from knowledge base"""
        if self._indexed:
            return
        
        articles = self.kb.list_articles()
        documents = {}
        
        for article in articles:
            documents[article.path] = (article.title, article.content)
        
        if documents:
            self.bm25_indexer.index(documents)
            self._indexed = True
            logger.info(f"Indexed {len(documents)} documents for BM25")
    
    def search(
        self,
        query: str,
        limit: int = 10,
        vector_limit: int = 50,
        bm25_limit: int = 50,
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining vector and BM25.
        
        Args:
            query: Search query
            limit: Maximum results to return
            vector_limit: Max results from vector search
            bm25_limit: Max results from BM25
            
        Returns:
            List of SearchResult sorted by RRF score
        """
        # Ensure BM25 index is built
        self.ensure_index()
        
        # Get BM25 results
        bm25_results = self.bm25_indexer.search(query, limit=bm25_limit)
        bm25_scores = self.bm25_indexer.get_scores(query)
        
        # Get vector search results
        vector_results = self._vector_search(query, limit=vector_limit)
        
        # Fuse results using RRF
        fused = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
        )
        
        # Build SearchResult objects
        search_results = []
        for path, combined_score, vec_score, bm_score, vec_rank, bm_rank in fused[:limit]:
            article = self.kb.get_article(path)
            if article:
                # Get parent context (full article for context injection)
                parent_text = article.content
                
                # Get best matching chunk
                chunk_text = self._get_relevant_chunk(article.content, query)
                
                search_results.append(SearchResult(
                    path=path,
                    title=article.title,
                    chunk_text=chunk_text,
                    parent_text=parent_text,
                    score=combined_score,
                    vector_score=vec_score,
                    bm25_score=bm_score,
                    rank_vector=vec_rank,
                    rank_bm25=bm_rank,
                    metadata={
                        "word_count": article.word_count,
                        "backlinks": len(article.backlinks),
                    }
                ))
        
        return search_results
    
    def _vector_search(self, query: str, limit: int) -> List[Tuple[str, float]]:
        """Perform vector search using embeddings"""
        try:
            query_embedding = self.embedder.encode(query)
            
            # Search in knowledge base memory
            results = self.kb.search(query, limit=limit)
            
            vector_results = []
            for article, score in results:
                vector_results.append((article.path, score))
            
            return vector_results
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[str, float]],
        bm25_results: List[Tuple[str, float]],
    ) -> List[Tuple[str, float, float, float, int, int]]:
        """
        Fuse results using Reciprocal Rank Fusion.
        
        Returns list of (doc_id, combined_score, vec_score, bm_score, vec_rank, bm_rank)
        """
        rrf_scores: Dict[str, Dict[str, Any]] = {}
        
        # Process vector results
        for rank, (doc_id, score) in enumerate(vector_results):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {"vector_score": 0.0, "bm25_score": 0.0, "vec_rank": 0, "bm_rank": 0}
            rrf_scores[doc_id]["vector_score"] = score
            rrf_scores[doc_id]["vec_rank"] = rank + 1
        
        # Process BM25 results
        for rank, (doc_id, score) in enumerate(bm25_results):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {"vector_score": 0.0, "bm25_score": 0.0, "vec_rank": 0, "bm_rank": 0}
            rrf_scores[doc_id]["bm25_score"] = score
            rrf_scores[doc_id]["bm_rank"] = rank + 1
        
        # Calculate RRF scores
        fused = []
        for doc_id, scores in rrf_scores.items():
            vec_rank = scores["vec_rank"]
            bm_rank = scores["bm_rank"]
            
            # RRF formula
            vec_rrf = 1.0 / (self.rrf_k + vec_rank) if vec_rank > 0 else 0.0
            bm_rrf = 1.0 / (self.rrf_k + bm_rank) if bm_rank > 0 else 0.0
            
            # Weighted combination
            combined = (self.vector_weight * vec_rrf) + (self.bm25_weight * bm_rrf)
            
            fused.append((
                doc_id,
                combined,
                scores["vector_score"],
                scores["bm25_score"],
                vec_rank,
                bm_rank,
            ))
        
        # Sort by combined score
        fused.sort(key=lambda x: x[1], reverse=True)
        
        return fused
    
    def _get_relevant_chunk(self, content: str, query: str) -> str:
        """Extract the most relevant chunk from content"""
        query_tokens = set(query.lower().split())
        
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        best_sentence = sentences[0] if sentences else content[:500]
        best_score = 0
        
        for sentence in sentences:
            sentence_tokens = set(sentence.lower().split())
            overlap = len(query_tokens & sentence_tokens)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence
        
        # Return the best sentence plus some context
        return best_sentence[:500]
    
    def reindex(self) -> None:
        """Rebuild the BM25 index"""
        self._indexed = False
        self.ensure_index()
    
    def update_weights(self, vector_weight: float, bm25_weight: float) -> None:
        """Update fusion weights"""
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        return {
            "indexed_docs": self.bm25_indexer.doc_count,
            "avg_doc_length": self.bm25_indexer.avg_doc_len,
            "unique_terms": len(self.bm25_indexer.doc_freq),
            "rrf_k": self.rrf_k,
            "vector_weight": self.vector_weight,
            "bm25_weight": self.bm25_weight,
        }


# === Query Expansion for Better Recall ===

class QueryExpander:
    """
    Expands queries to improve recall.
    
    For technical domains, query expansion helps capture:
    - Synonyms
    - Acronyms
    - Related technical terms
    """
    
    def __init__(self):
        # Common technical term expansions
        self.expansions = {
            "sw": "software",
            "hw": "hardware",
            "req": "requirement requirements",
            "spec": "specification specifications",
            "doc": "document documentation",
            "api": "application programming interface",
            "ui": "user interface",
            "ux": "user experience",
            "db": "database",
            "sql": "structured query language",
            "ml": "machine learning",
            "ai": "artificial intelligence",
            "dl": "deep learning",
            "nn": "neural network",
            "rf": "radio frequency",
            "emc": "electromagnetic compatibility",
            "emi": "electromagnetic interference",
            "safety": "safety-critical functional safety",
            "iec": "International Electrotechnical Commission",
            "iso": "International Organization for Standardization",
        }
    
    def expand(self, query: str) -> str:
        """Expand query with synonyms and related terms"""
        tokens = query.split()
        expanded_tokens = []
        
        for token in tokens:
            expanded_tokens.append(token)
            
            # Check for known expansions
            token_lower = token.lower().rstrip('s')  # Remove trailing 's' for matching
            if token_lower in self.expansions:
                expansion = self.expansions[token_lower]
                expanded_tokens.append(expansion)
        
        return " ".join(expanded_tokens)
    
    def expand_for_compliance(self, query: str) -> str:
        """Specialized expansion for compliance documents"""
        compliance_terms = [
            "requirement", "specification", "validation", "verification",
            "traceability", "qualification", "certification", "audit",
            "IEC", "62304", "EN", "50128", "ISO", "14971",
            "safety", "risk", "hazard", "mitigation",
        ]
        
        query_lower = query.lower()
        expanded = [query]
        
        # Add relevant compliance terms if not present
        for term in compliance_terms:
            if term.lower() not in query_lower and any(t in query_lower for t in term.lower().split()):
                expanded.append(term)
        
        return " ".join(expanded)


def create_hybrid_search(knowledgebase, embedder) -> HybridSearch:
    """Factory to create a hybrid search instance"""
    return HybridSearch(knowledgebase, embedder)