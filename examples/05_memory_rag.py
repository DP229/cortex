"""
Example 5: Memory with RAG - Semantic Search & Persistence

Demonstrates:
- Vector embeddings for semantic search
- SQLite persistent storage
- Memory consolidation (STM -> LTM)
- Memory decay over time
- Cross-session memory

Inspired by Hermes Agent's Honcho user modeling.

Run:
    python examples/05_memory_rag.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import Memory, MemoryType, MemoryImportance


def example_basic_rag():
    """Basic RAG memory functionality"""
    print("=" * 60)
    print("Example 1: Basic RAG Memory")
    print("=" * 60)
    
    memory = Memory()
    
    # Store various types of memories
    print("\n📝 Storing memories...")
    
    memory.add(
        "User prefers dark mode interfaces",
        entry_type="preference",
        importance=MemoryImportance.HIGH.value,
        tags=["ui", "preference"]
    )
    
    memory.add(
        "User works as a Python developer",
        entry_type="fact",
        importance=MemoryImportance.NORMAL.value,
        tags=["work", "developer"]
    )
    
    memory.add(
        "Remember to use type hints in all Python code",
        entry_type="skill",
        importance=MemoryImportance.HIGH.value,
        tags=["coding", "python"]
    )
    
    memory.add(
        "User is interested in AI and machine learning",
        entry_type="fact",
        importance=MemoryImportance.NORMAL.value,
        tags=["ai", "interest"]
    )
    
    memory.add(
        "Don't suggest JavaScript solutions",
        entry_type="constraint",
        importance=MemoryImportance.CRITICAL.value,
        tags=["constraint", "language"]
    )
    
    # Retrieve semantically
    print("\n🔍 Query: 'What does the user prefer for UI?'")
    results = memory.retrieve("What does the user prefer for UI?", limit=3)
    for i, entry in enumerate(results, 1):
        print(f"  {i}. [{entry.entry_type}] {entry.content}")
    
    print("\n🔍 Query: 'What programming language does the user know?'")
    results = memory.retrieve("programming language expertise", limit=3)
    for i, entry in enumerate(results, 1):
        print(f"  {i}. [{entry.entry_type}] {entry.content}")
    
    print("\n🔍 Query: 'Any coding guidelines?'")
    results = memory.retrieve("coding guidelines", limit=3)
    for i, entry in enumerate(results, 1):
        print(f"  {i}. [{entry.entry_type}] {entry.content}")


def example_semantic_search():
    """Demonstrate semantic search capabilities"""
    print("\n" + "=" * 60)
    print("Example 2: Semantic Search")
    print("=" * 60)
    
    memory = Memory()
    
    # Store memories with varied content
    memories = [
        ("I love drinking coffee in the morning", "preference", ["coffee", "morning"]),
        ("I'm allergic to shellfish", "health", ["allergy", "food"]),
        ("My favorite color is blue", "preference", ["color"]),
        ("I prefer working in quiet environments", "preference", ["work", "environment"]),
        ("I know Python and Go programming", "skill", ["programming", "languages"]),
        ("My birthday is in March", "fact", ["personal"]),
        ("I don't like noisy places", "preference", ["environment", "noise"]),
        ("I'm learning Spanish", "goal", ["language", "learning"]),
    ]
    
    for content, entry_type, tags in memories:
        memory.add(content, entry_type=entry_type, tags=tags)
    
    # Test various queries
    queries = [
        "What are the user's food preferences?",
        "Tell me about programming skills",
        "Any workplace preferences?",
        "Language learning goals",
        "What does the user drink?",
    ]
    
    print("\n🔍 Testing semantic queries:")
    for query in queries:
        print(f"\n  Query: '{query}'")
        results = memory.retrieve(query, limit=2)
        for entry, score in [(e, 1.0) for e in results]:
            print(f"    → {entry.content[:50]}... [{entry.entry_type}]")


def example_remember_function():
    """Using the remember() convenience function"""
    print("\n" + "=" * 60)
    print("Example 3: Remember Function")
    print("=" * 60)
    
    memory = Memory()
    
    # Store context
    memory.add("User is building a distributed AI system", entry_type="project")
    memory.add("Project uses Python and Go", entry_type="fact")
    memory.add("User prefers async patterns", entry_type="preference")
    
    # Get formatted memory context
    context = memory.remember("What is the user working on?")
    print("\n📋 Memory context for 'What is the user working on?':")
    print(context)


def example_memory_types():
    """Demonstrate different memory types"""
    print("\n" + "=" * 60)
    print("Example 4: Memory Types")
    print("=" * 60)
    
    memory = Memory()
    
    # Short-term memory
    print("\n📝 Adding to SHORT_TERM memory...")
    memory.add(
        "This is a temporary thought",
        entry_type="thought",
        memory_type=MemoryType.SHORT_TERM
    )
    
    # Long-term memory
    print("📝 Adding to LONG_TERM memory...")
    memory.add(
        "User has been working on AI for 5 years",
        entry_type="fact",
        memory_type=MemoryType.LONG_TERM,
        importance=MemoryImportance.HIGH.value
    )
    
    # Semantic memory
    print("📝 Adding to SEMANTIC memory...")
    memory.add(
        "Python is a programming language",
        entry_type="knowledge",
        memory_type=MemoryType.SEMANTIC
    )
    
    # Working memory (current task)
    print("📝 Adding to WORKING memory...")
    memory.add(
        "Currently debugging the neural network training",
        entry_type="context",
        memory_type=MemoryType.WORKING
    )
    
    # Stats
    print("\n📊 Memory statistics:")
    stats = memory.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def example_persistence():
    """Demonstrate persistence across sessions"""
    print("\n" + "=" * 60)
    print("Example 5: Persistence")
    print("=" * 60)
    
    # Use specific storage path for demo
    storage_path = "/tmp/cortex_demo_memory"
    
    # Create memory and add data
    memory1 = Memory(storage_path=storage_path)
    memory1.add("This memory persists across sessions", entry_type="fact")
    
    print(f"\n💾 Memory stored at: {storage_path}")
    print(f"📊 Stats: {memory1.get_stats()}")
    
    # Simulate session end
    del memory1
    
    # Create new memory instance - should still have the data
    memory2 = Memory(storage_path=storage_path)
    print(f"\n🔄 New session started")
    print(f"📊 Stats: {memory2.get_stats()}")
    
    # Retrieve
    results = memory2.retrieve("What memory persists?", limit=1)
    if results:
        print(f"\n✅ Retrieved: {results[0].content}")
    
    # Clean up
    memory2.clear()


def example_importance_decay():
    """Demonstrate memory importance and decay"""
    print("\n" + "=" * 60)
    print("Example 6: Importance & Decay")
    print("=" * 60)
    
    memory = Memory()
    
    # Add memories with different importance levels
    print("\n📝 Adding memories with varying importance...")
    
    memory.add(
        "Critical security requirement: encrypt all data",
        entry_type="security",
        importance=MemoryImportance.CRITICAL.value,
        tags=["security", "critical"]
    )
    
    memory.add(
        "User casually mentioned liking pizza",
        entry_type="preference",
        importance=MemoryImportance.TRIVIAL.value,
        tags=["food"]
    )
    
    memory.add(
        "User's main project deadline is Friday",
        entry_type="goal",
        importance=MemoryImportance.HIGH.value,
        tags=["project", "urgent"]
    )
    
    # Query - should prioritize by importance
    print("\n🔍 Query: 'What are important things to remember?'")
    results = memory.retrieve("What are important things to remember?", limit=3)
    for i, entry in enumerate(results, 1):
        stars = "⭐" * int(entry.importance * 5)
        print(f"  {i}. {entry.content[:50]}... {stars}")


def example_agent_integration():
    """Show how agents use memory"""
    print("\n" + "=" * 60)
    print("Example 7: Agent Integration")
    print("=" * 60)
    
    from cortex import Agent
    
    # Create memory
    memory = Memory(agent_id="assistant-001")
    
    # Add context about user
    memory.add("User is named Alex", entry_type="fact", importance=MemoryImportance.HIGH.value)
    memory.add("User prefers concise responses", entry_type="preference", importance=MemoryImportance.NORMAL.value)
    memory.add("User works in AI research", entry_type="fact", importance=MemoryImportance.HIGH.value)
    
    # Create agent with memory
    agent = Agent(model="llama3", memory=memory)
    
    print("\n🤖 Agent created with memory context")
    print(f"📊 Memory stats: {memory.get_stats()}")
    
    # Use remember() for context
    context = memory.remember("Tell me about the user")
    print(f"\n📋 Agent memory context:\n{context}")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       NeuronMesh - Memory with RAG Examples                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  These examples demonstrate the intelligent memory layer:      ║
║  • Vector embeddings for semantic search                     ║
║  • SQLite persistent storage                                 ║
║  • Memory consolidation (STM -> LTM)                        ║
║  • Memory decay over time                                   ║
║  • Cross-agent shared memory                                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    example_basic_rag()
    example_semantic_search()
    example_remember_function()
    example_memory_types()
    example_persistence()
    example_importance_decay()
    example_agent_integration()
    
    print("\n✅ All memory examples completed!")


if __name__ == "__main__":
    main()
