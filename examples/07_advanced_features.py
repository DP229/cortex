"""
Example 7: Advanced Features - Phase 2 Demonstration

Demonstrates:
- Redis memory (distributed)
- Qdrant vector DB (production)
- Cost optimizer (smart routing)
- Metrics (performance monitoring)

Run:
    python examples/07_advanced_features.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import Agent, Memory
from cortex.metrics import MetricsCollector, get_metrics
from cortex.optimizer import CostOptimizer


def example_cost_optimizer():
    """Demonstrate cost optimization"""
    print("=" * 60)
    print("Example 1: Cost Optimizer")
    print("=" * 60)
    
    optimizer = CostOptimizer(prefer_free=True)
    
    # Test model selection
    prompts = [
        "What is Python?",
        "Explain quantum computing",
        "Write a sorting algorithm",
        "Compare AI models",
    ]
    
    print("\n📊 Smart Model Selection:")
    for prompt in prompts:
        model = optimizer.select_model(prompt)
        complexity = optimizer._analyze_complexity(prompt)
        cost_est = optimizer.estimate_cost(prompt, model)
        
        print(f"\n  Prompt: '{prompt[:40]}...'")
        print(f"    Model: {model}")
        print(f"    Complexity: {complexity.value}")
        print(f"    Est. Cost: ${cost_est.estimated_cost:.4f}")
    
    # Test caching
    print("\n\n📦 Request Caching:")
    test_prompt = "What is machine learning?"
    
    # First request - cache miss
    cached = optimizer.get_cached(test_prompt, "llama3")
    print(f"  First request cache: {'HIT' if cached else 'MISS'}")
    
    # Cache the response
    optimizer.set_cached(test_prompt, "llama3", {"answer": "ML is..."})
    
    # Second request - cache hit
    cached = optimizer.get_cached(test_prompt, "llama3")
    print(f"  Second request cache: {'HIT' if cached else 'MISS'}")
    
    # Budget management
    print("\n\n💰 Budget Management:")
    optimizer.create_budget("project_x", total_credits=100.0, limit_per_request=10.0)
    
    can_run = optimizer.check_budget("project_x", 5.0)
    print(f"  Budget check (need $5): {'ALLOWED' if can_run else 'DENIED'}")
    
    optimizer.track_cost("project_x", 5.0)
    budget = optimizer.get_budget("project_x")
    print(f"  Budget: ${budget.spent_credits:.2f} / ${budget.total_credits:.2f}")
    
    print(f"\n📈 Optimizer Stats:")
    print(f"  Cache hit rate: {optimizer.get_cache_stats()['hit_rate']:.1%}")


def example_metrics():
    """Demonstrate performance metrics"""
    print("\n" + "=" * 60)
    print("Example 2: Performance Metrics")
    print("=" * 60)
    
    metrics = MetricsCollector()
    
    # Simulate requests
    print("\n📊 Simulating requests...")
    
    for i in range(10):
        latency = 100 + (i * 20)  # Varying latency
        tokens = 500 + (i * 50)
        cost = 0.001 + (i * 0.0005)
        success = i != 7  # One failure
        
        metrics.track_request(
            model="llama3",
            latency_ms=latency,
            tokens_used=tokens,
            cost=cost,
            success=success,
        )
    
    # Get stats
    stats = metrics.get_stats()
    
    print(f"\n📈 Request Statistics:")
    print(f"  Total requests: {stats['requests']['total']}")
    print(f"  Success rate: {stats['requests']['success_rate']:.1%}")
    
    print(f"\n⏱️  Latency:")
    print(f"  Min: {stats['latency_ms']['min']}ms")
    print(f"  Avg: {stats['latency_ms']['avg']:.1f}ms")
    print(f"  P95: {stats['latency_ms']['p95']:.1f}ms")
    print(f"  P99: {stats['latency_ms']['p99']:.1f}ms")
    
    print(f"\n💰 Cost:")
    print(f"  Total: ${stats['cost']['total']:.4f}")
    print(f"  Avg per request: ${stats['cost']['avg_per_request']:.6f}")
    
    print(f"\n📊 Model breakdown:")
    model_stats = metrics.get_model_stats()
    for model, m_stats in model_stats.items():
        print(f"  {model}:")
        print(f"    Requests: {m_stats['requests']}")
        print(f"    Avg latency: {m_stats['avg_latency_ms']}ms")


def example_memory_redis():
    """Demonstrate Redis memory"""
    print("\n" + "=" * 60)
    print("Example 3: Redis Memory (Distributed)")
    print("=" * 60)
    
    try:
        from cortex.memory_redis import RedisMemory
        
        memory = RedisMemory()
        
        if memory._redis:
            print("\n✅ Connected to Redis")
            
            # Add memories
            print("\n📝 Adding memories...")
            memory.add("User prefers dark mode", entry_type="preference")
            memory.add("User works on AI research", entry_type="fact")
            
            # Retrieve
            print("\n🔍 Retrieving preferences:")
            results = memory.retrieve(entry_type="preference")
            for r in results:
                print(f"  - {r.get('content')}")
            
            # Stats
            print(f"\n📊 Stats: {memory.get_stats()}")
            
            # Cleanup
            memory.clear()
            print("\n🗑️  Cleared memories")
        else:
            print("\n⚠️  Redis not connected (install Redis to enable)")
            print("   Run: docker run -d -p 6379:6379 redis")
    
    except ImportError:
        print("\n⚠️  Redis not installed")
        print("   Run: pip install redis")


def example_memory_qdrant():
    """Demonstrate Qdrant vector DB"""
    print("\n" + "=" * 60)
    print("Example 4: Qdrant Vector DB (Production)")
    print("=" * 60)
    
    try:
        from cortex.memory_qdrant import QdrantMemory
        
        memory = QdrantMemory()
        
        if memory._client:
            print("\n✅ Connected to Qdrant")
            
            # Add memories with embeddings
            print("\n📝 Adding memories with vectors...")
            
            test_embedding = [0.1] * 384  # Simplified embedding
            
            memory.add(
                content="Machine learning is a subset of AI",
                embedding=test_embedding,
                entry_type="fact",
            )
            
            # Search
            print("\n🔍 Searching vectors...")
            results = memory.search(test_embedding, limit=5)
            print(f"  Found {len(results)} results")
            
            # Count
            print(f"\n📊 Total memories: {memory.count()}")
            
            # Cleanup
            memory.clear()
            print("\n🗑️  Cleared collection")
        else:
            print("\n⚠️  Qdrant not connected (install Qdrant to enable)")
            print("   Run: docker run -d -p 6333:6333 qdrant/qdrant")
    
    except ImportError:
        print("\n⚠️  Qdrant client not installed")
        print("   Run: pip install qdrant-client")


def example_agent_with_tracking():
    """Demonstrate agent with metrics tracking"""
    print("\n" + "=" * 60)
    print("Example 5: Agent with Metrics Tracking")
    print("=" * 60)
    
    # Get global metrics
    metrics = get_metrics()
    metrics.reset()  # Clear previous data
    
    # Create agent
    agent = Agent(model="llama3")
    
    print("\n🤖 Running agent with metrics tracking...")
    
    prompts = [
        "What is Python?",
        "Explain AI",
        "Define machine learning",
    ]
    
    for prompt in prompts:
        start = time.time()
        response = agent.run(prompt)
        latency = int((time.time() - start) * 1000)
        
        # Track metrics
        metrics.track_request(
            model="llama3",
            latency_ms=latency,
            tokens_used=len(response.content) // 4,
            cost=0,  # Free model
            success=not response.error,
        )
        
        print(f"  ✅ '{prompt[:20]}...' - {latency}ms")
    
    print(f"\n📈 Global Metrics:")
    stats = metrics.get_stats()
    print(f"  Requests: {stats['requests']['total']}")
    print(f"  Avg latency: {stats['latency_ms']['avg']:.1f}ms")
    print(f"  P95 latency: {stats['latency_ms']['p95']:.1f}ms")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     NeuronMesh - Phase 2 Advanced Features                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  This example demonstrates Phase 2 (Intelligence) features:  ║
║  • Cost Optimizer - Smart routing, caching, budgets          ║
║  • Metrics - Performance monitoring, tracking                ║
║  • Redis Memory - Distributed memory                         ║
║  • Qdrant Vector DB - Production vector search               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    example_cost_optimizer()
    example_metrics()
    example_memory_redis()
    example_memory_qdrant()
    example_agent_with_tracking()
    
    print("\n" + "=" * 60)
    print("✅ All Phase 2 examples completed!")
    print("=" * 60)
    
    print("""

Next Steps:
  • Week 5: Advanced Memory (Redis, Qdrant, encryption) ✅
  • Week 6: Cost Optimization (routing, caching, budgets) ✅
  • Week 7: Optimization & Metrics ✅
  • Week 8: Distributed Execution (sharding, migration)

Learn more:
  • docs/API.md - Full API reference
  • docs/QUICKSTART.md - Getting started
    """)


if __name__ == "__main__":
    main()
