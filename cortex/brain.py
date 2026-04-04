"""
NeuronMesh Brain - Unified LLM Interface

Provides a unified interface to multiple LLM providers with:
- Multi-provider support (OpenAI, Anthropic, Ollama, OpenRouter, etc.)
- Streaming support
- Cost optimization
- Fallback chains for reliability

Inspired by Hermes Agent's multi-provider support and AutoAgent's natural language interface.
"""

import os
import time
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    LM_STUDIO = "lmstudio"
    VLLM = "vllm"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    LOCAL = "local"  # llama.cpp style


@dataclass
class ModelConfig:
    """Configuration for a model generation"""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    stop: Optional[List[str]] = None
    stream: bool = False
    repetition_penalty: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "stop": self.stop,
            "stream": self.stream,
            "repetition_penalty": self.repetition_penalty,
        }


@dataclass
class ModelInfo:
    """Information about a model"""
    name: str
    provider: ModelProvider
    context_length: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    capabilities: List[str] = field(default_factory=list)  # "chat", "completion", "function_calling"
    description: str = ""
    
    @property
    def cost_per_1k(self) -> float:
        return (self.cost_per_1k_input + self.cost_per_1k_output) / 2
    
    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


class ModelRegistry:
    """Registry of available models"""
    
    # Default models with pricing
    DEFAULT_MODELS = {
        # OpenAI
        "gpt-4o": ModelInfo(
            name="gpt-4o",
            provider=ModelProvider.OPENAI,
            context_length=128000,
            cost_per_1k_input=0.0025,
            cost_per_1k_output=0.01,
            capabilities=["chat", "function_calling", "vision"],
            description="GPT-4o - Latest, fastest GPT-4",
        ),
        "gpt-4o-mini": ModelInfo(
            name="gpt-4o-mini",
            provider=ModelProvider.OPENAI,
            context_length=128000,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            capabilities=["chat", "function_calling"],
            description="GPT-4o Mini - Fast and cheap",
        ),
        "gpt-4-turbo": ModelInfo(
            name="gpt-4-turbo",
            provider=ModelProvider.OPENAI,
            context_length=128000,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            capabilities=["chat", "function_calling"],
            description="GPT-4 Turbo - Powerful and capable",
        ),
        "gpt-3.5-turbo": ModelInfo(
            name="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI,
            context_length=16385,
            cost_per_1k_input=0.0005,
            cost_per_1k_output=0.0015,
            capabilities=["chat", "function_calling"],
            description="GPT-3.5 Turbo - Fast and affordable",
        ),
        
        # Anthropic
        "claude-sonnet-4-20250514": ModelInfo(
            name="claude-sonnet-4-20250514",
            provider=ModelProvider.ANTHROPIC,
            context_length=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            capabilities=["chat", "function_calling"],
            description="Claude Sonnet 4 - Balanced capability",
        ),
        "claude-3-5-sonnet-20241022": ModelInfo(
            name="claude-3-5-sonnet-20241022",
            provider=ModelProvider.ANTHROPIC,
            context_length=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            capabilities=["chat", "function_calling"],
            description="Claude 3.5 Sonnet - Latest Sonnet",
        ),
        "claude-3-5-haiku-20241022": ModelInfo(
            name="claude-3-5-haiku-20241022",
            provider=ModelProvider.ANTHROPIC,
            context_length=200000,
            cost_per_1k_input=0.0008,
            cost_per_1k_output=0.004,
            capabilities=["chat"],
            description="Claude 3.5 Haiku - Fast and cheap",
        ),
        
        # Ollama / Local (Free)
        "llama3": ModelInfo(
            name="llama3",
            provider=ModelProvider.OLLAMA,
            context_length=8192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Meta's Llama 3 8B - Open model",
        ),
        "llama3.1": ModelInfo(
            name="llama3.1",
            provider=ModelProvider.OLLAMA,
            context_length=128000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Llama 3.1 - Extended context",
        ),
        "llama3.2": ModelInfo(
            name="llama3.2",
            provider=ModelProvider.OLLAMA,
            context_length=128000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat", "vision"],
            description="Llama 3.2 - Vision support",
        ),
        "codellama": ModelInfo(
            name="codellama",
            provider=ModelProvider.OLLAMA,
            context_length=16384,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat", "completion"],
            description="Code Llama - Specialized for code",
        ),
        "mistral": ModelInfo(
            name="mistral",
            provider=ModelProvider.OLLAMA,
            context_length=8192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Mistral AI - Efficient open model",
        ),
        "mixtral": ModelInfo(
            name="mixtral",
            provider=ModelProvider.OLLAMA,
            context_length=32768,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Mixtral - Mixture of experts",
        ),
        "qwen2.5": ModelInfo(
            name="qwen2.5",
            provider=ModelProvider.OLLAMA,
            context_length=32768,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Qwen 2.5 - Strong Chinese support",
        ),
        "gemma2": ModelInfo(
            name="gemma2",
            provider=ModelProvider.OLLAMA,
            context_length=8192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Google Gemma 2 - Lightweight model",
        ),
        "nomic-embed-text": ModelInfo(
            name="nomic-embed-text",
            provider=ModelProvider.OLLAMA,
            context_length=8192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["embeddings"],
            description="Nomic Embed Text - For embeddings",
        ),
        
        # OpenRouter (aggregates many models)
        "openrouter/deepseek/deepseek-r1": ModelInfo(
            name="openrouter/deepseek/deepseek-r1",
            provider=ModelProvider.OPENROUTER,
            context_length=64000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat", "reasoning"],
            description="DeepSeek R1 - OpenAI competitor",
        ),
        "openrouter/anthropic/claude-3.5-sonnet": ModelInfo(
            name="openrouter/anthropic/claude-3.5-sonnet",
            provider=ModelProvider.OPENROUTER,
            context_length=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            capabilities=["chat", "function_calling"],
            description="Claude via OpenRouter",
        ),
        
        # Groq (fast inference)
        "groq/llama-3.3-70b-versatile": ModelInfo(
            name="groq/llama-3.3-70b-versatile",
            provider=ModelProvider.GROQ,
            context_length=128000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Groq Llama 3.3 70B - Extremely fast",
        ),
        "groq/mixtral-8x7b-32768": ModelInfo(
            name="groq/mixtral-8x7b-32768",
            provider=ModelProvider.GROQ,
            context_length=32768,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            capabilities=["chat"],
            description="Groq Mixtral - Fast MoE",
        ),
    }
    
    def __init__(self):
        self.models: Dict[str, ModelInfo] = self.DEFAULT_MODELS.copy()
    
    def register(self, model: ModelInfo):
        """Register a new model"""
        self.models[model.name] = model
    
    def get(self, name: str) -> Optional[ModelInfo]:
        """Get model info"""
        return self.models.get(name)
    
    def list(self, provider: Optional[ModelProvider] = None) -> List[ModelInfo]:
        """List all models, optionally filtered by provider"""
        models = list(self.models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models
    
    def list_free(self) -> List[ModelInfo]:
        """List all free models (local/API)"""
        return [m for m in self.models.values() if m.cost_per_1k == 0]
    
    def list_by_capability(self, capability: str) -> List[ModelInfo]:
        """List models by capability"""
        return [m for m in self.models.values() if m.supports(capability)]
    
    def select(
        self,
        task: str = "chat",
        max_cost: float = 1.0,
        prefer_free: bool = True,
    ) -> Optional[ModelInfo]:
        """
        Select the best model for a task based on constraints.
        
        Args:
            task: Type of task ("chat", "completion", "embedding")
            max_cost: Maximum cost per 1K tokens
            prefer_free: Prefer free models when available
            
        Returns:
            Best model for the task, or None
        """
        candidates = [
            m for m in self.models.values()
            if m.supports(task) and m.cost_per_1k <= max_cost
        ]
        
        if not candidates:
            return None
        
        if prefer_free:
            # Prioritize free models
            free = [m for m in candidates if m.cost_per_1k == 0]
            if free:
                return free[0]
        
        # Sort by cost (prefer cheaper)
        candidates.sort(key=lambda m: m.cost_per_1k)
        
        return candidates[0]


class Brain:
    """
    Unified interface to LLM providers.
    
    Features:
    - Automatic provider detection based on model name
    - Streaming responses
    - Cost tracking
    - Fallback chains
    
    Inspired by Hermes Agent's multi-provider support.
    """
    
    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        default_model: str = "llama3",
        api_key: Optional[str] = None,
    ):
        self.registry = registry or ModelRegistry()
        self.default_model = default_model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        
        # Provider clients
        self._clients: Dict[ModelProvider, Any] = {}
        self._init_clients()
        
        # Metrics
        self._total_requests = 0
        self._total_cost = 0.0
        self._total_tokens = 0
    
    def _init_clients(self):
        """Initialize provider clients based on environment"""
        # Check for API keys
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import AsyncOpenAI, OpenAI
                self._clients[ModelProvider.OPENAI] = AsyncOpenAI()
                self._clients["openai_sync"] = OpenAI()
            except ImportError:
                logger.warning("OpenAI SDK not installed")
        
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                from anthropic import AsyncAnthropic, Anthropic
                self._clients[ModelProvider.ANTHROPIC] = AsyncAnthropic()
                self._clients["anthropic_sync"] = Anthropic()
            except ImportError:
                logger.warning("Anthropic SDK not installed")
        
        # Ollama is always available if running locally
        self._clients[ModelProvider.OLLAMA] = _OllamaClient()
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Generate text using the specified model (sync version).
        """
        model = model or self.default_model
        config = config or ModelConfig()
        
        # Detect provider
        model_info = self.registry.get(model)
        if model_info:
            provider = model_info.provider
        else:
            if model.startswith("gpt-"):
                provider = ModelProvider.OPENAI
            elif model.startswith("claude-"):
                provider = ModelProvider.ANTHROPIC
            elif model.startswith("groq-") or model.startswith("groq/"):
                provider = ModelProvider.GROQ
            elif model.startswith("openrouter/") or model.startswith("or-"):
                provider = ModelProvider.OPENROUTER
            else:
                provider = ModelProvider.OLLAMA
        
        client = self._get_sync_client(provider)
        if not client:
            raise ValueError(f"No client available for provider {provider}")
        
        self._total_requests += 1
        
        try:
            if provider == ModelProvider.OPENAI:
                return self._generate_openai(client, model, prompt, config, system_prompt)
            elif provider == ModelProvider.ANTHROPIC:
                return self._generate_anthropic(client, model, prompt, config, system_prompt)
            elif provider == ModelProvider.GROQ:
                return self._generate_groq(client, model, prompt, config, system_prompt)
            elif provider == ModelProvider.OPENROUTER:
                return self._generate_openrouter(client, model, prompt, config, system_prompt)
            else:
                return self._generate_ollama(client, model, prompt, config)
                
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model-specific pricing (per 1K tokens)"""
        pricing = {
            # OpenAI
            "gpt-4o": {"input": 0.0025, "output": 0.010},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.010, "output": 0.030},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            # Anthropic
            "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
            # Groq
            "llama-3.1-70b": {"input": 0.00059, "output": 0.00079},
            "llama-3.1-8b": {"input": 0.00005, "output": 0.00008},
            # Default fallback
        }
        
        model_pricing = pricing.get(model, {"input": 0.001, "output": 0.002})
        
        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model-specific pricing (per 1K tokens)"""
        pricing = {
            # OpenAI
            "gpt-4o": {"input": 0.0025, "output": 0.010},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.010, "output": 0.030},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            # Anthropic
            "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
            # Groq
            "llama-3.1-70b": {"input": 0.00059, "output": 0.00079},
            "llama-3.1-8b": {"input": 0.00005, "output": 0.00008},
            # Default fallback
        }
        
        model_pricing = pricing.get(model, {"input": 0.001, "output": 0.002})
        
        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    def _get_sync_client(self, provider: ModelProvider):
        """Get sync client for provider"""
        if provider == ModelProvider.OPENAI:
            return self._clients.get("openai_sync")
        elif provider == ModelProvider.ANTHROPIC:
            return self._clients.get("anthropic_sync")
        elif provider == ModelProvider.OLLAMA:
            return self._clients.get(provider)
        else:
            # For other providers, try to find any available client
            return self._clients.get(provider)
    
    def _generate_openai(
        self,
        client,
        model: str,
        prompt: str,
        config: ModelConfig,
        system_prompt: Optional[str],
    ) -> tuple[str, Dict[str, Any]]:
        """Generate using OpenAI API"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stop=config.stop,
        )
        
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": self._calculate_cost(model, response.usage.prompt_tokens, response.usage.completion_tokens),
        }
        
        self._total_cost += usage["cost"]
        self._total_tokens += usage["total_tokens"]
        
        return text, usage
    
    def _generate_anthropic(
        self,
        client,
        model: str,
        prompt: str,
        config: ModelConfig,
        system_prompt: Optional[str],
    ) -> tuple[str, Dict[str, Any]]:
        """Generate using Anthropic API"""
        response = client.messages.create(
            model=model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            "cost": 0.0,  # Calculate based on model pricing
        }
        
        return text, usage
    
    def _generate_ollama(
        self,
        client,
        model: str,
        prompt: str,
        config: ModelConfig,
    ) -> tuple[str, Dict[str, Any]]:
        """Generate using Ollama API"""
        text = client.generate(model, prompt, config)
        usage = {"cost": 0}  # Local models are free
        
        return text, usage
    
    async def generate_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Async version of generate using native async clients"""
        model = model or self.default_model
        config = config or ModelConfig()
        
        # Detect provider
        model_info = self.registry.get(model)
        if model_info:
            provider = model_info.provider
        else:
            if model.startswith("gpt-"):
                provider = ModelProvider.OPENAI
            elif model.startswith("claude-"):
                provider = ModelProvider.ANTHROPIC
            else:
                provider = ModelProvider.OLLAMA
        
        # Use async client
        async_client = self._clients.get(provider)
        if async_client:
            self._total_requests += 1
            try:
                if provider == ModelProvider.OPENAI:
                    return await self._generate_async_openai(async_client, model, prompt, config, system_prompt)
                elif provider == ModelProvider.ANTHROPIC:
                    return await self._generate_async_anthropic(async_client, model, prompt, config, system_prompt)
                else:
                    return await async_client.generate_async(prompt, model, config, system_prompt)
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(2)
                    return await self.generate_async(prompt, model, config, system_prompt)
                raise
        
        # Fallback to sync
        return self.generate(prompt, model, config, system_prompt)
    
    async def _generate_async_openai(self, client, model, prompt, config, system_prompt):
        """Async OpenAI generation with rate limit handling"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stop=config.stop,
        )
        
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": self._calculate_cost(model, response.usage.prompt_tokens, response.usage.completion_tokens),
        }
        
        self._total_cost += usage["cost"]
        self._total_tokens += usage["total_tokens"]
        
        return text, usage
    
    async def _generate_async_anthropic(self, client, model, prompt, config, system_prompt):
        """Async Anthropic generation with rate limit handling"""
        response = await client.messages.create(
            model=model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = response.content[0].text
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": total_tokens,
            "cost": self._calculate_cost(model, response.usage.input_tokens, response.usage.output_tokens),
        }
        
        self._total_cost += usage["cost"]
        self._total_tokens += usage["total_tokens"]
        
        return text, usage
    
    async def _generate_async_openai(self, client, model, prompt, config, system_prompt):
        """Async OpenAI generation with rate limit handling"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stop=config.stop,
        )
        
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": self._calculate_cost(model, response.usage.prompt_tokens, response.usage.completion_tokens),
        }
        
        self._total_cost += usage["cost"]
        self._total_tokens += usage["total_tokens"]
        
        return text, usage
    
    async def _generate_async_anthropic(self, client, model, prompt, config, system_prompt):
        """Async Anthropic generation with rate limit handling"""
        response = await client.messages.create(
            model=model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = response.content[0].text
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": total_tokens,
            "cost": self._calculate_cost(model, response.usage.input_tokens, response.usage.output_tokens),
        }
        
        self._total_cost += usage["cost"]
        self._total_tokens += usage["total_tokens"]
        
        return text, usage
    
    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Streaming generation"""
        model = model or self.default_model
        config = config or ModelConfig()
        
        # Detect provider
        model_info = self.registry.get(model)
        if model_info:
            provider = model_info.provider
        else:
            if model.startswith("gpt-"):
                provider = ModelProvider.OPENAI
            elif model.startswith("claude-"):
                provider = ModelProvider.ANTHROPIC
            elif "/" in model:
                provider = ModelProvider.OPENROUTER
            else:
                provider = ModelProvider.OLLAMA
        
        if provider == ModelProvider.OPENAI:
            client = self._clients.get(ModelProvider.OPENAI)
            if client:
                async for chunk in self._stream_openai(client, model, prompt, config, system_prompt):
                    yield chunk
                return
        
        # Fallback to non-streaming
        text, _ = self.generate(prompt, model, config, system_prompt)
        yield text
    
    async def _stream_openai(
        self,
        client,
        model: str,
        prompt: str,
        config: ModelConfig,
        system_prompt: Optional[str],
    ) -> AsyncIterator[str]:
        """Stream using OpenAI API"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self._total_requests,
            "total_cost": round(self._total_cost, 4),
            "total_tokens": self._total_tokens,
            "available_providers": [p.value for p in self._clients.keys() if isinstance(p, ModelProvider)],
        }


# === Provider Clients ===

class _OllamaClient:
    """Simple Ollama API client for local inference"""
    
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    def generate(self, model: str, prompt: str, config: ModelConfig) -> str:
        """Call Ollama API"""
        import urllib.request
        import urllib.error
        
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
                "top_p": config.top_p,
            }
        }
        
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result.get("response", "")
        except urllib.error.URLError as e:
            logger.warning(f"Ollama not available: {e}")
            return f"[Ollama not running at {self.base_url}. Install: curl -fsSL https://ollama.com/install.sh | sh]"
    
    def list_models(self) -> List[str]:
        """List available models"""
        import urllib.request
        
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                return [m["name"] for m in result.get("models", [])]
        except Exception:
            return []


def create_brain(
    default_model: str = "llama3",
    prefer_free: bool = True,
) -> Brain:
    """
    Create a Brain with specified configuration.
    
    Example:
        brain = create_brain(default_model="llama3", prefer_free=True)
    """
    brain = Brain(default_model=default_model)
    return brain
