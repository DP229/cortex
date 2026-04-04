"""
Cortex Query Agent - Answer questions against the knowledge base

The main interaction mode: user asks a question, agent researches it
against the wiki and synthesizes a comprehensive answer.

Usage:
    query_agent = QueryAgent(agent, knowledgebase)
    result = query_agent.ask("What are the tradeoffs between consensus algorithms?")
"""

import re
import time
from typing import Optional, List
from dataclasses import dataclass
import logging

from cortex.knowledgebase import KnowledgeBase

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result from a knowledge base query"""
    question: str
    answer: str
    sources: List[str]
    output_path: Optional[str] = None
    latency_ms: int = 0


class QueryAgent:
    """
    Agent that answers questions by researching the knowledge base.
    """
    
    def __init__(
        self,
        agent,
        knowledgebase: KnowledgeBase,
    ):
        self.agent = agent
        self.kb = knowledgebase
    
    def ask(self, question: str, write_output: bool = True) -> QueryResult:
        """
        Ask a question against the knowledge base.
        
        The agent will:
        1. Check the wiki index for relevant topics
        2. Search for relevant articles
        3. Read the most relevant articles
        4. Synthesize a comprehensive answer
        5. Optionally write the answer as a new article
        """
        start_time = time.time()
        sources = []
        
        # Step 1: Ensure index exists
        index = self.kb.get_article("index.md")
        if not index:
            self.kb.generate_index()
            index = self.kb.get_article("index.md")
        
        # Step 2: Search for relevant articles
        search_results = self.kb.search(question, limit=10)
        
        if not search_results:
            return QueryResult(
                question=question,
                answer="I couldn't find any relevant articles in the knowledge base. Try ingesting some documents first with `cortex ingest <path>`.",
                sources=[],
                latency_ms=int((time.time() - start_time) * 1000),
            )
        
        # Step 3: Build context from relevant articles
        context_parts = []
        for article, score in search_results[:5]:
            sources.append(article.path)
            context_parts.append(
                f"## {article.title}\n"
                f"Source: {article.path}\n\n"
                f"{article.content[:3000]}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Step 4: Synthesize answer
        query_prompt = f"""Answer the following question based on the provided knowledge base articles.

Question: {question}

Knowledge Base Articles:
{context}

Instructions:
1. Provide a comprehensive, well-structured answer
2. Cite sources using markdown links (e.g., [Article Title](path/to/article.md))
3. If information is missing, note what's not covered
4. Suggest related topics to explore
5. Format as markdown

Your answer:"""
        
        response = self.agent.run(query_prompt)
        
        # Step 5: Write output
        output_path = None
        if write_output and response.content:
            slug = re.sub(r'[^\w\s-]', '', question.lower())[:50]
            slug = slug.replace(" ", "-").replace("--", "-")
            output_path = f"outputs/{slug}.md"
            
            output_content = f"# {question}\n\n"
            output_content += f"_Generated: {time.strftime('%Y-%m-%d %H:%M')}_\n\n"
            output_content += f"_Sources: {', '.join(sources)}_\n\n"
            output_content += "---\n\n"
            output_content += response.content
            
            self.kb.write_article(output_path, output_content)
        
        return QueryResult(
            question=question,
            answer=response.content,
            sources=sources,
            output_path=output_path,
            latency_ms=int((time.time() - start_time) * 1000),
        )
