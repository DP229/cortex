# NeuronMesh Quick Start Guide

Get up and running with NeuronMesh in 5 minutes.

## Installation

```bash
# Clone the repository
git clone https://github.com/dp229/cortex.git
cd cortex

# Install
pip install -e .

# Or install with all dependencies
pip install -e ".[dev]"
```

## Prerequisites

NeuronMesh works with multiple LLM providers. Choose one:

### Option 1: Ollama (Recommended - Free & Local)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Start Ollama server
ollama serve
```

### Option 2: OpenAI API

```bash
export OPENAI_API_KEY=your_api_key_here
```

### Option 3: Anthropic API

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Quick Examples

### 1. Create Your First Agent

```python
from cortex import Agent, Memory

# Create memory for persistence
memory = Memory()

# Create agent
agent = Agent(model="llama3", memory=memory)

# Run
response = agent.run("Hello, remember that I like coffee")
print(response.content)

# Later - agent remembers
response = agent.run("What did I say I like?")
print(response.content)  # "You like coffee!"
```

### 2. Use Tools

```python
from cortex import create_coder_agent

# Create coding agent
coder = create_coder_agent(model="codellama")

# Agent can now use tools
response = coder.run("List all Python files in this directory")
print(response.content)
```

### 3. Multi-Agent Orchestration

```python
from cortex import Orchestrator, AgentSpec

orchestrator = Orchestrator()

# Define agents
agents = [
    AgentSpec("researcher", "researcher", "Research the topic thoroughly."),
    AgentSpec("writer", "writer", "Write a clear summary."),
]

# Run pipeline
result = orchestrator.sync_sequential(agents, "What is AI?")

print(result.outputs["researcher"])
print(result.outputs["writer"])
```

### 4. CLI Usage

```bash
# Run agent
cortex agent run "What is Python?"

# Interactive chat
cortex agent chat

# List models
cortex model list

# Memory operations
cortex memory add "Important fact" --type fact --importance 0.8
cortex memory search "fact"
```

## Examples

See the `examples/` directory for more:

| Example | Description |
|---------|-------------|
| `00_welcome.py` | Feature showcase |
| `01_quickstart.py` | Basic agent + memory |
| `02_multi_agent.py` | Multiple agents |
| `04_tools.py` | Tool system demo |
| `05_memory_rag.py` | Memory with RAG |
| `06_orchestrator.py` | Multi-agent orchestration |

Run an example:
```bash
python examples/00_welcome.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Cortex                                 │
│                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌─────────┐           │
│  │  Agent  │◄──►│ KnowledgeBase│◄──►│  Brain  │           │
│  │         │    │   (Wiki)     │    │ (LLMs)  │           │
│  └────┬────┘    └──────────────┘    └────┬────┘           │
│       │                                   │                │
│       └──────────┬────────────────────────┘                │
│                  │                                         │
│          ┌──────┴──────┐                                 │
│          │ Orchestrator │  Sequential, Parallel           │
│          └─────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────────┐
│                       Cortex                                 │
│                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌─────────┐           │
│  │  Agent  │◄──►│ KnowledgeBase│◄──►│  Brain  │           │
│  │         │    │   (Wiki)     │    │ (LLMs)  │           │
│  └────┬────┘    └──────────────┘    └────┬────┘           │
│       │                                   │                │
│       └──────────┬────────────────────────┘                │
│                  │                                         │
│          ┌──────┴──────┐                                 │
│          │ Orchestrator │  Sequential, Parallel           │
│          └─────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

- Read the [API Reference](API.md)
- Explore [Examples](examples/)
- Check out the [12-Week Plan](PLAN.md)
- Join the community

## Troubleshooting

### "Ollama not available"

Start Ollama:
```bash
ollama serve
```

### "Model not found"

Pull the model:
```bash
ollama pull llama3
```

### Import errors

Reinstall:
```bash
pip install -e .
```
