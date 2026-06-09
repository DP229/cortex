"""
Semantic Search Module for Cortex

Provides vector-based semantic search over the Cortex knowledge base
without requiring a separate Qdrant instance. Uses sentence-transformers
for embedding generation and SQLite for storage.

This is a "SQLite-backed fallback" that works out of the box. For
production scale (>100k articles), switch to Qdrant via cortex/memory_qdrant.py.

Usage:
    from cortex.semantic_search import SemanticSearchEngine
    engine = SemanticSearchEngine()
    engine.index_all()                    # Build the index
    results = engine.search("RFID balise read failure", top_k=5)
"""

from __future__ import annotations

import json
import os
import sys
import structlog
from typing import List, Optional, Dict, Any
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from sqlalchemy import text

logger = structlog.get_logger()


class SemanticSearchEngine:
    """
    Lightweight semantic search over KB articles and requirements.

    - Embedding model: all-MiniLM-L6-v2 (384 dimensions, fast on CPU)
    - Storage: SQLite (BLOB column for vector bytes)
    - Similarity: cosine
    - Fallback: hash-based embeddings (no model needed)
    """

    MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIM = 384
    TABLE_NAME = "semantic_embeddings"

    def __init__(self, db_session_factory=None):
        self.model = None
        self._db_session_factory = db_session_factory
        self._try_load_model()

    def _try_load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.MODEL_NAME)
            logger.info("semantic_search_model_loaded", model=self.MODEL_NAME, dim=self.EMBEDDING_DIM)
        except Exception as e:
            logger.warning("semantic_search_model_unavailable", error=str(e))
            self.model = None

    def _embed_text(self, text: str) -> List[float]:
        if self.model is not None:
            vec = self.model.encode(text, convert_to_numpy=True).tolist()
            return vec
        # Fallback: deterministic hash-based pseudo-embedding
        import hashlib
        h = hashlib.sha512(text.encode("utf-8")).digest()
        # Repeat hash to fill 384 dims
        full = (h * ((self.EMBEDDING_DIM * 4) // len(h) + 1))[:self.EMBEDDING_DIM * 4]
        # Convert to float in [-1, 1]
        return [(b - 128) / 128.0 for b in full[:self.EMBEDDING_DIM * 4]][:self.EMBEDDING_DIM]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _ensure_table(self, session):
        """Ensure the embeddings table exists."""
        try:
            session.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                        id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        source_table TEXT NOT NULL,
                        text_hash TEXT NOT NULL,
                        text_content TEXT,
                        embedding BLOB NOT NULL,
                        model TEXT NOT NULL,
                        dim INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(source_type, source_id)
                    )
                    """
                )
            )
            session.commit()
        except Exception as e:
            logger.warning("ensure_table_error", error=str(e))
            session.rollback()

    def index_text(self, session, source_type: str, source_id: str, content: str):
        """Index a single text entity."""
        self._ensure_table(session)
        text_hash = hash(content)
        # Check if already indexed with same hash
        row = session.execute(
            text(f"SELECT text_hash FROM {self.TABLE_NAME} WHERE source_type = :st AND source_id = :sid"),
            {"st": source_type, "sid": str(source_id)}
        ).fetchone()
        if row and row[0] == str(text_hash):
            return  # Already up to date

        vec = self._embed_text(content)
        vec_blob = json.dumps(vec).encode("utf-8")

        if row:
            session.execute(
                text(
                    f"UPDATE {self.TABLE_NAME} SET text_hash=:th, text_content=:tc, embedding=:em, model=:m, dim=:d, created_at=:ca WHERE source_type=:st AND source_id=:sid"
                ),
                {"th": str(text_hash), "tc": content[:2000], "em": vec_blob, "m": self.MODEL_NAME, "d": self.EMBEDDING_DIM, "ca": datetime.utcnow().isoformat(), "st": source_type, "sid": str(source_id)}
            )
        else:
            session.execute(
                text(
                    f"INSERT INTO {self.TABLE_NAME} (id, source_type, source_id, source_table, text_hash, text_content, embedding, model, dim, created_at) VALUES (:id, :st, :sid, :tbl, :th, :tc, :em, :m, :d, :ca)"
                ),
                {"id": str(uuid4()), "st": source_type, "sid": str(source_id), "tbl": "", "th": str(text_hash), "tc": content[:2000], "em": vec_blob, "m": self.MODEL_NAME, "d": self.EMBEDDING_DIM, "ca": datetime.utcnow().isoformat()}
            )
        session.commit()

    def index_kb_articles(self, session) -> int:
        """Index all knowledge articles."""
        self._ensure_table(session)
        rows = session.execute(text("SELECT id, title, content, category FROM knowledge_articles")).fetchall()
        count = 0
        for r in rows:
            text_content = f"{r[1] or ''} {r[3] or ''} {r[2] or ''}"[:2000]
            self.index_text(session, "kb_article", r[0], text_content)
            count += 1
        return count

    def index_requirements(self, session) -> int:
        """Index all requirements."""
        self._ensure_table(session)
        rows = session.execute(
            text("SELECT id, requirement_id, title, description, category FROM requirements")
        ).fetchall()
        count = 0
        for r in rows:
            text_content = f"{r[1] or ''} {r[4] or ''} {r[2] or ''} {r[3] or ''}"[:2000]
            self.index_text(session, "requirement", r[0], text_content)
            count += 1
        return count

    def index_all(self, session) -> Dict[str, int]:
        """Index both KB articles and requirements."""
        return {
            "kb_articles": self.index_kb_articles(session),
            "requirements": self.index_requirements(session),
        }

    def search(self, session, query: str, top_k: int = 5, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search the index for entities semantically similar to the query."""
        self._ensure_table(session)
        if not query or not query.strip():
            return []
        query_vec = self._embed_text(query)
        if source_filter:
            rows = session.execute(
                text(f"SELECT id, source_type, source_id, text_content, embedding FROM {self.TABLE_NAME} WHERE source_type = :st"),
                {"st": source_filter}
            ).fetchall()
        else:
            rows = session.execute(
                text(f"SELECT id, source_type, source_id, text_content, embedding FROM {self.TABLE_NAME}")
            ).fetchall()
        results = []
        for r in rows:
            try:
                vec = json.loads(r[4].decode("utf-8"))
            except Exception:
                continue
            score = self._cosine_similarity(query_vec, vec)
            results.append({
                "id": r[0],
                "source_type": r[1],
                "source_id": r[2],
                "text_preview": (r[3] or "")[:200],
                "score": round(score, 4),
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def stats(self, session) -> Dict[str, Any]:
        """Return index statistics."""
        self._ensure_table(session)
        total = session.execute(text(f"SELECT COUNT(*) FROM {self.TABLE_NAME}")).fetchone()[0]
        by_type = session.execute(
            text(f"SELECT source_type, COUNT(*) FROM {self.TABLE_NAME} GROUP BY source_type")
        ).fetchall()
        return {
            "model": self.MODEL_NAME if self.model else "fallback-hash",
            "dim": self.EMBEDDING_DIM,
            "total_vectors": total,
            "by_type": {r[0]: r[1] for r in by_type},
        }
