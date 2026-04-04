"""
Example 0: Welcome to Cortex

This example showcases the core features of Cortex:
- Agent with memory
- Tool system
- Multiple LLM providers
- Local-first knowledge base

Run:
    python examples/00_welcome.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import (
    Agent,
    Memory,
    Brain,
    ModelRegistry,
    create_agent,
    create_coder_agent,
)


def welcome():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ███╗   ███╗███████╗███████╗████████╗ ██████╗██╗      ██╗ ║
║     ████╗ ████║██╔════╝██╔════╝╚══██╔══╝██╔════╝██║      ██║ ║
║     ██╔████╔██║█████╗  █████╗     ██║   ██║     ██║      ██║ ║
║     ██║╚██╔╝██║██╔══╝  ██╔══╝     ██║   ██║     ██║      ██║ ║
║     ██║ ╚═╝ ██║███████╗███████╗   ██║   ╚██████╗███████╗██║ ║
║     ╚═╝     ╚═╝╚══════╝╚══════╝   ╚═╝    ╚═════╝╚══════╝╚═╝ ║
║                                                              ║
║     Local-First AI Knowledge Base Agent                      ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  🧠 Intelligent Memory     - Agents remember context         ║
║  🔧 Claude Code Tools      - Bash, files, search, web       ║
║  🤖 Multi-Provider LLM     - OpenAI, Anthropic, Ollama       ║
║  📄 Wiki Knowledge Base    - Auto-maintained markdown wiki   ║
║  🔒 Local-First            - Zero data leaves your machine   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def feature_brain():
    """Showcase Brain (LLM interface)"""
    print("\n🧠 Feature: Brain (Unified LLM Interface)")
    print("-" * 50)
    
    brain = Brain()
    registry = brain.registry
    
    print(f"\n📊 Model Registry:")
    print(f"   Total models: {len(registry.models)}")
    
    # Show free models
    free_models = registry.list_free()
    print(f"\n💚 Free models ({len(free_models)}):")
    for m in free_models[:5]:
        print(f"   - {m.name} ({m.provider.value})")
    
    # Show stats
    print(f"\n📈 Brain stats: {brain.get_stats()}")


def feature_memory():
    """Showcase Memory"""
    print("\n🧠 Feature: Intelligent Memory")
    print("-" * 50)
    
    memory = Memory()
    
    # Store some memories
    memory.add("User prefers dark mode", entry_type="preference", importance=0.7)
    memory.add("User works with Python and Go", entry_type="fact", importance=0.8)
    memory.add("Remember to be concise in responses", entry_type="preference", importance=0.6)
    
    # Retrieve
    results = memory.retrieve("What does the user prefer?")
    
    print(f"\n📝 Stored 3 memories")
    print(f"\n🔍 Query: 'What does the user prefer?'")
    for r in results:
        print(f"   → {r.content}")
    
    print(f"\n📊 Memory stats: {memory.get_stats()}")


def feature_agents():
    """Showcase different agent types"""
    print("\n🤖 Feature: Specialized Agents")
    print("-" * 50)
    
    # General agent
    general = create_agent(model="llama3")
    print(f"\n1️⃣ General Agent:")
    print(f"   Name: {general.name}")
    print(f"   Tools: {[t.name for t in general.tools.list_tools()[:3]]}...")
    
    # Coder agent
    coder = create_coder_agent(model="codellama")
    print(f"\n2️⃣ Coder Agent:")
    print(f"   Name: {coder.name}")
    print(f"   Model: {coder.model}")
    print(f"   Instructions: {coder.config.system_prompt[:80]}...")


def feature_tools():
    """Showcase tool system"""
    print("\n🔧 Feature: Claude Code-Inspired Tools")
    print("-" * 50)
    
    from cortex import create_default_tools, BashTool, ReadFileTool
    
    tools = create_default_tools()
    
    print(f"\n📦 Default tools ({len(tools.list_tools())}):")
    categories = {}
    for tool in tools.list_tools():
        cat = tool.category.value
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(tool.name)
    
    for cat, names in categories.items():
        print(f"\n   {cat.upper()}:")
        for name in names[:3]:
            print(f"      • {name}")
        if len(names) > 3:
            print(f"      • ... and {len(names)-3} more")


def quick_demo():
    """Quick agent demo"""
    print("\n🚀 Quick Demo: Agent with Memory")
    print("-" * 50)
    
    memory = Memory()
    agent = Agent(model="llama3", memory=memory)
    
    print("\n1️⃣ User: 'My name is Alex and I work on AI research'")
    response = agent.run("My name is Alex and I work on AI research")
    print(f"   Agent: {response.content[:100]}...")
    
    print("\n2️⃣ User: 'What is my name?'")
    response = agent.run("What is my name?")
    print(f"   Agent: {response.content[:100]}...")
    
    print("\n3️⃣ User: 'What do I work on?'")
    response = agent.run("What do I work on?")
    print(f"   Agent: {response.content[:100]}...")


def main():
    welcome()
    feature_brain()
    feature_memory()
    feature_agents()
    feature_tools()
    quick_demo()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  ✅ Cortex is ready to use!                                  ║
║                                                              ║
║  Next steps:                                                 ║
║    1. Start Ollama: ollama serve                            ║
║    2. Try examples: python examples/01_quickstart.py         ║
║    3. Read docs: https://github.com/dp229/cortex          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
