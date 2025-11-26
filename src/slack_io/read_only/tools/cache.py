"""
Caching layer for Slack channel and user data.
"""
import time
from typing import Dict, Optional, Any
from collections import OrderedDict
from .config import TOOL_CONFIG

# Cache configuration
CACHE_TTL = TOOL_CONFIG["idempotency"]["ttl_seconds"]
CACHE_SIZE = TOOL_CONFIG["idempotency"]["cache_size"]


class LRUCache:
    """Simple LRU cache with TTL support."""
    
    def __init__(self, max_size: int = CACHE_SIZE, ttl_seconds: int = CACHE_TTL):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            # Expired, remove it
            del self.cache[key]
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return entry["value"]
    
    def set(self, key: str, value: Any):
        """Set value in cache with current timestamp."""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
        else:
            # Add new entry
            if len(self.cache) >= self.max_size:
                # Remove oldest (first item)
                self.cache.popitem(last=False)
        
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()


# Global caches
channel_cache = LRUCache()  # channel_name -> channel_id
user_cache = LRUCache()     # user_id -> user_info
channel_id_cache = LRUCache()  # channel_id -> channel_info


def get_channel_id(channel_name: str) -> Optional[str]:
    """Get channel ID from cache by name."""
    return channel_cache.get(channel_name)


def set_channel_id(channel_name: str, channel_id: str):
    """Cache channel name to ID mapping."""
    channel_cache.set(channel_name, channel_id)


def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user info from cache."""
    return user_cache.get(user_id)


def set_user_info(user_id: str, user_info: Dict[str, Any]):
    """Cache user info."""
    user_cache.set(user_id, user_info)
