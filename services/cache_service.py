from datetime import datetime, timedelta
import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_memory_cache: dict[str, dict[str, Any]] = {}


def get_cached(key: str) -> Any | None:
    """Retrieves an item from cache if it has not expired."""
    entry = _memory_cache.get(key)
    if not entry:
        return None

    if datetime.now() > entry["expires_at"]:
        del _memory_cache[key]
        return None

    return entry["value"]


def set_cached(key: str, value: Any, ttl_seconds: int = 120):
    """Sets a cache value with a TTL in seconds."""
    _memory_cache[key] = {
        "value": value,
        "expires_at": datetime.now() + timedelta(seconds=ttl_seconds),
    }


def clear_cache():
    """Flushes the in-memory cache."""
    _memory_cache.clear()


def ttl_cache(ttl_seconds: int = 120):
    """Decorator for caching async or sync function outputs by argument key."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_val = get_cached(key)
            if cached_val is not None:
                logger.debug("Cache hit for %s", key)
                return cached_val
            result = await func(*args, **kwargs)
            set_cached(key, result, ttl_seconds=ttl_seconds)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_val = get_cached(key)
            if cached_val is not None:
                logger.debug("Cache hit for %s", key)
                return cached_val
            result = func(*args, **kwargs)
            set_cached(key, result, ttl_seconds=ttl_seconds)
            return result

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
