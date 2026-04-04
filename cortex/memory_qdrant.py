"""
NeuronMesh Memory Qdrant - Qdrant Vector DB Integration

Provides production-grade vector search using Qdrant.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result from Qdrant"""
    id: str
    score: float
    payload: Dict[str, Any]


class QdrantMemory:
    """
    Qdrant-backed memory for production vector search.
    
    Features:
    - Production-grade vector similarity search
    - Filtering by metadata
    - Sparse/dense hybrid search ready
    - Horizontal scaling
    
    Requires: pip install qdrant-client
    
    Example:
        memory = QdrantMemory()
        memory.add("User preference", entry_type="preference")
        
        results = memory.search("preferences", limit=5)
    """
    
    def __init__(
        self,
        url: str = None,
        api_key: str = None,
        collection_name: str = "cortex_memory",
        vector_size: int = 384,
        distance: str = "Cosine",
    ):
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY", "")
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance = distance
        self._client = None
        self._connect()
    
    def _connect(self):
        """Connect to Qdrant"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            self._client = QdrantClient(
                url=self.url,
                api_key=self.api_key if self.api_key else None,
            )
            
            # Create collection if not exists
            self._ensure_collection()
            
            logger.info(f"Connected to Qdrant at {self.url}")
        except ImportError:
            logger.warning("qdrant-client not installed. Run: pip install qdrant-client")
            self._client = None
        except Exception as e:
            logger.warning(f"Qdrant connection failed: {e}")
            self._client = None
    
    def _ensure_collection(self):
        """Ensure collection exists"""
        try:
            from qdrant_client.http import models
            
            collections = self._client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to create collection: {e}")
    
    def add(
        self,
        content: str,
        embedding: List[float],
        entry_type: str = "fact",
        memory_type: str = "ltm",
        importance: float = 0.5,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Add a memory with embedding to Qdrant.
        
        Returns the memory ID.
        """
        if not self._client:
            return None
        
        import uuid
        memory_id = str(uuid.uuid4())[:16]
        
        payload = {
            "content": content,
            "entry_type": entry_type,
            "memory_type": memory_type,
            "importance": importance,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        
        try:
            from qdrant_client.http import models
            
            self._client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=memory_id,
                        vector=embedding,
                        payload=payload,
                    )
                ],
            )
            
            return memory_id
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None
    
    def search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        entry_type: str = None,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search for similar memories.
        
        Returns list of SearchResult with id, score, and payload.
        """
        if not self._client:
            return []
        
        try:
            from qdrant_client.http import models
            
            # Build filter if entry_type specified
            filter_conditions = None
            if entry_type:
                filter_conditions = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="entry_type",
                            match=models.MatchValue(value=entry_type),
                        )
                    ]
                )
            
            results = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=filter_conditions,
                score_threshold=min_score,
            )
            
            return [
                SearchResult(
                    id=r.id,
                    score=r.score,
                    payload=r.payload,
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def retrieve(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID"""
        if not self._client:
            return None
        
        try:
            results = self._client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
            )
            
            if results:
                result = results[0]
                return {
                    "id": result.id,
                    **result.payload,
                }
            return None
        except Exception as e:
            logger.error(f"Retrieve failed: {e}")
            return None
    
    def delete(self, memory_id: str):
        """Delete a memory"""
        if not self._client:
            return
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )
        except Exception as e:
            logger.error(f"Delete failed: {e}")
    
    def count(self) -> int:
        """Count total memories"""
        if not self._client:
            return 0
        
        try:
            return self._client.count(
                collection_name=self.collection_name,
            ).count
        except Exception:
            return 0
    
    def clear(self):
        """Clear all memories"""
        if not self._client:
            return
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.SelectFilter(),
            )
        except Exception as e:
            logger.error(f"Clear failed: {e}")


def create_qdrant_memory(**kwargs) -> QdrantMemory:
    """Create Qdrant memory instance"""
    return QdrantMemory(**kwargs)
