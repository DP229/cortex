"""
NeuronMesh Memory Redis - Redis Integration

Provides Redis-backed memory for distributed, multi-agent scenarios.
"""

import os
import json
import time
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RedisMemory:
    """
    Redis-backed memory for distributed multi-agent scenarios.
    
    Features:
    - Distributed memory across agents
    - Pub/sub for real-time sync
    - TTL support for ephemeral memories
    - Sorted sets for time-based retrieval
    
    Requires: pip install redis
    
    Example:
        memory = RedisMemory()
        memory.add("User preference", entry_type="preference")
        
        # Another agent can access same memory
        results = memory.retrieve("preference")
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = 6379,
        db: int = 0,
        password: str = None,
        prefix: str = "cortex:",
        ttl: int = 86400,  # 24 hours default TTL
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        self.ttl = ttl
        self._redis = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            import redis
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            # Test connection
            self._redis.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except ImportError:
            logger.warning("redis package not installed. Run: pip install redis")
            self._redis = None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._redis = None
    
    def _key(self, *parts) -> str:
        """Generate Redis key with prefix"""
        return self.prefix + ":".join(str(p) for p in parts)
    
    def add(
        self,
        content: str,
        entry_type: str = "fact",
        agent_id: str = None,
        ttl: int = None,
    ) -> Dict[str, Any]:
        """Add a memory to Redis"""
        if not self._redis:
            return {"error": "Redis not connected"}
        
        import uuid
        memory_id = str(uuid.uuid4())[:16]
        
        memory = {
            "id": memory_id,
            "content": content,
            "entry_type": entry_type,
            "agent_id": agent_id,
            "created_at": time.time(),
            "access_count": 0,
        }
        
        # Store memory
        key = self._key("memory", memory_id)
        self._redis.set(key, json.dumps(memory))
        
        # Set TTL
        memory_ttl = ttl or self.ttl
        self._redis.expire(key, memory_ttl)
        
        # Add to index by type
        self._redis.zadd(
            self._key("index", entry_type),
            {memory_id: time.time()}
        )
        
        # Add to agent index if specified
        if agent_id:
            self._redis.zadd(
                self._key("agent", agent_id),
                {memory_id: time.time()}
            )
        
        return memory
    
    def retrieve(
        self,
        query: str,
        entry_type: str = None,
        agent_id: str = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories from Redis"""
        if not self._redis:
            return []
        
        results = []
        
        if entry_type:
            # Get by type
            memory_ids = self._redis.zrevrange(
                self._key("index", entry_type),
                0,
                limit - 1
            )
            
            for memory_id in memory_ids:
                key = self._key("memory", memory_id)
                data = self._redis.get(key)
                if data:
                    results.append(json.loads(data))
        
        elif agent_id:
            # Get by agent
            memory_ids = self._redis.zrevrange(
                self._key("agent", agent_id),
                0,
                limit - 1
            )
            
            for memory_id in memory_ids:
                key = self._key("memory", memory_id)
                data = self._redis.get(key)
                if data:
                    results.append(json.loads(data))
        
        else:
            # Get recent
            keys = self._redis.keys(self._key("memory", "*"))
            for key in keys[:limit]:
                data = self._redis.get(key)
                if data:
                    results.append(json.loads(data))
        
        return results
    
    def delete(self, memory_id: str):
        """Delete a memory"""
        if not self._redis:
            return
        
        key = self._key("memory", memory_id)
        data = self._redis.get(key)
        
        if data:
            memory = json.loads(data)
            
            # Remove from type index
            self._redis.zrem(self._key("index", memory["entry_type"]), memory_id)
            
            # Remove from agent index
            if memory.get("agent_id"):
                self._redis.zrem(self._key("agent", memory["agent_id"]), memory_id)
        
        self._redis.delete(key)
    
    def clear(self, entry_type: str = None, agent_id: str = None):
        """Clear memories"""
        if not self._redis:
            return
        
        if entry_type:
            # Get all IDs and delete
            memory_ids = self._redis.zrange(self._key("index", entry_type), 0, -1)
            for memory_id in memory_ids:
                self._redis.delete(self._key("memory", memory_id))
            self._redis.delete(self._key("index", entry_type))
        
        elif agent_id:
            memory_ids = self._redis.zrange(self._key("agent", agent_id), 0, -1)
            for memory_id in memory_ids:
                self._redis.delete(self._key("memory", memory_id))
            self._redis.delete(self._key("agent", agent_id))
        
        else:
            # Clear all
            keys = self._redis.keys(self._key("*"))
            if keys:
                self._redis.delete(*keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        if not self._redis:
            return {"status": "disconnected"}
        
        memory_keys = self._redis.keys(self._key("memory", "*"))
        
        return {
            "total_memories": len(memory_keys),
            "host": self.host,
            "port": self.port,
            "db": self.db,
        }


def create_redis_memory(**kwargs) -> RedisMemory:
    """Create Redis memory instance"""
    return RedisMemory(**kwargs)
