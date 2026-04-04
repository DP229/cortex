"""
NeuronMesh Embeddings - Vector Embedding Generation

Provides embedding generation for memory RAG using:
- Sentence-transformers (primary)
- OpenAI embeddings (fallback)
- Simple hash-based (last resort)

No numpy required - uses JSON serialization for storage.
"""

import os
import json
import hashlib
from typing import List, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    embedding: List[float]
    model: str
    dimension: int
    tokens: Optional[int] = None


def vector_to_blob(vector: List[float]) -> str:
    """Convert vector to storable format (JSON)"""
    return json.dumps(vector)


def blob_to_vector(blob: str) -> Optional[List[float]]:
    """Convert stored blob back to vector"""
    if not blob:
        return None
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return None


class Embedder:
    """
    Unified embedding generation.
    
    Supports:
    - Sentence-transformers (local, free)
    - OpenAI embeddings (API)
    - Simple hash fallback
    """
    
    def __init__(
        self,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        
        # Determine device
        if device:
            self.device = device
        else:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        
        self._model = None
        self._dimension = 384  # Default for MiniLM
    
    def _load_sentence_transformers(self):
        """Load sentence-transformers model"""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Loaded sentence-transformers: {self.model_name}, dim={self._dimension}")
        except ImportError:
            logger.warning("sentence-transformers not installed. Using fallback embeddings.")
            self._model = None
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> List[List[float]]:
        """
        Generate embeddings for text(s).
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for encoding
            normalize: Whether to L2-normalize embeddings
            
        Returns:
            List of embedding vectors
        """
        if isinstance(texts, str):
            texts = [texts]
        
        # Try sentence-transformers first
        try:
            self._load_sentence_transformers()
            if self._model is not None:
                embeddings = self._model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=normalize,
                    show_progress_bar=False,
                )
                return embeddings.tolist()
        except Exception as e:
            logger.warning(f"sentence-transformers failed: {e}")
        
        # Try OpenAI embeddings
        if self.api_key:
            try:
                return self._openai_embeddings(texts)
            except Exception as e:
                logger.warning(f"OpenAI embeddings failed: {e}")
        
        # Fallback to simple embeddings
        return [self._simple_embedding(text) for text in texts]
    
    def _openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            model = "text-embedding-3-small"
            
            response = client.embeddings.create(
                model=model,
                input=texts,
            )
            
            return [item.embedding for item in response.data]
        except ImportError:
            raise Exception("OpenAI SDK not installed")
        except Exception as e:
            raise Exception(f"OpenAI embeddings failed: {e}")
    
    def _simple_embedding(self, text: str) -> List[float]:
        """
        Generate a simple embedding using word frequency.
        Not semantic, but provides consistent dimensionality.
        """
        words = text.lower().split()
        embedding = [0.0] * self._dimension
        
        for i, word in enumerate(words):
            word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = word_hash % self._dimension
            embedding[idx] += 1.0 / (i + 1)
        
        # Normalize
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        dot = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def dimension(self) -> int:
        """Get embedding dimension"""
        return self._dimension


# === Global embedder instance ===

_global_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    """Get global embedder instance"""
    global _global_embedder
    if _global_embedder is None:
        model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        _global_embedder = Embedder(model=model)
    return _global_embedder


def encode(texts: Union[str, List[str]]) -> List[List[float]]:
    """Quick encoding using global embedder"""
    return get_embedder().encode(texts)


def similarity(e1: List[float], e2: List[float]) -> float:
    """Quick similarity calculation"""
    return get_embedder().similarity(e1, e2)
