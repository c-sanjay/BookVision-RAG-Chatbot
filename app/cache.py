"""
Simple caching layer with Redis support and in-memory fallback
"""
import json
import hashlib
from typing import Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .config import REDIS_URL, CACHE_TTL

class Cache:
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}  # Fallback in-memory cache
        
        if REDIS_AVAILABLE and REDIS_URL:
            try:
                self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                print("Redis cache connected")
            except Exception as e:
                print(f"Redis connection failed, using in-memory cache: {e}")
                self.redis_client = None
        else:
            print("Using in-memory cache (Redis not configured)")

    def _make_key(self, prefix: str, query: str) -> str:
        """Create a cache key from query"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"bookvision:{prefix}:{query_hash}"

    def get(self, prefix: str, query: str) -> Optional[dict]:
        """Get cached result"""
        key = self._make_key(prefix, query)
        
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                print(f"Cache get error: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        return None

    def set(self, prefix: str, query: str, value: dict, ttl: int = None):
        """Set cached result"""
        key = self._make_key(prefix, query)
        ttl = ttl or CACHE_TTL
        
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return
            except Exception as e:
                print(f"Cache set error: {e}")
        
        # Fallback to memory cache (simple TTL not implemented for memory)
        self.memory_cache[key] = value
        # Limit memory cache size
        if len(self.memory_cache) > 1000:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self.memory_cache.keys())[:100]
            for k in keys_to_remove:
                del self.memory_cache[k]

    def clear(self, prefix: str = None):
        """Clear cache (optionally by prefix)"""
        if self.redis_client:
            try:
                if prefix:
                    pattern = f"bookvision:{prefix}:*"
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                else:
                    self.redis_client.flushdb()
            except Exception as e:
                print(f"Cache clear error: {e}")
        
        if prefix:
            # Clear memory cache by prefix
            keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(f"bookvision:{prefix}:")]
            for k in keys_to_remove:
                del self.memory_cache[k]
        else:
            self.memory_cache.clear()

# Global cache instance
cache = Cache()

