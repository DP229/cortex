"""
NeuronMesh Memory - Intelligent Memory Layer with RAG

Provides persistent, searchable memory for agents:
- Short-term memory (recent context)
- Long-term memory (vector RAG with embeddings)
- Structured memory (facts, preferences, skills)
- Cross-agent shared memory

Inspired by:
- Hermes Agent's Honcho dialectic user modeling
- AutoAgent's natural language memory
- Claude Code's memory system
"""

import os
import time
import json
import hashlib
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from contextlib import contextmanager
import logging

from cortex.embeddings import get_embedder

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory"""
    SHORT_TERM = "stm"           # Recent conversation (in-memory)
    LONG_TERM = "ltm"            # Vector stored memories (persistent)
    WORKING = "working"          # Current task context
    PROCEDURAL = "procedural"    # Skills and procedures
    EPISODIC = "episodic"        # Events and experiences
    SEMANTIC = "semantic"        # Facts and knowledge


class MemoryImportance(Enum):
    """Importance levels for memory consolidation"""
    TRIVIAL = 0.2
    LOW = 0.4
    NORMAL = 0.5
    HIGH = 0.7
    CRITICAL = 0.9


@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    content: str
    entry_type: str = "fact"  # "fact", "preference", "skill", "conversation", "event"
    memory_type: MemoryType = MemoryType.LONG_TERM
    importance: float = 0.5    # 0.0 - 1.0
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    decay_score: float = 1.0  # For memory decay
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Additional fields
    agent_id: Optional[str] = None  # Which agent created this
    session_id: Optional[str] = None  # Which session
    tags: List[str] = field(default_factory=list)  # For categorization
    
    def touch(self):
        """Update access time and count"""
        self.last_accessed = time.time()
        self.access_count += 1
        self.decay_score = min(1.0, self.decay_score + 0.1)  # Boost on access
    
    def decay(self, factor: float = 0.95):
        """Apply time-based decay to memory importance"""
        time_since_access = time.time() - self.last_accessed
        days = time_since_access / (24 * 60 * 60)  # Convert to days
        self.decay_score = max(0.1, self.decay_score * (factor ** days))
    
    def effective_importance(self) -> float:
        """Calculate importance considering access patterns"""
        return self.importance * self.decay_score * (1 + 0.1 * min(self.access_count, 10))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "entry_type": self.entry_type,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "decay_score": self.decay_score,
            "metadata": self.metadata,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            id=data["id"],
            content=data["content"],
            entry_type=data.get("entry_type", "fact"),
            memory_type=MemoryType(data.get("memory_type", "ltm")),
            importance=data.get("importance", 0.5),
            embedding=data.get("embedding"),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
            decay_score=data.get("decay_score", 1.0),
            metadata=data.get("metadata", {}),
            agent_id=data.get("agent_id"),
            session_id=data.get("session_id"),
            tags=data.get("tags", []),
        )


class VectorStore:
    """
    Vector store for embeddings with SQLite persistence.
    
    Uses simple cosine similarity for retrieval.
    Production could use Qdrant, Pinecone, or ChromaDB.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.expanduser("~/.cortex/memory/")
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.db_path = os.path.join(self.storage_path, "vectors.db")
        self._init_db()
        
        self._embedder = get_embedder()
        self._lock = threading.RLock()
    
    def _init_db(self):
        """Initialize SQLite database"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    entry_type TEXT,
                    memory_type TEXT,
                    importance REAL,
                    embedding BLOB,
                    created_at REAL,
                    last_accessed REAL,
                    access_count INTEGER,
                    decay_score REAL,
                    metadata TEXT,
                    agent_id TEXT,
                    session_id TEXT,
                    tags TEXT
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_type ON memories(entry_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_access_count ON memories(access_count)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get SQLite connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def add(self, entry: MemoryEntry):
        """Add an entry to the store"""
        with self._lock:
            with self._get_connection() as conn:
                # Generate embedding if not present
                if entry.embedding is None:
                    entry.embedding = self._embedder.encode(entry.content)[0]
                
                # Store embedding as JSON
                embedding_blob = json.dumps(entry.embedding)
                
                conn.execute("""
                    INSERT OR REPLACE INTO memories 
                    (id, content, entry_type, memory_type, importance, embedding,
                     created_at, last_accessed, access_count, decay_score, 
                     metadata, agent_id, session_id, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.id,
                    entry.content,
                    entry.entry_type,
                    entry.memory_type.value,
                    entry.importance,
                    embedding_blob,
                    entry.created_at,
                    entry.last_accessed,
                    entry.access_count,
                    entry.decay_score,
                    json.dumps(entry.metadata),
                    entry.agent_id,
                    entry.session_id,
                    json.dumps(entry.tags),
                ))
                conn.commit()
    
    def get(self, id: str) -> Optional[MemoryEntry]:
        """Get an entry by ID"""
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (id,)
                ).fetchone()
                
                if row:
                    return self._row_to_entry(row)
                return None
    
    def update_access(self, id: str):
        """Update access time and count"""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE memories 
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE id = ?
                """, (time.time(), id))
                conn.commit()
    
    def delete(self, id: str):
        """Delete an entry"""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM memories WHERE id = ?", (id,))
                conn.commit()
    
    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
        entry_types: Optional[List[str]] = None,
        min_importance: float = 0.0,
    ) -> List[tuple[MemoryEntry, float]]:
        """
        Search for similar memories using cosine similarity.
        
        Returns list of (entry, similarity_score) tuples sorted by relevance.
        """
        with self._lock:
            with self._get_connection() as conn:
                # Build query
                conditions = ["embedding IS NOT NULL"]
                params = []
                
                if memory_types:
                    placeholders = ",".join("?" * len(memory_types))
                    conditions.append(f"memory_type IN ({placeholders})")
                    params.extend([mt.value for mt in memory_types])
                
                if entry_types:
                    placeholders = ",".join("?" * len(entry_types))
                    conditions.append(f"entry_type IN ({placeholders})")
                    params.extend(entry_types)
                
                if min_importance > 0:
                    conditions.append("importance >= ?")
                    params.append(min_importance)
                
                where_clause = " AND ".join(conditions)
                
                rows = conn.execute(f"""
                    SELECT * FROM memories WHERE {where_clause}
                """, params).fetchall()
                
                # Calculate similarities
                results = []
                for row in rows:
                    entry = self._row_to_entry(row)
                    if entry.embedding:
                        similarity = self._cosine_similarity(query_embedding, entry.embedding)
                        results.append((entry, similarity))
                
                # Sort by similarity (descending)
                results.sort(key=lambda x: x[1], reverse=True)
                
                return results[:limit]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity"""
        if not a or not b:
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert SQLite row to MemoryEntry"""
        embedding = None
        if row["embedding"]:
            try:
                embedding = json.loads(row["embedding"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            entry_type=row["entry_type"],
            memory_type=MemoryType(row["memory_type"]),
            importance=row["importance"],
            embedding=embedding,
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"],
            decay_score=row["decay_score"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )
    
    def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories"""
        with self._get_connection() as conn:
            if memory_type:
                row = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                    (memory_type.value,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return row[0] if row else 0
    
    def clear(self, memory_type: Optional[MemoryType] = None):
        """Clear memories"""
        with self._lock:
            with self._get_connection() as conn:
                if memory_type:
                    conn.execute("DELETE FROM memories WHERE memory_type = ?",
                                (memory_type.value,))
                else:
                    conn.execute("DELETE FROM memories")
                conn.commit()
    
    def vacuum(self):
        """Optimize database"""
        with self._get_connection() as conn:
            conn.execute("VACUUM")


class Memory:
    """
    Intelligent memory for agents with RAG support.
    
    Features:
    - Automatic importance scoring
    - Memory consolidation (STM -> LTM)
    - Semantic search via embeddings
    - Memory decay over time
    - Configurable retention policies
    - Cross-agent shared memory
    
    Inspired by Hermes Agent's memory system.
    
    Example:
        memory = Memory()
        
        # Store something
        memory.add("User prefers dark mode", entry_type="preference")
        
        # Retrieve semantically
        results = memory.retrieve("What are user preferences?")
        for entry, score in results:
            print(f"{score:.2f}: {entry.content}")
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_stm_size: int = 100,
        consolidation_threshold: float = 0.6,
        decay_enabled: bool = True,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.storage_path = storage_path
        self.max_stm_size = max_stm_size
        self.consolidation_threshold = consolidation_threshold
        self.decay_enabled = decay_enabled
        self.agent_id = agent_id
        self.session_id = session_id or self._generate_session_id()
        
        # Initialize stores
        self.vector_store = VectorStore(storage_path)
        self._embedder = get_embedder()
        
        # Short-term memory (in-memory, fast access)
        self.stm: List[MemoryEntry] = []
        
        # Working memory (current task)
        self.working: List[MemoryEntry] = []
        
        # Load any existing session memories
        self._load_session_memories()
    
    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for a memory"""
        timestamp = str(time.time())
        return hashlib.md5(f"{content}{timestamp}".encode()).hexdigest()[:16]
    
    def _generate_session_id(self) -> str:
        """Generate a session ID"""
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    
    def add(
        self,
        content: str,
        entry_type: str = "fact",
        importance: Optional[float] = None,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
    ) -> MemoryEntry:
        """
        Add a new memory entry.
        
        Args:
            content: The memory content
            entry_type: Type of memory ("fact", "preference", "skill", "conversation", "event")
            importance: 0.0-1.0 importance score (auto-calculated if not provided)
            memory_type: Where to store the memory
            metadata: Additional metadata
            agent_id: Which agent is creating this
            tags: Tags for categorization
            embedding: Pre-computed embedding (optional)
            
        Returns:
            The created MemoryEntry
        """
        # Auto-calculate importance if not provided
        if importance is None:
            importance = self._calculate_importance(content, entry_type)
        
        # Generate embedding if not provided
        if embedding is None:
            try:
                embedding = self._embedder.encode(content)[0]
            except Exception as e:
                logger.warning(f"Embedding generation failed: {e}")
                embedding = None
        
        entry = MemoryEntry(
            id=self._generate_id(content),
            content=content,
            entry_type=entry_type,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding,
            metadata=metadata or {},
            agent_id=agent_id or self.agent_id,
            session_id=self.session_id,
            tags=tags or [],
        )
        
        if memory_type == MemoryType.SHORT_TERM:
            self.stm.append(entry)
            self._maybe_consolidate()
        elif memory_type == MemoryType.WORKING:
            self.working.append(entry)
        else:
            self.vector_store.add(entry)
        
        return entry
    
    def _calculate_importance(self, content: str, entry_type: str) -> float:
        """Calculate importance score for a memory"""
        score = 0.5  # Base score
        
        # Higher importance for certain types
        importance_boosts = {
            "preference": 0.2,
            "skill": 0.3,
            "fact": 0.1,
            "goal": 0.3,
            "constraint": 0.2,
        }
        score += importance_boosts.get(entry_type, 0)
        
        # Longer content might be more important
        if len(content) > 100:
            score += 0.1
        
        # Check for emphasis markers
        if any(marker in content.lower() for marker in ["important", "remember", "never", "always"]):
            score += 0.15
        
        return min(1.0, max(0.1, score))
    
    def _maybe_consolidate(self):
        """
        Consolidate short-term memories to long-term.
        Called when STM is getting full.
        """
        if len(self.stm) > self.max_stm_size:
            # Sort by importance
            self.stm.sort(key=lambda e: e.effective_importance(), reverse=True)
            
            # Move top memories to LTM
            to_move = self.stm[:self.max_stm_size // 2]
            for entry in to_move:
                entry.memory_type = MemoryType.LONG_TERM
                self.vector_store.add(entry)
            
            # Keep only recent half
            self.stm = self.stm[self.max_stm_size // 2:]
    
    def retrieve(
        self,
        query: str,
        limit: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
        entry_types: Optional[List[str]] = None,
        min_importance: float = 0.0,
        include_stm: bool = True,
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memories for a query using semantic search.
        
        Args:
            query: Query text
            limit: Maximum number of memories to return
            memory_types: Which memory types to search (None = all except WORKING)
            entry_types: Filter by entry types
            min_importance: Minimum importance threshold
            include_stm: Whether to include short-term memory
            
        Returns:
            List of relevant MemoryEntry objects, sorted by relevance
        """
        memory_types = memory_types or [MemoryType.LONG_TERM, MemoryType.SEMANTIC]
        
        # Generate query embedding
        try:
            query_embedding = self._embedder.encode(query)[0]
        except Exception as e:
            logger.warning(f"Query embedding failed: {e}")
            return []
        
        results = []
        
        # Search vector store (LTM)
        if MemoryType.LONG_TERM in memory_types or MemoryType.SEMANTIC in memory_types:
            vector_results = self.vector_store.search(
                query_embedding,
                limit=limit * 2,  # Get more, filter later
                memory_types=[MemoryType.LONG_TERM, MemoryType.SEMANTIC],
                entry_types=entry_types,
                min_importance=min_importance,
            )
            
            for entry, score in vector_results:
                entry.touch()
                entry.decay() if self.decay_enabled else None
                results.append(entry)
        
        # Search STM
        if include_stm and MemoryType.SHORT_TERM in memory_types:
            stm_scores = []
            for entry in self.stm:
                if entry.embedding:
                    score = self._embedder.similarity(query_embedding, entry.embedding)
                    stm_scores.append((entry, score))
            
            stm_scores.sort(key=lambda x: x[1], reverse=True)
            for entry, _ in stm_scores[:limit]:
                entry.touch()
                results.append(entry)
        
        # Search working memory
        if MemoryType.WORKING in memory_types:
            for entry in self.working:
                entry.touch()
                results.append(entry)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for entry in results:
            if entry.id not in seen:
                seen.add(entry.id)
                unique_results.append(entry)
        
        # Sort by effective importance
        unique_results.sort(key=lambda e: e.effective_importance(), reverse=True)
        
        return unique_results[:limit]
    
    def remember(
        self,
        query: str,
        context: Optional[str] = None,
        limit: int = 3,
    ) -> str:
        """
        Get formatted memory context for an agent.
        
        Args:
            query: What to remember about
            context: Additional context to help retrieval
            limit: Number of memories to retrieve
            
        Returns:
            Formatted string of relevant memories
        """
        search_query = query
        if context:
            search_query = f"{context} {query}"
        
        results = self.retrieve(search_query, limit=limit)
        
        if not results:
            return ""
        
        parts = ["## Relevant Memories:\n"]
        for i, entry in enumerate(results, 1):
            importance_label = "⭐" * int(entry.importance * 5)
            parts.append(f"{i}. {entry.content} {importance_label}")
        
        return "\n".join(parts)
    
    def forget(self, id: str):
        """Remove a memory by ID"""
        self.vector_store.delete(id)
        self.stm = [e for e in self.stm if e.id != id]
        self.working = [e for e in self.working if e.id != id]
    
    def clear(
        self,
        memory_type: Optional[MemoryType] = None,
        older_than_days: Optional[float] = None,
    ):
        """Clear memories"""
        if memory_type is None and older_than_days is None:
            # Clear everything
            self.stm.clear()
            self.working.clear()
            self.vector_store.clear()
        elif older_than_days:
            # Clear old memories
            time.time() - (older_than_days * 24 * 60 * 60)
            with self._get_connection():
                # This would need to be implemented
                pass
        else:
            # Clear specific type
            if memory_type == MemoryType.SHORT_TERM:
                self.stm.clear()
            elif memory_type == MemoryType.WORKING:
                self.working.clear()
            else:
                self.vector_store.clear(memory_type)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "stm_size": len(self.stm),
            "working_size": len(self.working),
            "ltm_size": self.vector_store.count(MemoryType.LONG_TERM),
            "semantic_size": self.vector_store.count(MemoryType.SEMANTIC),
            "total_memories": self.vector_store.count(),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
        }
    
    def _load_session_memories(self):
        """Load memories from current session"""
        # In a full implementation, this would load recent STM memories
        pass
    
    def export(self) -> List[Dict[str, Any]]:
        """Export all memories as list of dicts"""
        memories = []
        
        # Add LTM
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM memories").fetchall()
            for row in rows:
                if row["embedding"]:
                    try:
                        json.loads(row["embedding"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                memories.append({
                    "content": row["content"],
                    "entry_type": row["entry_type"],
                    "memory_type": row["memory_type"],
                    "importance": row["importance"],
                    "created_at": row["created_at"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                })
        
        return memories
    
    def _get_connection(self):
        """Get connection to vector store"""
        return self.vector_store._get_connection()
    
    def vacuum(self):
        """Optimize memory storage"""
        self.vector_store.vacuum()
