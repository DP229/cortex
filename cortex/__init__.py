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

from cortex.memory import Memory, MemoryEntry, MemoryType

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

from cortex.deterministic_core import (
    ComplianceResult,
    compute_hash,
    commit as commit_hash,
    verify as verify_hash,
    ModuleVersion,
)

from cortex.tqk import (
    QualificationEngine,
    T2EvidencePackage,
    EvidenceCollector,
    SignedT2Evidence,
)

from cortex.rail_taxonomy import (
    EN50128Phase,
    TraceLinkType,
    DocumentKind,
    DataQualityRecord,
    DataQualityReport,
)

from cortex.rail_validation import (
    RailValidator,
    SignalTiming,
    ATPProfile,
    SILCompatibilityCheck,
)

from cortex.regression_guard import RegressionGuard

from cortex.ci_qualify import qualify as ci_qualify, generate_evidence as ci_evidence

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

    # T2 Deterministic Core
    "ComplianceResult",
    "compute_hash",
    "commit_hash",
    "verify_hash",
    "ModuleVersion",

    # T2 Qualification Kit
    "QualificationEngine",
    "T2EvidencePackage",
    "EvidenceCollector",
    "SignedT2Evidence",

    # Rail Taxonomy
    "EN50128Phase",
    "TraceLinkType",
    "DocumentKind",
    "DataQualityRecord",
    "DataQualityReport",

    # Rail Validation
    "RailValidator",
    "SignalTiming",
    "ATPProfile",
    "SILCompatibilityCheck",

    # T2 Regression Guard & CI
    "RegressionGuard",
    "ci_qualify",
    "ci_evidence",
]
