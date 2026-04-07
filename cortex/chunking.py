"""
Cortex Contextual Chunking - Parent-Child Document Retrieval

Phase 1 Compliance Enhancement: Implements hierarchical document chunking
where small child chunks are indexed for precise retrieval while larger
parent sections are injected into LLM context.

Key Features:
- Parent document preservation (structural meaning intact)
- Child chunk indexing (precise semantic matching)
- Configurable chunk sizes with overlap
- Section-aware splitting (preserves headings/lists)
- Metadata preservation across chunk hierarchy

For safety-critical industries:
- Ensures technical specifications aren't split mid-sentence
- Preserves requirement context for verification
- Maintains document hierarchy for audit trails
"""

import re
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A document chunk at any level of the hierarchy"""
    chunk_id: str
    content: str
    chunk_type: str  # "parent", "section", "paragraph", "sentence"
    path: str
    title: str
    parent_id: Optional[str] = None
    level: int = 0  # 0=parent, 1=section, 2=paragraph
    start_char: int = 0
    end_char: int = 0
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = self._generate_id()
        if self.word_count == 0:
            self.word_count = len(self.content.split())
    
    def _generate_id(self) -> str:
        """Generate unique chunk ID from content hash"""
        content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:12]
        return f"chunk_{content_hash}"


@dataclass
class ChunkedDocument:
    """A document broken into hierarchical chunks"""
    path: str
    title: str
    parent_chunk: Chunk
    child_chunks: List[Chunk] = field(default_factory=list)
    section_chunks: List[Chunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    """
    Hierarchical document chunking with parent-child relationships.
    
    Strategy:
    1. Parse document into sections (by heading hierarchy)
    2. Create parent chunk (full document, for context)
    3. Create section chunks (for topic-level retrieval)
    4. Create paragraph chunks (for precise semantic matching)
    5. Index only child chunks, but retrieve parent context
    """
    
    def __init__(
        self,
        parent_max_tokens: int = 4000,  # Full doc context limit
        section_max_tokens: int = 1000,   # Section chunk limit
        chunk_max_tokens: int = 300,      # Small chunk for precise retrieval
        chunk_overlap: int = 50,          # Overlap between chunks
        preserve_headings: bool = True,
        preserve_lists: bool = True,
        min_chunk_size: int = 50,        # Minimum chunk in words
    ):
        self.parent_max_tokens = parent_max_tokens
        self.section_max_tokens = section_max_tokens
        self.chunk_max_tokens = chunk_max_tokens
        self.chunk_overlap = chunk_overlap
        self.preserve_headings = preserve_headings
        self.preserve_lists = preserve_lists
        self.min_chunk_size = min_chunk_size
    
    def chunk_document(self, path: str, content: str, title: str = "") -> ChunkedDocument:
        """
        Chunk a document into hierarchical structure.
        
        Returns:
            ChunkedDocument with parent and child chunks
        """
        if not title:
            title = self._extract_title(content, path)
        
        # Parse sections from content
        sections = self._parse_sections(content)
        
        # Create parent chunk (full document)
        parent_chunk = Chunk(
            chunk_id=f"parent_{hashlib.sha256(path.encode()).hexdigest()[:12]}",
            content=content[:self.parent_max_tokens * 4],  # Approximate chars
            chunk_type="parent",
            path=path,
            title=title,
            level=0,
            start_char=0,
            end_char=len(content),
            metadata={"total_sections": len(sections)}
        )
        
        section_chunks = []
        child_chunks = []
        
        current_pos = 0
        for i, section in enumerate(sections):
            section_start = content.find(section)
            section_end = section_start + len(section)
            
            # Create section chunk
            section_chunk = Chunk(
                chunk_id=f"section_{hashlib.sha256((path + str(i)).encode()).hexdigest()[:12]}",
                content=section[:self.section_max_tokens * 4],
                chunk_type="section",
                path=path,
                title=title,
                parent_id=parent_chunk.chunk_id,
                level=1,
                start_char=section_start,
                end_char=section_end,
                metadata={"section_index": i, "section_count": len(sections)}
            )
            section_chunks.append(section_chunk)
            
            # Split section into smaller chunks
            section_children = self._chunk_text(
                section,
                path,
                title,
                parent_chunk.chunk_id,
                section_chunk.chunk_id,
                level=2,
                max_tokens=self.chunk_max_tokens,
            )
            child_chunks.extend(section_children)
        
        return ChunkedDocument(
            path=path,
            title=title,
            parent_chunk=parent_chunk,
            child_chunks=child_chunks,
            section_chunks=section_chunks,
            metadata={
                "total_chunks": 1 + len(section_chunks) + len(child_chunks),
                "total_words": len(content.split()),
            }
        )
    
    def _parse_sections(self, content: str) -> List[str]:
        """
        Parse document into sections by heading hierarchy.
        
        Uses markdown heading pattern: # ## ### etc.
        """
        # Find all headings with their positions
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        headings = []
        
        for match in re.finditer(heading_pattern, content, re.MULTILINE):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            headings.append({
                'level': level,
                'text': heading_text,
                'start': match.start(),
                'end': match.end(),
            })
        
        if not headings:
            # No headings, treat entire content as one section
            return [content]
        
        sections = []
        
        for i, heading in enumerate(headings):
            # Determine section boundaries
            start = heading['start']
            
            # End is start of next heading (or end of content)
            if i + 1 < len(headings):
                end = headings[i + 1]['start']
            else:
                end = len(content)
            
            # Extract section content (from end of heading to next heading)
            section_content = content[start:end].strip()
            
            if section_content:
                sections.append(section_content)
        
        return sections
    
    def _chunk_text(
        self,
        text: str,
        path: str,
        title: str,
        parent_id: str,
        section_id: str,
        level: int,
        max_tokens: int,
    ) -> List[Chunk]:
        """
        Split text into chunks with overlap.
        
        Preserves sentence boundaries and paragraph structure.
        """
        chunks = []
        
        # Split into paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        current_start = 0
        
        for para in paragraphs:
            para_len = len(para.split())
            
            # If single paragraph exceeds max, split by sentences
            if para_len > max_tokens // 4:
                sentence_chunks = self._split_by_sentences(
                    para, path, title, parent_id, section_id, level, max_tokens
                )
                chunks.extend(sentence_chunks)
                continue
            
            # Check if adding this paragraph exceeds limit
            if current_chunk and (len(current_chunk.split()) + para_len) > max_tokens:
                # Save current chunk
                chunk = Chunk(
                    chunk_id=f"chunk_{hashlib.sha256((current_chunk + path).encode()).hexdigest()[:12]}",
                    content=current_chunk.strip(),
                    chunk_type="paragraph" if level == 2 else "sentence",
                    path=path,
                    title=title,
                    parent_id=parent_id,
                    level=level,
                    start_char=current_start,
                    end_char=current_start + len(current_chunk),
                    metadata={"section_id": section_id}
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + " " + para
                current_start = current_start + len(current_chunk) - len(overlap_text)
            else:
                current_chunk += "\n\n" + para
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunk = Chunk(
                chunk_id=f"chunk_{hashlib.sha256((current_chunk + path).encode()).hexdigest()[:12]}",
                content=current_chunk.strip(),
                chunk_type="paragraph" if level == 2 else "sentence",
                path=path,
                title=title,
                parent_id=parent_id,
                level=level,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                metadata={"section_id": section_id}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_by_sentences(
        self,
        text: str,
        path: str,
        title: str,
        parent_id: str,
        section_id: str,
        level: int,
        max_tokens: int,
    ) -> List[Chunk]:
        """Split long text by sentences"""
        # Simple sentence splitting
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        
        chunks = []
        current = ""
        
        for sentence in sentences:
            if len(current.split()) + len(sentence.split()) > max_tokens:
                if current:
                    chunk = Chunk(
                        chunk_id=f"chunk_{hashlib.sha256((current + path).encode()).hexdigest()[:12]}",
                        content=current.strip(),
                        chunk_type="sentence",
                        path=path,
                        title=title,
                        parent_id=parent_id,
                        level=level,
                        metadata={"section_id": section_id}
                    )
                    chunks.append(chunk)
                
                # If single sentence is too long, truncate it
                if len(sentence.split()) > max_tokens:
                    words = sentence.split()
                    while words:
                        chunk_text = " ".join(words[:max_tokens])
                        chunk = Chunk(
                            chunk_id=f"chunk_{hashlib.sha256((chunk_text + path).encode()).hexdigest()[:12]}",
                            content=chunk_text,
                            chunk_type="sentence",
                            path=path,
                            title=title,
                            parent_id=parent_id,
                            level=level,
                            metadata={"section_id": section_id, "truncated": True}
                        )
                        chunks.append(chunk)
                        words = words[max_tokens:]
                    
                    current = ""
                else:
                    current = sentence
            else:
                current += (" " if current else "") + sentence
        
        if current.strip():
            chunk = Chunk(
                chunk_id=f"chunk_{hashlib.sha256((current + path).encode()).hexdigest()[:12]}",
                content=current.strip(),
                chunk_type="sentence",
                path=path,
                title=title,
                parent_id=parent_id,
                level=level,
                metadata={"section_id": section_id}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """Get overlapping text for chunk continuity"""
        words = text.split()
        overlap_count = min(self.chunk_overlap, len(words) // 2)
        return " ".join(words[-overlap_count:]) if overlap_count > 0 else ""
    
    def _extract_title(self, content: str, path: str) -> str:
        """Extract title from first heading or filename"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # Fallback to filename
        return Path(path).stem.replace('-', ' ').replace('_', ' ').title()


