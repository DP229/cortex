"""
NeuronMesh Agent - Core Agent Implementation

Inspired by patterns from:
- Claude Code (Anthropic) - Tool system, permission model
- Hermes Agent (Nous Research) - Self-improving, memory persistence
- AutoAgent (HKUDS) - Zero-code customization
- AutoGen (Microsoft) - Multi-agent orchestration
"""

import json
import time
import asyncio
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

from cortex.brain import Brain, ModelConfig
from cortex.memory import Memory
from cortex.tools import (
    ToolRegistry, ToolResult, create_default_tools
)

logger = logging.getLogger(__name__)


class AgentMode(Enum):
    """Agent execution modes"""
    LOCAL = "local"           # Run on local machine
    KNOWLEDGE = "knowledge"   # Knowledge base mode with wiki tools
    HYBRID = "hybrid"         # Local + knowledge base


class TurnState(Enum):
    """State of an agent turn"""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    RESPONDING = "responding"
    DONE = "done"
    ERROR = "error"


@dataclass
class ToolCall:
    """A tool call made by the agent"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[ToolResult] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def duration_ms(self) -> int:
        end = self.end_time or time.time()
        return int((end - self.start_time) * 1000)


@dataclass
class Turn:
    """A single turn in the conversation"""
    user_message: str
    assistant_message: str = ""
    state: TurnState = TurnState.THINKING
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    latency_ms: int = 0
    cost: float = 0.0
    tokens_used: int = 0
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "state": self.state.value,
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result.to_dict() if tc.result else None,
                    "duration_ms": tc.duration_ms,
                }
                for tc in self.tool_calls
            ],
            "model": self.model,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "tokens_used": self.tokens_used,
        }


@dataclass
class AgentConfig:
    """Configuration for an agent"""
    name: str = "agent"
    model: str = "llama3"
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = "You are a helpful AI assistant."
    mode: AgentMode = AgentMode.LOCAL
    max_turns: int = 10  # Max tool call loops
    timeout: int = 120  # Seconds
    tools_enabled: bool = True
    memory_enabled: bool = True
    stream_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "mode": self.mode.value,
            "max_turns": self.max_turns,
            "tools_enabled": self.tools_enabled,
            "memory_enabled": self.memory_enabled,
        }


@dataclass
class Message:
    """A message in the conversation"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from an agent"""
    content: str
    turns: List[Turn]
    final: bool = True
    error: Optional[str] = None
    latency_ms: int = 0
    cost: float = 0.0
    model: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "final": self.final,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "model": self.model,
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata,
        }


