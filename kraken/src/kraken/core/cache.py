"""
Cache para KRAKEN v3.0.
Soporta memoria (dict) o Redis (opcional).
"""
import time
import json
import os
from typing import Any, Optional


class MemoryCache:
    """Cache en memoria con TTL."""
    
    def __init__(self, expiry: int = 3600):
        self._cache = {}
        self._expiry = expiry
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._expiry:
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.time())
    
    def delete(self, key: str) -> None:
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        self._cache.clear()
    
    def stats(self) -> dict:
        return {"items": len(self._cache), "expiry": self._expiry}


class RedisCache:
    """Cache en Redis (opcional, requiere redis instalado)."""
    
    def __init__(self, url: str = "redis://localhost:6379/0", expiry: int = 3600):
        import redis
        self._redis = redis.from_url(url)
        self._expiry = expiry
    
    def get(self, key: str) -> Optional[Any]:
        data = self._redis.get(key)
        return json.loads(data) if data else None
    
    def set(self, key: str, value: Any) -> None:
        self._redis.setex(key, self._expiry, json.dumps(value))
    
    def delete(self, key: str) -> None:
        self._redis.delete(key)
    
    def clear(self) -> None:
        self._redis.flushdb()
    
    def stats(self) -> dict:
        return {"items": self._redis.dbsize(), "expiry": self._expiry}


# Singleton
_cache_instance = None


def cache(cache_type: str = "memory", redis_url: str = "redis://localhost:6379/0",
          expiry: int = 3600):
    """Factory de cache."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance
    
    if cache_type == "redis":
        try:
            _cache_instance = RedisCache(url=redis_url, expiry=expiry)
        except ImportError:
            _cache_instance = MemoryCache(expiry=expiry)
    else:
        _cache_instance = MemoryCache(expiry=expiry)
    
    return _cache_instance