class ChunkIndex:
    """
    Index for managing chunks and their parent-child relationships.
    
    Provides retrieval methods that return parent context along
    with matched child chunks.
    """
    
    def __init__(self):
        self.chunks: Dict[str, Chunk] = {}
        self.documents: Dict[str, ChunkedDocument] = {}
        self.path_to_parent: Dict[str, str] = {}  # path -> parent_chunk_id
        self.chunk_to_parent: Dict[str, str] = {}  # chunk_id -> parent_chunk_id
    
    def add_document(self, doc: ChunkedDocument) -> None:
        """Add a chunked document to the index"""
        self.documents[doc.path] = doc
        self.path_to_parent[doc.path] = doc.parent_chunk.chunk_id
        
        # Index all chunks
        self.chunks[doc.parent_chunk.chunk_id] = doc.parent_chunk
        
        for chunk in doc.section_chunks:
            self.chunks[chunk.chunk_id] = chunk
            self.chunk_to_parent[chunk.chunk_id] = doc.parent_chunk.chunk_id
        
        for chunk in doc.child_chunks:
            self.chunks[chunk.chunk_id] = chunk
            self.chunk_to_parent[chunk.chunk_id] = doc.parent_chunk.chunk_id
    
    def get_parent_context(self, chunk_id: str, max_context_chars: int = 4000) -> Tuple[str, Dict]:
        """
        Get parent document context for a chunk.
        
        Returns:
            Tuple of (parent_content, metadata)
        """
        parent_id = self.chunk_to_parent.get(chunk_id)
        if not parent_id or parent_id not in self.chunks:
            return "", {}
        
        parent = self.chunks[parent_id]
        return parent.content[:max_context_chars], parent.metadata
    
    def get_section_context(self, chunk_id: str) -> str:
        """Get section context for a chunk"""
        chunk = self.chunks.get(chunk_id)
        if not chunk:
            return ""
        
        section_id = chunk.metadata.get("section_id")
        if section_id and section_id in self.chunks:
            return self.chunks[section_id].content
        
        return chunk.content
    
    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Get a specific chunk by ID"""
        return self.chunks.get(chunk_id)
    
    def get_document(self, path: str) -> Optional[ChunkedDocument]:
        """Get a chunked document by path"""
        return self.documents.get(path)
    
    def remove_document(self, path: str) -> None:
        """Remove a document from the index"""
        if path not in self.documents:
            return
        
        doc = self.documents[path]
        
        # Remove all chunks
        for chunk in doc.child_chunks:
            self.chunks.pop(chunk.chunk_id, None)
            self.chunk_to_parent.pop(chunk.chunk_id, None)
        
        for chunk in doc.section_chunks:
            self.chunks.pop(chunk.chunk_id, None)
            self.chunk_to_parent.pop(chunk.chunk_id, None)
        
        self.chunks.pop(doc.parent_chunk.chunk_id, None)
        self.path_to_parent.pop(path, None)
        self.documents.pop(path, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
            "parent_chunks": sum(1 for c in self.chunks.values() if c.chunk_type == "parent"),
            "section_chunks": sum(1 for c in self.chunks.values() if c.chunk_type == "section"),
            "child_chunks": sum(1 for c in self.chunks.values() if c.chunk_type in ("paragraph", "sentence")),
        }


class ContextualRetriever:
    """
    Retrieval that always returns parent context along with matched chunks.
    
    This ensures that when a small chunk is matched, the full parent
    document is available for LLM context, preserving structural meaning.
    """
    
    def __init__(self, chunker: DocumentChunker, embedder):
        self.chunker = chunker
        self.embedder = embedder
        self.index = ChunkIndex()
    
    def index_document(self, path: str, content: str) -> ChunkedDocument:
        """Index a document for retrieval"""
        doc = self.chunker.chunk_document(path, content)
        self.index.add_document(doc)
        return doc
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_parent_context: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks with parent context.
        
        Args:
            query: Search query
            top_k: Number of results to return
            include_parent_context: If True, include full parent document
            
        Returns:
            List of dicts with chunk content and parent context
        """
        # Encode query
        query_embedding = self.embedder.encode(query)
        
        # Search child chunks
        results = []
        
        for chunk_id, chunk in self.index.chunks.items():
            if chunk.chunk_type == "parent":
                continue  # Don't match parents directly
            
            # Calculate similarity
            chunk_embedding = self.embedder.encode(chunk.content)
            similarity = self.embedder.similarity(query_embedding, chunk_embedding)
            
            results.append({
                "chunk": chunk,
                "score": similarity,
            })
        
        # Sort by score and get top k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]
        
        # Add parent context
        for result in results:
            if include_parent_context:
                parent_context, parent_meta = self.index.get_parent_context(result["chunk"].chunk_id)
                result["parent_context"] = parent_context
                result["parent_metadata"] = parent_meta
            else:
                result["parent_context"] = ""
                result["parent_metadata"] = {}
        
        return results
    
    def build_retrieval_context(
        self,
        query: str,
        max_context_tokens: int = 4000,
    ) -> str:
        """
        Build a retrieval context string for LLM consumption.
        
        Combines matched chunks with parent context, truncated
        to fit within token limit.
        """
        results = self.retrieve(query, top_k=5, include_parent_context=True)
        
        context_parts = []
        total_chars = 0
        
        for result in results:
            chunk = result["chunk"]
            parent = result["parent_context"]
            
            # Format this result
            formatted = f"[Source: {chunk.path}]\n"
            formatted += f"## {chunk.title}\n\n"
            formatted += f"{chunk.content}\n\n"
            
            # Add parent context if significantly different
            if parent and parent != chunk.content:
                formatted += f"### Full Context\n\n{parent[:2000]}...\n\n"
            
            formatted += "---\n\n"
            
            if total_chars + len(formatted) > max_context_tokens * 4:
                break
            
            context_parts.append(formatted)
            total_chars += len(formatted)
        
        return "".join(context_parts)


# === Utility Functions ===

def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars per token average)"""
    return len(text) // 4


def chunk_document_simple(
    content: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """
    Simple sliding window chunking (fallback).
    
    Use this when hierarchical chunking is not needed.
    """
    words = content.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) >= overlap:  # At least overlap words
            chunks.append(" ".join(chunk_words))
    
    return chunks