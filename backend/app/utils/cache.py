"""
Redis-backed cache with in-memory fallback.
Used for download tokens and other temporary data.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Redis client (lazy initialized)
_redis_client = None
_redis_available = None


def _get_redis():
    """Get Redis client, initializing if needed."""
    global _redis_client, _redis_available

    if _redis_available is False:
        return None

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()
    if not settings.redis_url:
        logger.info("Redis URL not configured, using in-memory fallback")
        _redis_available = False
        return None

    try:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis connection established")
        _redis_available = True
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
        _redis_available = False
        return None


# In-memory fallback storage
_memory_store: dict[str, dict] = {}


def _cleanup_expired_memory():
    """Remove expired entries from memory store."""
    now = datetime.utcnow().timestamp()
    expired = [k for k, v in _memory_store.items() if v.get("_expires_at", float("inf")) < now]
    for k in expired:
        del _memory_store[k]


class Cache:
    """Cache abstraction with Redis backend and in-memory fallback."""

    def __init__(self, prefix: str = ""):
        """
        Initialize cache with optional key prefix.

        Args:
            prefix: Prefix for all keys (e.g., "download_token:")
        """
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Build full key with prefix."""
        return f"{self.prefix}{key}"

    def set(self, key: str, value: Any, ttl_seconds: int = 600) -> bool:
        """
        Set a value with TTL.

        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default 10 minutes)

        Returns:
            True if successful
        """
        full_key = self._key(key)
        redis_client = _get_redis()

        if redis_client:
            try:
                redis_client.setex(full_key, ttl_seconds, json.dumps(value))
                return True
            except Exception as e:
                logger.error(f"Redis set failed: {e}")

        # Fallback to memory
        _cleanup_expired_memory()
        _memory_store[full_key] = {
            "value": value,
            "_expires_at": datetime.utcnow().timestamp() + ttl_seconds,
        }
        return True

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value.

        Args:
            key: Cache key

        Returns:
            Value if exists and not expired, None otherwise
        """
        full_key = self._key(key)
        redis_client = _get_redis()

        if redis_client:
            try:
                data = redis_client.get(full_key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.error(f"Redis get failed: {e}")

        # Fallback to memory
        _cleanup_expired_memory()
        entry = _memory_store.get(full_key)
        if entry:
            return entry.get("value")
        return None

    def delete(self, key: str) -> bool:
        """
        Delete a value.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        full_key = self._key(key)
        redis_client = _get_redis()

        if redis_client:
            try:
                redis_client.delete(full_key)
                return True
            except Exception as e:
                logger.error(f"Redis delete failed: {e}")

        # Fallback to memory
        if full_key in _memory_store:
            del _memory_store[full_key]
        return True

    def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if exists and not expired
        """
        return self.get(key) is not None


# Pre-configured cache instances
download_token_cache = Cache(prefix="download_token:")
