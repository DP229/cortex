"""
Example 2: Multi-Agent Collaboration

Demonstrates multiple agents working together.
"""

from cortex import Agent, Memory


def multi_agent():
    """Run multiple agents with different roles"""
    print("=" * 60)
    print("Multi-Agent Collaboration")
    print("=" * 60)
    
    # Create specialized agents
    researcher = Agent(
        name="researcher",
        model="llama3",
        config=None,
    )
    # Override system prompt
    researcher.config.system_prompt = """You are a research assistant.
    You excel at finding information and summarizing key points."""
    
    writer = Agent(
        name="writer", 
        model="llama3",
    )
    writer.config.system_prompt = """You are a technical writer.
    You write clear, concise documentation."""
    
    memory = Memory()
    
    # Step 1: Research
    print("\n1️⃣ Researcher analyzing topic...")
    research_task = "What are the key benefits of distributed AI systems?"
    research_response = researcher.run(research_task, memory=memory)
    print(f"Researcher: {research_response.content[:200]}...")
    
    # Step 2: Write
    print("\n2️⃣ Writer creating documentation...")
    write_task = f"Based on this research, write a short paragraph:\n{research_response.content[:500]}"
    writer_response = writer.run(write_task)
    print(f"Writer: {writer_response.content[:300]}...")
    
    # Store final output
    memory.add(
        f"Distributed AI benefits: {writer_response.content[:100]}",
        entry_type="fact",
        importance=0.7,
    )
    
    print("\n✅ Multi-agent collaboration complete!")


if __name__ == "__main__":
    multi_agent()
