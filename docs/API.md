# NeuronMesh API Reference

Complete API documentation for NeuronMesh.

## Agent

### Agent

```python
from cortex import Agent, Memory

agent = Agent(
    name: str = "agent",           # Agent name
    model: str = "llama3",         # Model to use
    brain: Brain = None,            # LLM interface (optional)
    memory: Memory = None,          # Memory instance (optional)
    config: AgentConfig = None,    # Configuration (optional)
    tools: ToolRegistry = None,     # Tool registry (optional)
)
```

#### Methods

**`run(prompt: str, memory: Memory = None, max_turns: int = None) -> AgentResponse`**

Run the agent synchronously.

```python
response = agent.run("What is Python?")
print(response.content)
```

**`run_async(prompt: str, memory: Memory = None, stream_callback: Callable = None) -> AgentResponse`**

Run the agent asynchronously.

```python
response = await agent.run_async("Write code")
```

**`reset()`**

Reset conversation history.

```python
agent.reset()
```

#### AgentResponse

```python
@dataclass
class AgentResponse:
    content: str              # Response text
    turns: List[Turn]         # Turn history
    final: bool               # Is this final?
    error: Optional[str]      # Error message
    latency_ms: int          # Latency in ms
    cost: float              # Cost in credits
    model: str               # Model used
```

### Convenience Functions

```python
# General agent
agent = create_agent(model="llama3")

# Coder agent
coder = create_coder_agent(model="codellama")

# Researcher agent
researcher = create_researcher_agent(model="llama3")
```

---

## Memory

### Memory

```python
from cortex import Memory, MemoryType

memory = Memory(
    storage_path: str = None,      # Path for persistence
    max_stm_size: int = 100,       # Max short-term memories
    consolidation_threshold: float = 0.6,  # When to consolidate
    decay_enabled: bool = True,     # Enable memory decay
    agent_id: str = None,          # Agent identifier
    session_id: str = None,        # Session identifier
)
```

#### Methods

**`add(content: str, entry_type: str = "fact", importance: float = 0.5, memory_type: MemoryType = MemoryType.LONG_TERM, metadata: dict = None) -> MemoryEntry`**

Add a memory.

```python
memory.add(
    "User prefers dark mode",
    entry_type="preference",
    importance=0.8,
    tags=["ui", "preference"]
)
```

**`retrieve(query: str, limit: int = 5, memory_types: List[MemoryType] = None) -> List[MemoryEntry]`**

Retrieve relevant memories.

```python
results = memory.retrieve("What are user preferences?", limit=5)
for entry in results:
    print(entry.content)
```

**`remember(query: str, context: str = None, limit: int = 3) -> str`**

Get formatted memory context.

```python
context = memory.remember("What is the user working on?")
```

**`forget(id: str)`**

Remove a memory.

**`clear(memory_type: MemoryType = None)`**

Clear memories.

**`get_stats() -> dict`**

Get memory statistics.

```python
stats = memory.get_stats()
print(stats)
# {'stm_size': 10, 'working_size': 2, 'ltm_size': 50, ...}
```

### MemoryType

```python
from cortex import MemoryType

MemoryType.SHORT_TERM    # Recent conversation
MemoryType.LONG_TERM     # Persistent memories
MemoryType.WORKING       # Current task
MemoryType.SEMANTIC      # Facts and knowledge
MemoryType.PROCEDURAL    # Skills
MemoryType.EPISODIC      # Events
```

### MemoryEntry

```python
@dataclass
class MemoryEntry:
    id: str
    content: str
    entry_type: str       # "fact", "preference", "skill", etc.
    memory_type: MemoryType
    importance: float     # 0.0 - 1.0
    embedding: List[float]
    created_at: float
    last_accessed: float
    access_count: int
    metadata: dict
```

---

## Brain (LLM Interface)

### Brain

```python
from cortex import Brain, ModelConfig, ModelProvider

brain = Brain(
    registry: ModelRegistry = None,   # Model registry
    default_model: str = "llama3",    # Default model
    api_key: str = None,              # API key
)
```

