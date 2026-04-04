"""
Example 6: Multi-Agent Orchestration

Demonstrates:
- Sequential pipeline
- Parallel execution
- Hierarchical (manager + sub-agents)
- Debate pattern

Inspired by AutoGen's group chat and CrewAI's crew patterns.

Run:
    python examples/06_orchestrator.py
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import (
    Orchestrator,
    OrchestrationPattern,
    AgentSpec,
)


def example_sequential():
    """Sequential pipeline: researcher → writer"""
    print("=" * 60)
    print("Example 1: Sequential Pipeline")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    # Define agents
    agents = [
        AgentSpec(
            name="researcher",
            role="researcher",
            instructions="""You are a research assistant. 
            Find key information about the topic given. 
            Provide factual, well-organized findings.""",
        ),
        AgentSpec(
            name="writer",
            role="writer",
            instructions="""You are a technical writer.
            Take the research findings and write a clear, concise summary.
            Use simple language. Be concise.""",
        ),
    ]
    
    print("\n📝 Task: Research and summarize AI trends")
    print("-" * 40)
    
    # Run sequential pipeline
    result = orchestrator.sync_sequential(
        agents=agents,
        initial_input="What are the main trends in AI for 2026?",
    )
    
    print(f"\n✅ Sequential pipeline complete!")
    print(f"   Pattern: {result.pattern.value}")
    print(f"   Duration: {result.duration_ms}ms")
    print(f"   Errors: {len(result.errors)}")
    
    print(f"\n📄 Research Output:")
    print(f"   {result.outputs.get('researcher', 'N/A')[:200]}...")
    
    print(f"\n📝 Writer Output:")
    print(f"   {result.outputs.get('writer', 'N/A')[:300]}...")


def example_parallel():
    """Parallel execution: multiple agents on same task"""
    print("\n" + "=" * 60)
    print("Example 2: Parallel Execution")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    # Define agents with different perspectives
    agents = [
        AgentSpec(
            name="proponent",
            role="pro",
            instructions="You are an advocate for renewable energy. Present strong arguments in favor.",
        ),
        AgentSpec(
            name="critic",
            role="con",
            instructions="You are a skeptic of renewable energy. Present challenges and concerns.",
        ),
        AgentSpec(
            name="analyst",
            role="analyst",
            instructions="You are a neutral analyst. Provide balanced, data-driven insights.",
        ),
    ]
    
    print("\n📝 Task: Evaluate renewable energy adoption")
    print("-" * 40)
    
    # Run parallel
    result = orchestrator.sync_parallel(
        agents=agents,
        input="Should countries invest heavily in renewable energy?",
    )
    
    print(f"\n✅ Parallel execution complete!")
    print(f"   Pattern: {result.pattern.value}")
    print(f"   Duration: {result.duration_ms}ms")
    print(f"   Agents ran: {len(result.agent_results)}")
    
    print(f"\n👤 Proponent View:")
    print(f"   {result.outputs.get('proponent', 'N/A')[:200]}...")
    
    print(f"\n👤 Critic View:")
    print(f"   {result.outputs.get('critic', 'N/A')[:200]}...")
    
    print(f"\n👤 Analyst View:")
    print(f"   {result.outputs.get('analyst', 'N/A')[:200]}...")


def example_hierarchical():
    """Hierarchical: manager delegates to sub-agents"""
    print("\n" + "=" * 60)
    print("Example 3: Hierarchical (Manager + Sub-agents)")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    # Define manager
    manager = AgentSpec(
        name="manager",
        role="manager",
        instructions="""You are a project manager.
        Break down complex tasks into subtasks for specialized agents.
        Coordinate and synthesize their work.""",
    )
    
    # Define sub-agents
    sub_agents = [
        AgentSpec(
            name="frontend",
            role="frontend_dev",
            instructions="You are a frontend developer. Build user interfaces.",
        ),
        AgentSpec(
            name="backend",
            role="backend_dev",
            instructions="You are a backend developer. Build APIs and data processing.",
        ),
        AgentSpec(
            name="security",
            role="security_engineer",
            instructions="You are a security engineer. Review for vulnerabilities.",
        ),
    ]
    
    print("\n📝 Task: Build a web application")
    print("-" * 40)
    
    # Run hierarchical
    async def run():
        return await orchestrator.hierarchical(
            manager=manager,
            sub_agents=sub_agents,
            input="Build a secure user authentication system",
        )
    
    result = asyncio.get_event_loop().run_until_complete(run())
    
    print(f"\n✅ Hierarchical orchestration complete!")
    print(f"   Pattern: {result.pattern.value}")
    print(f"   Duration: {result.duration_ms}ms")
    print(f"   Sub-agents: {len([k for k in result.outputs.keys() if k.startswith('subagent')])}")
    
    print(f"\n📋 Manager Analysis:")
    print(f"   {result.outputs.get('manager_analysis', 'N/A')[:200]}...")
    
    print(f"\n🔧 Frontend Output:")
    print(f"   {result.outputs.get('subagent_frontend', 'N/A')[:150]}...")
    
    print(f"\n⚙️ Backend Output:")
    print(f"   {result.outputs.get('subagent_backend', 'N/A')[:150]}...")
    
    print(f"\n🔒 Security Output:")
    print(f"   {result.outputs.get('subagent_security', 'N/A')[:150]}...")




def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Cortex - Multi-Agent Orchestration Examples           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  These examples demonstrate multi-agent orchestration:          ║
║  • Sequential pipeline (output → next input)                ║
║  • Parallel execution (same input, aggregate)              ║
║  • Hierarchical (manager delegates to sub-agents)           ║
║                                                              ║
║  Inspired by:                                                ║
║  • AutoGen's GroupChat                                    ║
║  • CrewAI's crew patterns                                  ║
║  • Hermes Agent's sub-agent spawning                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    example_sequential()
    example_parallel()
    example_hierarchical()
    
    print("\n✅ All orchestration examples completed!")


if __name__ == "__main__":
    main()