class Agent:
    """
    Core NeuronMesh agent with tool support and memory.
    
    Features (inspired by Claude Code + Hermes Agent):
    - Tool system with permission model
    - Streaming responses
    - Memory persistence
    - Self-improving via reflection
    
    Example:
        agent = Agent(model="llama3")
        memory = Memory()
        
        response = agent.run("Build me a web server")
        print(response.content)
    """
    
    def __init__(
        self,
        name: str = "agent",
        model: str = "llama3",
        brain: Optional[Brain] = None,
        memory: Optional[Memory] = None,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        self.name = name
        self.model = model
        self.brain = brain or Brain()
        self.memory = memory
        self.config = config or AgentConfig(name=name, model=model)
        
        # Tool registry
        self.tools = tools or create_default_tools(memory=memory)
        
        # Conversation history
        self.messages: List[Message] = []
        
        # Initialize system message
        self.messages.append(Message(
            role="system",
            content=self._build_system_prompt()
        ))
        
        # Turn history for this session
        self.turns: List[Turn] = []
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with tools"""
        prompt = self.config.system_prompt
        
        # Add tool descriptions if enabled
        if self.config.tools_enabled:
            tool_schemas = self.tools.get_schema()
            if tool_schemas:
                prompt += "\n\n## Available Tools\n"
                prompt += "You can use these tools to help complete tasks:\n\n"
                
                for schema in tool_schemas:
                    prompt += f"### {schema['name']}\n"
                    prompt += f"{schema['description']}\n"
                    prompt += f"Parameters: {json.dumps(schema['parameters'], indent=2)}\n\n"
        
        return prompt
    
    def run(
        self,
        prompt: str,
        memory: Optional[Memory] = None,
        max_turns: Optional[int] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Run the agent synchronously with tool execution.
        
        Handles both sync and async contexts properly.
        
        Args:
            prompt: User input
            memory: Optional memory override
            max_turns: Max tool call loops
            
        Returns:
            AgentResponse with content and metadata
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.get_event_loop().run_until_complete(
                self.run_async(prompt, memory, max_turns, **kwargs)
            )
        else:
            return asyncio.run(self.run_async(prompt, memory, max_turns, **kwargs))
    
    async def run_async(
        self,
        prompt: str,
        memory: Optional[Memory] = None,
        max_turns: Optional[int] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Run the agent asynchronously with tool execution.
        
        Args:
            prompt: User input
            memory: Optional memory override
            max_turns: Max tool call loops
            stream_callback: Optional callback for streaming
            
        Returns:
            AgentResponse with content and metadata
        """
        max_turns = max_turns or self.config.max_turns
        memory = memory or self.memory
        
        start_time = time.time()
        
        # Create turn
        turn = Turn(user_message=prompt, model=self.model)
        self.turns.append(turn)
        
        # Add user message
        self.messages.append(Message(role="user", content=prompt))
        
        try:
            # Build context from memory if enabled
            context = ""
            if memory and self.config.memory_enabled:
                relevant = memory.retrieve(prompt, limit=5)
                if relevant:
                    context = "\n\n## Relevant Memory:\n" + "\n".join([
                        f"- {entry.content}" 
                        for entry in relevant
                    ])
            
            # Main agent loop
            current_prompt = self._build_prompt(context)
            tool_loop_count = 0
            final_response = ""
            
            while tool_loop_count < max_turns:
                turn.state = TurnState.THINKING
                
                # Call LLM
                if self.config.stream_enabled and stream_callback:
                    # Streaming response
                    response_text = ""
                    async for chunk in self.brain.generate_stream(
                        prompt=current_prompt,
                        model=self.model,
                        config=ModelConfig(
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                        ),
                    ):
                        response_text += chunk
                        stream_callback(chunk)
                    full_response = response_text
                else:
                    full_response, usage = self.brain.generate(
                        prompt=current_prompt,
                        model=self.model,
                        config=ModelConfig(
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                        ),
                    )
                    if usage:
                        turn.cost = usage.get("cost", 0)
                        turn.tokens_used = usage.get("total_tokens", 0)
                
                turn.state = TurnState.RESPONDING
                
                # Parse tool calls from response
                tool_calls = self._parse_tool_calls(full_response)
                
                if not tool_calls:
                    # No tool calls, this is the final response
                    final_response = full_response
                    turn.assistant_message = final_response
                    break
                
                # Execute tool calls
                turn.state = TurnState.TOOL_CALL
                
                for tool_call_data in tool_calls:
                    tool_call = ToolCall(
                        id=tool_call_data.get("id", f"call_{len(turn.tool_calls)}"),
                        name=tool_call_data["name"],
                        arguments=tool_call_data.get("arguments", {}),
                    )
                    turn.tool_calls.append(tool_call)
                    
                    # Execute tool
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    tool_call.result = result
                    tool_call.end_time = time.time()
                
                # Add assistant response to context (separate from tool results)
                self.messages.append(Message(role="assistant", content=full_response))
                
                # Add tool results as separate messages for proper context
                for tool_call in turn.tool_calls:
                    if tool_call.result:
                        result_content = tool_call.result.output or ""
                        if tool_call.result.error:
                            result_content = f"Error: {tool_call.result.error}"
                        self.messages.append(Message(
                            role="tool",
                            content=f"[Tool: {tool_call.name}] {result_content}",
                        ))
                
                # Update prompt for next iteration
                current_prompt = self._build_prompt(context)
                tool_loop_count += 1
            
            # Store in memory if enabled
            if memory and self.config.memory_enabled:
                self._store_interactions(memory)
            
            turn.state = TurnState.DONE
            turn.latency_ms = int((time.time() - start_time) * 1000)
            
            return AgentResponse(
                content=final_response,
                turns=self.turns,
                final=True,
                latency_ms=turn.latency_ms,
                cost=turn.cost,
                model=self.model,
            )
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            turn.state = TurnState.ERROR
            return AgentResponse(
                content="",
                turns=self.turns,
                final=True,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response"""
        # Look for tool call patterns
        # Pattern: <tool_call>{"name": "bash", "arguments": {...}}</tool_call>
        
        tool_calls = []
        
        try:
            import re
            pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
            matches = re.findall(pattern, response, re.DOTALL)
            
            for i, match in enumerate(matches):
                try:
                    data = json.loads(match)
                    tool_calls.append({
                        "id": data.get("id", f"call_{i}"),
                        "name": data.get("name", data.get("function", {}).get("name")),
                        "arguments": data.get("arguments", data.get("function", {}).get("arguments", {})),
                    })
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        
        return tool_calls
    
    def _format_tool_results(self, tool_calls: List[ToolCall]) -> str:
        """Format tool results for LLM context"""
        if not tool_calls:
            return ""
        
        results = []
        for tc in tool_calls:
            if tc.result:
                result_text = str(tc.result.output) if tc.result.success else f"Error: {tc.result.error}"
                results.append(
                    f"<tool_result id='{tc.id}' tool='{tc.name}'>\n{result_text}\n</tool_result>"
                )
        
        return "\n\n" + "\n".join(results)
    
    def _build_prompt(self, context: str = "") -> str:
        """Build the full prompt with context"""
        messages_for_context = self.messages[-20:]  # Last 20 messages
        
        prompt_parts = []
        for msg in messages_for_context:
            if msg.role == "system":
                continue
            prefix = "User" if msg.role == "user" else "Assistant"
            prompt_parts.append(f"{prefix}: {msg.content}")
        
        if context:
            prompt_parts.append(f"\n{context}")
        
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    def _store_interactions(self, memory: Memory):
        """Store recent interactions in memory"""
        if len(self.messages) >= 2:
            user_msg = None
            for msg in reversed(self.messages[:-1]):
                if msg.role == "user":
                    user_msg = msg
                    break
            
            if user_msg:
                memory.add(
                    content=f"User preference: {user_msg.content}",
                    entry_type="preference",
                    importance=0.5,
                )
    
    def reset(self):
        """Reset conversation history (keep system message)"""
        self.messages = [self.messages[0]]  # Keep system message
        self.turns = []
    
    def get_history(self) -> List[Message]:
        """Get conversation history"""
        return self.messages.copy()
    
    def get_turns(self) -> List[Turn]:
        """Get turn history"""
        return self.turns.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state"""
        return {
            "name": self.name,
            "model": self.model,
            "config": self.config.to_dict(),
            "message_count": len(self.messages),
            "turn_count": len(self.turns),
            "tools_enabled": len(self.tools.list_tools()),
        }


# === Convenience Functions ===

def create_agent(
    name: str = "agent",
    model: str = "llama3",
    instructions: str = "You are a helpful assistant.",
    memory: bool = True,
    tools: bool = True,
) -> Agent:
    """
    Create a simple agent with default settings.
    
    Example:
        agent = create_agent("coder", model="codellama")
        response = agent.run("Write a hello world in Python")
    """
    config = AgentConfig(
        name=name,
        model=model,
        system_prompt=instructions,
        tools_enabled=tools,
        memory_enabled=memory,
    )
    return Agent(
        name=name,
        model=model,
        config=config,
        memory=Memory() if memory else None,
    )


def create_coder_agent(model: str = "codellama") -> Agent:
    """Create a coding-specialized agent"""
    return create_agent(
        name="coder",
        model=model,
        instructions="""You are an expert programmer. You help write, debug, and refactor code.
        
When writing code:
- Follow best practices and clean code principles
- Include comments explaining key sections
- Handle errors gracefully
- Write tests when appropriate

You have access to tools for reading, writing, and executing code.""",
    )


def create_researcher_agent(model: str = "llama3") -> Agent:
    """Create a research-specialized agent"""
    return create_agent(
        name="researcher",
        model=model,
        instructions="""You are a research assistant. You help find, analyze, and summarize information.

Your strengths:
- Web search and data gathering
- Critical analysis and synthesis
- Clear, structured summaries
- Citation and source tracking

Be thorough but concise. Always cite your sources.""",
    )


def create_kb_agent(
    model: str = "llama3",
    knowledgebase=None,
    memory=None,
) -> Agent:
    """Create an agent specialized for knowledge base operations"""
    from cortex.tools import ToolRegistry, create_default_tools
    from cortex.wiki_tools import create_wiki_tools

    kb = knowledgebase
    registry = ToolRegistry()

    # Add wiki tools first (higher priority)
    if kb:
        for tool in create_wiki_tools(knowledgebase=kb):
            registry.register(tool)
        # Add default tools selectively
        for tool in create_default_tools(memory=memory).list_tools():
            # Only add read-only tools for KB agent
            if tool.name in ("memory_search", "memory_store", "grep", "glob"):
                registry.register(create_default_tools(memory=memory).get(tool.name))
    else:
        registry = create_default_tools(memory=memory)

    return Agent(
        name="knowledge-agent",
        model=model,
        memory=memory,
        tools=registry,
        config=AgentConfig(
            name="knowledge-agent",
            model=model,
            system_prompt="""You are a knowledge base agent. You help users explore and maintain a wiki-based knowledge base.

Your capabilities:
- Read and search wiki articles
- Write and update articles
- Find connections between concepts
- Generate summaries and reports
- Maintain wiki health and consistency

When answering questions:
1. First check the wiki index for relevant articles
2. Read the most relevant articles
3. Synthesize a comprehensive answer
4. Write your answer as a new article if it adds value

Always cite your sources by linking to wiki articles.""",
        ),
    )
