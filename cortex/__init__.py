"""
Cortex - Local-First AI Knowledge Base Agent

Core package for building AI agents with intelligent memory,
wiki-based knowledge management, and local LLM support.
"""

__version__ = "0.1.0"

from cortex.agent import (
    Agent,
    AgentConfig,
    AgentMode,
    AgentResponse,
    Turn,
    ToolCall,
    Message,
    create_agent,
    create_coder_agent,
    create_researcher_agent,
)

from cortex.memory import Memory, MemoryEntry, MemoryType, MemoryImportance

from cortex.brain import (
    Brain,
    ModelConfig,
    ModelInfo,
    ModelProvider,
    ModelRegistry,
    create_brain,
)

from cortex.tools import (
    ToolRegistry,
    ToolDefinition,
    ToolResult,
    ToolCategory,
    BaseTool,
    create_default_tools,
    # Built-in tools
    BashTool,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    GrepTool,
    WebSearchTool,
    MemorySearchTool,
    MemoryStoreTool,
)

from cortex.orchestrator import (
    Orchestrator,
    OrchestratorResult,
    OrchestrationPattern,
    AgentSpec,
)

from cortex.knowledgebase import KnowledgeBase, Article

from cortex.wiki_tools import create_wiki_tools

from cortex.agent import create_kb_agent

from cortex.config import CortexConfig

from cortex.ingest import IngestPipeline, IngestResult

from cortex.query_agent import QueryAgent, QueryResult

from cortex.compile_wiki import WikiCompiler, CompileResult

from cortex.render import OutputRenderer

from cortex.wiki_health import WikiHealthChecker, HealthIssue

from cortex.finetune import FineTuneExporter

__all__ = [
    # Version
    "__version__",
    
    # Agent
    "Agent",
    "AgentConfig",
    "AgentMode",
    "AgentResponse",
    "Turn",
    "ToolCall",
    "Message",
    "create_agent",
    "create_coder_agent",
    "create_researcher_agent",
    "create_kb_agent",
    
    # Memory
    "Memory",
    "MemoryEntry",
    "MemoryType",
    
    # Brain
    "Brain",
    "ModelConfig",
    "ModelInfo",
    "ModelProvider",
    "ModelRegistry",
    "create_brain",
    
    # Tools
    "ToolRegistry",
    "ToolDefinition",
    "ToolResult",
    "ToolCategory",
    "BaseTool",
    "create_default_tools",
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "GlobTool",
    "GrepTool",
    "WebSearchTool",
    "MemorySearchTool",
    "MemoryStoreTool",
    
    # Knowledge Base
    "KnowledgeBase",
    "Article",
    "create_wiki_tools",
    
    # Ingest
    "IngestPipeline",
    "IngestResult",
    
    # Query
    "QueryAgent",
    "QueryResult",
    
    # Compile
    "WikiCompiler",
    "CompileResult",
    
    # Render
    "OutputRenderer",
    
    # Health
    "WikiHealthChecker",
    "HealthIssue",
    
    # Fine-tune
    "FineTuneExporter",
    
    # Config
    "CortexConfig",
    
    # Orchestrator
    "Orchestrator",
    "OrchestratorResult",
    "OrchestrationPattern",
    "AgentSpec",
]