#### Methods

**`generate(prompt: str, model: str = None, config: ModelConfig = None) -> tuple[str, dict]`**

Generate text.

```python
text, usage = brain.generate(
    "Hello",
    model="llama3",
    config=ModelConfig(temperature=0.7)
)
```

**`generate_stream(prompt: str, model: str = None) -> AsyncIterator[str]`**

Stream text generation.

```python
async for chunk in brain.generate_stream("Write a story"):
    print(chunk, end="")
```

**`get_stats() -> dict`**

Get usage statistics.

### ModelConfig

```python
@dataclass
class ModelConfig:
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    stop: List[str] = None
    stream: bool = False
```

### ModelRegistry

```python
registry = brain.registry

# List all models
models = registry.list()

# List free models
free_models = registry.list_free()

# Get model info
model = registry.get("llama3")

# Select best model
model = registry.select(task="chat", prefer_free=True)
```

### ModelProvider

```python
from cortex import ModelProvider

ModelProvider.OPENAI      # OpenAI models
ModelProvider.ANTHROPIC   # Claude models
ModelProvider.OLLAMA       # Local Ollama
ModelProvider.GROQ         # Groq models
ModelProvider.OPENROUTER   # OpenRouter
```

---

## Tools

### ToolRegistry

```python
from cortex import ToolRegistry, create_default_tools

# Use default tools
registry = create_default_tools()

# Or create empty
registry = ToolRegistry()
```

#### Methods

**`register(tool: BaseTool)`**

Register a tool.

**`get(name: str) -> BaseTool`**

Get a tool by name.

**`list_tools() -> List[ToolDefinition]`**

List all tools.

**`get_schema() -> List[dict]`**

Get OpenAI function schemas.

**`execute(name: str, parameters: dict) -> ToolResult`**

Execute a tool.

### Built-in Tools

```python
from cortex import (
    BashTool,       # Execute shell commands
    ReadFileTool,   # Read files
    WriteFileTool,  # Write files
    GlobTool,       # Find files
    GrepTool,      # Search in files
    WebSearchTool,  # Web search
    MemorySearchTool,  # Search memory
    MemoryStoreTool,   # Store memory
)
```

---

## Orchestrator

### Orchestrator

```python
from cortex import Orchestrator, AgentSpec, OrchestrationPattern

orchestrator = Orchestrator(
    memory: Memory = None,
    default_model: str = "llama3",
)
```

#### Patterns

**Sequential**

```python
agents = [
    AgentSpec("researcher", "researcher", "Research the topic."),
    AgentSpec("writer", "writer", "Write a summary."),
]

result = orchestrator.sync_sequential(agents, "AI trends")
print(result.outputs["researcher"])
print(result.outputs["writer"])
```

**Parallel**

```python
agents = [
    AgentSpec("analyst1", "analyst", "Analyze from perspective A."),
    AgentSpec("analyst2", "analyst", "Analyze from perspective B."),
]

result = orchestrator.sync_parallel(agents, "Should we invest in AI?")
```

**Hierarchical**

```python
manager = AgentSpec("manager", "manager", "Coordinate the team.")
sub_agents = [
    AgentSpec("frontend", "dev", "Build UI."),
    AgentSpec("backend", "dev", "Build API."),
]

result = await orchestrator.hierarchical(manager, sub_agents, "Build an app")
```

### AgentSpec

```python
@dataclass
class AgentSpec:
    name: str
    role: str
    instructions: str
    model: str = "llama3"
    tools_enabled: bool = True
    memory_enabled: bool = True
```

---

## Configuration

### CLI Configuration

```bash
# Set default model
cortex config set model gpt-4

# Enable verbose output
cortex --verbose agent run "Hello"

# JSON output
cortex --json model list
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
OPENPOOL_URL=http://localhost:8080
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## Error Handling

```python
from cortex import Agent

try:
    agent = Agent(model="nonexistent-model")
    response = agent.run("Hello")
except Exception as e:
    print(f"Error: {e}")
```
