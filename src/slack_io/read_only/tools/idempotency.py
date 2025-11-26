"""
Idempotency layer for tool calls.
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional, Tuple
from .cache import LRUCache
from .config import TOOL_CONFIG
from .logging import hash_params

# Idempotency cache
idempotency_cache = LRUCache(
    max_size=TOOL_CONFIG["idempotency"]["cache_size"],
    ttl_seconds=TOOL_CONFIG["idempotency"]["ttl_seconds"]
)


def generate_request_fingerprint(
    user_id: str,
    tool_name: str,
    params: Dict[str, Any],
    timestamp_window: int = 300  # 5 minutes
) -> str:
    """
    Generate a fingerprint for a request to detect duplicates.
    Uses a time window to group similar requests within the TTL period.
    """
    # Create a normalized representation
    normalized = {
        "user_id": user_id,
        "tool_name": tool_name,
        "params": params,
        "time_window": int(time.time() / timestamp_window)  # Group by 5-min windows
    }
    
    # Hash it
    fingerprint_str = json.dumps(normalized, sort_keys=True)
    fingerprint = hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    return fingerprint


def check_idempotency(fingerprint: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if this request was recently executed.
    Returns: (is_duplicate, cached_response)
    """
    if not TOOL_CONFIG["idempotency"]["enabled"]:
        return False, None
    
    cached_response = idempotency_cache.get(fingerprint)
    if cached_response:
        return True, cached_response
    
    return False, None


def cache_response(fingerprint: str, response: Dict[str, Any]):
    """Cache a response for idempotency."""
    if not TOOL_CONFIG["idempotency"]["enabled"]:
        return
    
    idempotency_cache.set(fingerprint, response)
