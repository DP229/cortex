"""
Cortex Wiki Tools - Knowledge base specific tools

Provides tools for the agent to interact with the wiki:
- Read articles
- Write/update articles
- Search articles
- Read the wiki index
- Find backlinks
- List articles by category
"""

from typing import Optional
from cortex.tools import BaseTool, ToolDefinition, ToolResult, ToolCategory


class WikiReadTool(BaseTool):
    """Read a wiki article"""
    definition = ToolDefinition(
        name="wiki_read",
        description="Read a wiki article from the knowledge base. Use path relative to wiki root.",
        category=ToolCategory.SEARCH,
        parameters={
            "path": {
                "type": "string",
                "description": "Path to article (e.g., 'concepts/transformers.md')",
                "required": True,
            },
        },
        returns="Full markdown content of the article",
        permission_level="auto",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        article = self.kb.get_article(path)
        if not article:
            return ToolResult(success=False, error=f"Article not found: {path}")
        
        return ToolResult(
            success=True,
            output=article.content,
            metadata={"title": article.title, "word_count": article.word_count},
        )


class WikiWriteTool(BaseTool):
    """Write/update a wiki article"""
    definition = ToolDefinition(
        name="wiki_write",
        description="Write or update a wiki article. Creates the article if it doesn't exist.",
        category=ToolCategory.FILE,
        parameters={
            "path": {
                "type": "string", 
                "description": "Path for article (e.g., 'concepts/ml-basics.md')",
                "required": True,
            },
            "content": {
                "type": "string",
                "description": "Full markdown content for the article",
                "required": True,
            },
        },
        returns="Confirmation with article path and word count",
        permission_level="user_confirm",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        article = self.kb.write_article(path, content)
        return ToolResult(
            success=True,
            output=f"Written: {article.path} ({article.word_count} words)",
            metadata={"path": article.path, "word_count": article.word_count},
        )


class WikiSearchTool(BaseTool):
    """Search wiki articles"""
    definition = ToolDefinition(
        name="wiki_search",
        description="Search wiki articles by semantic similarity. Returns relevant articles.",
        category=ToolCategory.SEARCH,
        parameters={
            "query": {
                "type": "string",
                "description": "Search query",
                "required": True,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results (default: 5)",
            },
        },
        returns="List of relevant articles with content snippets",
        permission_level="auto",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, query: str, limit: int = 5, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        results = self.kb.search(query, limit=limit)
        
        if not results:
            return ToolResult(success=True, output="No relevant articles found.")
        
        output_parts = []
        for article, score in results:
            snippet = article.content[:500] + ("..." if len(article.content) > 500 else "")
            output_parts.append(
                f"## {article.title} (relevance: {score:.2f})\n"
                f"Path: {article.path}\n"
                f"Words: {article.word_count:,}\n\n"
                f"{snippet}"
            )
        
        return ToolResult(
            success=True,
            output="\n\n---\n\n".join(output_parts),
            metadata={"count": len(results)},
        )


class WikiIndexTool(BaseTool):
    """Read the wiki index"""
    definition = ToolDefinition(
        name="wiki_index",
        description="Read the auto-generated wiki index showing all articles and categories.",
        category=ToolCategory.SEARCH,
        parameters={},
        returns="Full wiki index with all articles organized by category",
        permission_level="auto",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        index = self.kb.get_article("index.md")
        if not index:
            # Generate it
            index_content = self.kb.generate_index()
            return ToolResult(success=True, output=index_content)
        
        return ToolResult(success=True, output=index.content)


class WikiBacklinkTool(BaseTool):
    """Find backlinks to an article"""
    definition = ToolDefinition(
        name="wiki_backlinks",
        description="Find all articles that link to a specific article.",
        category=ToolCategory.SEARCH,
        parameters={
            "path": {
                "type": "string",
                "description": "Path to the article",
                "required": True,
            },
        },
        returns="List of articles linking to the specified article",
        permission_level="auto",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        backlinks = self.kb.get_backlinks(path)
        
        if not backlinks:
            return ToolResult(
                success=True,
                output=f"No articles link to {path}",
                metadata={"count": 0},
            )
        
        output = f"Articles linking to {path}:\n\n"
        for link in backlinks:
            article = self.kb.get_article(link)
            title = article.title if article else link
            output += f"- [{title}]({link})\n"
        
        return ToolResult(
            success=True,
            output=output,
            metadata={"count": len(backlinks)},
        )


class WikiListTool(BaseTool):
    """List articles by category"""
    definition = ToolDefinition(
        name="wiki_list",
        description="List wiki articles, optionally filtered by category.",
        category=ToolCategory.SEARCH,
        parameters={
            "category": {
                "type": "string",
                "description": "Category to filter by (e.g., 'concepts', 'summaries')",
            },
        },
        returns="List of articles with titles and paths",
        permission_level="auto",
    )
    
    def __init__(self, knowledgebase=None, **kwargs):
        super().__init__(**kwargs)
        self.kb = knowledgebase
    
    async def execute(self, category: Optional[str] = None, **kwargs) -> ToolResult:
        if not self.kb:
            return ToolResult(success=False, error="Knowledge base not configured")
        
        articles = self.kb.list_articles(category=category)
        
        if not articles:
            return ToolResult(success=True, output="No articles found.")
        
        output = f"Found {len(articles)} articles:\n\n"
        for article in articles:
            output += f"- [{article.title}]({article.path}) ({article.word_count:,} words)\n"
        
        return ToolResult(success=True, output=output)


def create_wiki_tools(knowledgebase=None) -> list:
    """Create all wiki tools"""
    return [
        WikiReadTool(knowledgebase=knowledgebase),
        WikiWriteTool(knowledgebase=knowledgebase),
        WikiSearchTool(knowledgebase=knowledgebase),
        WikiIndexTool(knowledgebase=knowledgebase),
        WikiBacklinkTool(knowledgebase=knowledgebase),
        WikiListTool(knowledgebase=knowledgebase),
    ]
