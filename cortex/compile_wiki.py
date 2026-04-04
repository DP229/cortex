"""
Cortex Wiki Compiler - LLM-powered wiki compilation

Takes raw documents and compiles them into a structured wiki:
1. Summarizes each document
2. Extracts key concepts
3. Creates/updates concept articles
4. Updates index and backlinks

Usage:
    compiler = WikiCompiler(knowledgebase, agent)
    result = compiler.compile_document(ingest_result)
"""

import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

from cortex.knowledgebase import KnowledgeBase
from cortex.ingest import IngestResult

logger = logging.getLogger(__name__)


@dataclass
class CompileResult:
    """Result of compiling a document"""
    source: str
    summary: Optional[str] = None
    concepts: List[str] = None
    concept_articles: List[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.concepts is None:
            self.concepts = []
        if self.concept_articles is None:
            self.concept_articles = []


class WikiCompiler:
    """
    Compiles raw documents into a structured wiki using LLM.
    """
    
    def __init__(
        self,
        knowledgebase: KnowledgeBase,
        agent,
    ):
        self.kb = knowledgebase
        self.agent = agent
    
    def compile_document(self, ingest_result: IngestResult) -> CompileResult:
        """
        Compile a single ingested document into the wiki.
        
        Steps:
        1. Read the raw document
        2. Generate a summary
        3. Extract key concepts
        4. Create/update concept articles
        5. Update backlinks
        """
        article = self.kb.get_article(ingest_result.wiki_path)
        if not article:
            return CompileResult(
                source=ingest_result.source_path,
                error=f"Article not found: {ingest_result.wiki_path}"
            )
        
        result = CompileResult(source=ingest_result.source_path)
        
        # Step 1: Generate summary
        summary_prompt = f"""Read this document and create a concise summary (3-5 paragraphs).

Document: {article.title}
Content:
{article.content[:4000]}

Provide:
1. A 3-5 paragraph summary
2. 3-5 key concepts mentioned
3. Suggested wiki category (concepts, tutorials, reference, etc.)

Format your response as:
## Summary
[summary text]

## Key Concepts
- concept1
- concept2

## Category
[category]"""
        
        try:
            summary_response = self.agent.run(summary_prompt)
            result.summary = summary_response.content
            
            # Step 2: Extract and create concept articles
            concepts = self._extract_concepts(summary_response.content)
            result.concepts = concepts
            
            for concept in concepts:
                concept_slug = concept.lower().replace(" ", "-")
                concept_path = f"concepts/{concept_slug}.md"
                
                existing = self.kb.get_article(concept_path)
                if existing:
                    # Update existing concept article
                    update_prompt = f"""Update this concept article to include information from a new source document.

Existing article: {existing.title}
{existing.content[:3000]}

New source: {article.title}
{article.content[:3000]}

Update the article to incorporate the new information. Keep it well-organized.
Add a reference link to the new source at the bottom."""
                    
                    update_response = self.agent.run(update_prompt)
                    self.kb.write_article(concept_path, update_response.content)
                    result.concept_articles.append(concept_path)
                else:
                    # Create new concept article
                    create_prompt = f"""Create a comprehensive wiki article about: {concept}

Source document: {article.title}
{article.content[:4000]}

Write a well-structured article with:
- Clear explanation of the concept
- Key points and details
- Examples if applicable
- References to related concepts (use markdown links)

Format as markdown."""
                    
                    create_response = self.agent.run(create_prompt)
                    self.kb.write_article(concept_path, create_response.content)
                    result.concept_articles.append(concept_path)
            
            # Step 3: Update backlinks and index
            self.kb.update_backlinks()
            self.kb.generate_index()
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Failed to compile document: {e}")
        
        return result
    
    def compile_all_new(self) -> List[CompileResult]:
        """Compile all unprocessed documents"""
        summaries = self.kb.list_articles(category="summaries")
        concepts = self.kb.list_articles(category="concepts")
        concept_titles = {c.title.lower() for c in concepts}
        
        results = []
        for summary in summaries:
            # Check if concepts have been extracted
            if not any(c.title.lower() in summary.content.lower() for c in concepts):
                result = self.compile_document(IngestResult(
                    source_path="",
                    wiki_path=summary.path,
                    title=summary.title,
                    word_count=summary.word_count,
                    content_type="text",
                ))
                results.append(result)
        
        return results
    
    def _extract_concepts(self, text: str) -> List[str]:
        """Extract concept names from text"""
        concepts = []
        in_concepts = False
        
        for line in text.split("\n"):
            if "key concepts" in line.lower():
                in_concepts = True
                continue
            if in_concepts:
                if line.startswith("- ") or line.startswith("* "):
                    concepts.append(line[2:].strip())
                elif line.strip() and not line.startswith("#"):
                    in_concepts = False
        
        return concepts
