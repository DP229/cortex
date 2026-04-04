"""
NeuronMesh Optimizer - Cost Optimization & Smart Routing

Provides:
- Smart model routing based on task complexity
- Request caching
- Budget management
- Cost tracking

Inspired by TurboQuant's efficiency principles.
"""

import os
import time
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for routing"""
    TRIVIAL = "trivial"     # Simple queries
    SIMPLE = "simple"       # Basic tasks
    MODERATE = "moderate"   # Standard tasks
    COMPLEX = "complex"     # Challenging tasks
    EXPERT = "expert"       # Expert-level tasks


@dataclass
class CostEstimate:
    """Cost estimate for a task"""
    model: str
    estimated_tokens: int
    estimated_cost: float
    complexity: TaskComplexity
    reasoning: str


@dataclass
class Budget:
    """Budget for an agent or project"""
    name: str
    total_credits: float
    spent_credits: float = 0.0
    limit_per_day: float = 0.0
    limit_per_request: float = 0.0
    
    @property
    def remaining(self) -> float:
        return self.total_credits - self.spent_credits
    
    @property
    def exhausted(self) -> bool:
        return self.spent_credits >= self.total_credits


@dataclass
class CacheEntry:
    """Cached response"""
    key: str
    response: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    ttl: int = 3600  # 1 hour default


class CostOptimizer:
    """
    Cost optimization engine.
    
    Features:
    - Smart model routing based on task analysis
    - Request caching with TTL
    - Budget management
    - Cost tracking and reporting
    
    Example:
        optimizer = CostOptimizer()
        
        # Route to best model
        model = optimizer.select_model("Explain quantum physics", complexity_threshold=0.5)
        
        # Check budget
        if optimizer.check_budget("project_x", 10.0):
            response = agent.run(prompt)
            optimizer.track_cost("project_x", 0.05)
    """
    
    def __init__(
        self,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        max_cache_size: int = 1000,
        prefer_free: bool = True,
    ):
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self.prefer_free = prefer_free
        
        # Cache
        self._cache: Dict[str, CacheEntry] = {}
        
        # Budgets
        self._budgets: Dict[str, Budget] = {}
        
        # Cost tracking
        self._total_spent = 0.0
        self._request_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Model costs (per 1K tokens)
        self._model_costs = {
            # OpenAI
            "gpt-4o": 0.006,
            "gpt-4o-mini": 0.00015,
            "gpt-4-turbo": 0.01,
            "gpt-3.5-turbo": 0.001,
            
            # Anthropic
            "claude-sonnet-4": 0.009,
            "claude-3.5-sonnet": 0.009,
            "claude-3.5-haiku": 0.0012,
            
            # Free models
            "llama3": 0.0,
            "codellama": 0.0,
            "mistral": 0.0,
            "mixtral": 0.0,
        }
        
        # Model capabilities
        self._model_capabilities = {
            "gpt-4o": {"reasoning", "coding", "creative", "analysis"},
            "gpt-3.5-turbo": {"chat", "simple_reasoning"},
            "claude-sonnet-4": {"reasoning", "analysis", "long_context"},
            "claude-3.5-haiku": {"chat", "fast"},
            "llama3": {"chat", "simple_reasoning"},
            "codellama": {"coding", "completion"},
            "mistral": {"chat"},
            "mixtral": {"chat", "reasoning"},
        }
    
    # === Caching ===
    
    def _cache_key(self, prompt: str, model: str) -> str:
        """Generate cache key"""
        content = f"{model}:{prompt[:1000]}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def get_cached(self, prompt: str, model: str) -> Optional[Any]:
        """Get cached response"""
        if not self.cache_enabled:
            return None
        
        key = self._cache_key(prompt, model)
        
        if key in self._cache:
            entry = self._cache[key]
            
            # Check TTL
            if time.time() - entry.created_at > entry.ttl:
                del self._cache[key]
                self._cache_misses += 1
                return None
            
            # Update access
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._cache_hits += 1
            
            return entry.response
        
        self._cache_misses += 1
        return None
    
    def set_cached(self, prompt: str, model: str, response: Any, ttl: int = None):
        """Cache a response"""
        if not self.cache_enabled:
            return
        
        key = self._cache_key(prompt, model)
        ttl = ttl or self.cache_ttl
        
        # Evict oldest if full
        if len(self._cache) >= self.max_cache_size:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(
            key=key,
            response=response,
            created_at=time.time(),
            ttl=ttl,
        )
    
    def _evict_oldest(self):
        """Evict least recently used entry"""
        if not self._cache:
            return
        
        oldest = min(self._cache.values(), key=lambda e: e.last_accessed)
        del self._cache[oldest.key]
    
    def clear_cache(self):
        """Clear all cached responses"""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(hit_rate, 3),
        }
    
    # === Cost Estimation ===
    
    def estimate_cost(
        self,
        prompt: str,
        model: str,
        response_length: int = 500,
    ) -> CostEstimate:
        """Estimate cost for a task"""
        # Estimate tokens (rough: 4 chars = 1 token)
        input_tokens = len(prompt) // 4
        output_tokens = response_length
        total_tokens = input_tokens + output_tokens
        
        # Get cost per 1K
        cost_per_1k = self._model_costs.get(model, 0.001)
        
        # Calculate cost
        estimated_cost = (total_tokens / 1000) * cost_per_1k
        
        # Analyze complexity
        complexity = self._analyze_complexity(prompt)
        
        reasoning = f"{complexity.value} task, ~{total_tokens} tokens"
        
        return CostEstimate(
            model=model,
            estimated_tokens=total_tokens,
            estimated_cost=estimated_cost,
            complexity=complexity,
            reasoning=reasoning,
        )
    
    def _analyze_complexity(self, prompt: str) -> TaskComplexity:
        """Analyze task complexity from prompt"""
        prompt_lower = prompt.lower()
        
        # Expert-level indicators
        expert_keywords = [
            "prove", "derive", "analyze deeply", "research paper",
            "mathematical", "complex algorithm", "architect",
        ]
        
        # Complex indicators
        complex_keywords = [
            "explain", "compare", "contrast", "implement",
            "debug", "optimize", "design", "create a",
        ]
        
        # Simple indicators
        simple_keywords = [
            "what is", "who is", "define", "simple",
            "list", "quick", "brief",
        ]
        
        if any(kw in prompt_lower for kw in expert_keywords):
            return TaskComplexity.EXPERT
        elif any(kw in prompt_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX
        elif any(kw in prompt_lower for kw in simple_keywords):
            return TaskComplexity.TRIVIAL
        else:
            return TaskComplexity.MODERATE
    
    # === Model Selection ===
    
    def select_model(
        self,
        prompt: str,
        required_capability: str = None,
        max_cost: float = 1.0,
        prefer_fast: bool = False,
    ) -> str:
        """
        Select the best model based on task requirements.
        
        Args:
            prompt: User prompt
            required_capability: Required capability (e.g., "coding")
            max_cost: Maximum cost per request
            prefer_fast: Prefer faster models
            
        Returns:
            Selected model name
        """
        complexity = self._analyze_complexity(prompt)
        
        # For simple tasks, use free/fast models
        if complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            if "coding" in prompt.lower() or "code" in prompt.lower():
                if self.prefer_free:
                    return "codellama"  # Free coding model
                return "gpt-3.5-turbo"
            if self.prefer_free:
                return "llama3"
            return "gpt-3.5-turbo"
        
        # For complex tasks, use capable models
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
            if "coding" in prompt.lower():
                if self.prefer_free:
                    return "codellama"
                return "gpt-4o"
            if required_capability == "long_context":
                return "claude-sonnet-4"
            if self.prefer_free:
                return "mixtral"  # Free reasoning model
            return "gpt-4o"
        
        # For moderate tasks, balance cost and capability
        if self.prefer_free:
            return "llama3"
        return "gpt-3.5-turbo"
    
    # === Budget Management ===
    
    def create_budget(
        self,
        name: str,
        total_credits: float,
        limit_per_day: float = 0,
        limit_per_request: float = 0,
    ) -> Budget:
        """Create a new budget"""
        budget = Budget(
            name=name,
            total_credits=total_credits,
            limit_per_day=limit_per_day,
            limit_per_request=limit_per_request,
        )
        self._budgets[name] = budget
        return budget
    
    def check_budget(self, name: str, required_amount: float = 0) -> bool:
        """Check if budget allows request"""
        if name not in self._budgets:
            return True  # No budget means allowed
        
        budget = self._budgets[name]
        
        # Check remaining
        if budget.exhausted:
            return False
        
        # Check per-request limit
        if budget.limit_per_request > 0 and required_amount > budget.limit_per_request:
            return False
        
        # Check daily limit (simplified)
        if budget.limit_per_day > 0:
            # Would need daily tracking for full implementation
            pass
        
        return True
    
    def track_cost(self, name: str, amount: float):
        """Track cost against budget"""
        if name in self._budgets:
            self._budgets[name].spent_credits += amount
        
        self._total_spent += amount
        self._request_count += 1
    
    def get_budget(self, name: str) -> Optional[Budget]:
        """Get budget info"""
        return self._budgets.get(name)
    
    def get_budgets(self) -> List[Budget]:
        """Get all budgets"""
        return list(self._budgets.values())
    
    # === Statistics ===
    
    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics"""
        return {
            "total_spent": round(self._total_spent, 4),
            "request_count": self._request_count,
            "avg_cost": round(self._total_spent / self._request_count, 4) if self._request_count > 0 else 0,
            "cache": self.get_cache_stats(),
            "budgets": {
                name: {
                    "total": b.total_credits,
                    "spent": b.spent_credits,
                    "remaining": round(b.remaining, 4),
                }
                for name, b in self._budgets.items()
            },
        }


# === Global optimizer ===

_global_optimizer: Optional[CostOptimizer] = None


def get_optimizer() -> CostOptimizer:
    """Get global optimizer instance"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = CostOptimizer()
    return _global_optimizer
