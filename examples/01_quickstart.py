"""
Example 1: Quick Start with NeuronMesh

Run this after installing cortex:
    pip install cortex
    ollama serve  # Start Ollama in another terminal

Then run:
    python examples/01_quickstart.py
"""

from cortex import Agent, Memory


def quickstart():
    """Basic agent with memory"""
    print("=" * 60)
    print("NeuronMesh Quick Start")
    print("=" * 60)
    
    # Create agent
    agent = Agent(model="llama3")
    
    # Create memory
    memory = Memory()
    
    # First conversation
    print("\n1️⃣ First interaction:")
    response = agent.run(
        "My name is Jack and I prefer dark mode interfaces.",
        memory=memory
    )
    print(f"Agent: {response.content[:200]}...")
    
    # Second conversation - agent remembers
    print("\n2️⃣ Second interaction (with memory):")
    response = agent.run(
        "What is my name and what interface style do I prefer?",
        memory=memory
    )
    print(f"Agent: {response.content[:200]}...")
    
    # Check memory stats
    print("\n3️⃣ Memory statistics:")
    stats = memory.get_stats()
    print(f"   Total memories: {stats['total_memories']}")
    print(f"   Long-term: {stats['ltm_size']}")


if __name__ == "__main__":
    quickstart()
