"""
Example 4: Tool System & Claude Code-Style Execution

Demonstrates:
- Using tools with the agent
- Tool permission model
- Streaming responses
- Multiple specialized agents

Run:
    python examples/04_tools.py
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import (
    Agent,
    Memory,
    create_agent,
    create_coder_agent,
    ToolRegistry,
    create_default_tools,
)


def example_basic_tools():
    """Basic tool execution"""
    print("=" * 60)
    print("Example 1: Basic Tool Execution")
    print("=" * 60)
    
    # Create agent with default tools
    agent = create_agent(
        name="assistant",
        model="llama3",
        instructions="You are a helpful assistant with access to tools.",
        tools=True,
    )
    
    # Run with a simple task
    print("\n📝 Task: List Python files in the current directory")
    print("-" * 40)
    
    response = agent.run("List all .py files in this directory using the glob tool")
    
    print(f"\n🤖 Response:\n{response.content}")
    print(f"\n📊 Stats:")
    print(f"   Turns: {len(response.turns)}")
    print(f"   Tool calls: {len(response.turns[0].tool_calls) if response.turns else 0}")
    print(f"   Latency: {response.latency_ms}ms")


def example_coder_agent():
    """Coding specialized agent"""
    print("\n" + "=" * 60)
    print("Example 2: Coder Agent")
    print("=" * 60)
    
    # Create coder agent
    coder = create_coder_agent(model="codellama")
    
    print("\n📝 Task: Write a simple HTTP server in Python")
    print("-" * 40)
    
    response = coder.run(
        "Write a simple HTTP server in Python that handles GET requests "
        "and returns 'Hello, World!'"
    )
    
    print(f"\n🤖 Response:\n{response.content[:500]}...")
    print(f"\n📊 Stats:")
    print(f"   Turns: {len(response.turns)}")
    print(f"   Latency: {response.latency_ms}ms")


def example_with_memory():
    """Agent with memory and tools"""
    print("\n" + "=" * 60)
    print("Example 3: Agent with Memory & Tools")
    print("=" * 60)
    
    # Create memory
    memory = Memory()
    
    # Create agent with memory and tools
    agent = Agent(
        name="assistant",
        model="llama3",
        memory=memory,
    )
    
    # First interaction - set preference
    print("\n1️⃣ First interaction: Setting context")
    response = agent.run(
        "I prefer Python over JavaScript and I like clean, typed code"
    )
    print(f"   Agent: {response.content[:100]}...")
    
    # Second interaction - agent should remember
    print("\n2️⃣ Second interaction: Remembering context")
    response = agent.run(
        "What programming language do I prefer based on our conversation?"
    )
    print(f"   Agent: {response.content[:200]}...")
    
    # Check memory stats
    print("\n3️⃣ Memory statistics:")
    stats = memory.get_stats()
    print(f"   Total memories: {stats['total_memories']}")
    print(f"   Long-term: {stats['ltm_size']}")


def example_multi_turn():
    """Multi-turn conversation with tools"""
    print("\n" + "=" * 60)
    print("Example 4: Multi-Turn with Tool Loop")
    print("=" * 60)
    
    agent = create_agent(model="llama3")
    
    # Complex task that requires multiple tool calls
    print("\n📝 Task: Find the largest Python file and show its first 20 lines")
    print("-" * 40)
    
    response = agent.run(
        "Use the glob tool to find all Python files in this project, "
        "then use bash to find the largest one, and read its first 20 lines"
    )
    
    print(f"\n🤖 Response:\n{response.content}")
    print(f"\n📊 Turn details:")
    for i, turn in enumerate(response.turns):
        print(f"   Turn {i+1}:")
        print(f"     State: {turn.state.value}")
        print(f"     Tool calls: {len(turn.tool_calls)}")
        for tc in turn.tool_calls:
            print(f"       - {tc.name}: {tc.result.output if tc.result else 'pending'}")


def example_tool_registry():
    """Explore the tool registry"""
    print("\n" + "=" * 60)
    print("Example 5: Tool Registry")
    print("=" * 60)
    
    tools = create_default_tools()
    
    print("\n📦 Available Tools:")
    print("-" * 40)
    
    for tool in tools.list_tools():
        print(f"\n🔧 {tool.name}")
        print(f"   Category: {tool.category.value}")
        print(f"   Permission: {tool.permission_level}")
        print(f"   {tool.description[:60]}...")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          NeuronMesh - Tool System Examples                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  These examples demonstrate the Claude Code-inspired         ║
║  tool system with:                                          ║
║  • Bash, File, Search, Web tools                            ║
║  • Memory integration                                       ║
║  • Streaming responses                                      ║
║  • Multi-turn tool loops                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Run examples
    example_tool_registry()
    example_basic_tools()
    example_coder_agent()
    example_with_memory()
    example_multi_turn()
    
    print("\n✅ All examples completed!")


if __name__ == "__main__":
    main()
