"""
Configuration for read-only Slack API tools.
"""
import os
from typing import Dict, Any

ALLOWLIST_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'read_only_methods.json'
)

TOOL_CONFIG: Dict[str, Any] = {
    "idempotency": {  # Fixed typo: was "idemptotency"
        "enabled": True,
        "ttl_seconds": 300,
        "cache_size": 1000,
    },
    "truncation": {
        "max_items": 50,
        "max_tokens": 2000,
        "strategy": "smart"
    },
    "planning": {
        "max_steps": 5,
        "enable_explicit_planning": False
    },
    "logging": {
        "enabled": True,
        "log_level": "INFO",
        "log_file": "tool_calls.log",
        "log_format": "json"
    },
    "rate_limiting": {
        "cooldown": 1.1,
        "retry_after_429": True,
    },
    "pagination": {
        "max_pages": 10,
        "default_limit": 50,
        "max_limit": 200,
    }
}

DAY_ONE_TOOLS = [
    "conversations.list",
    "conversations.history",
    "conversations.members",
    "conversations.replies",
    "users.info",
    "users.list",
    "search.messages",
    "team.info"  # Fixed: was "teams.info"
]

SLACK_LIMITS = {
    "conversations.list": {"limit": 1000},
    "conversations.history": {"limit": 200},
    "conversations.members": {"limit": 1000},
    "search.messages": {"count": 100},
    "users.list": {"limit": 200}
}

def load_allowlist() -> Dict[str, Any]:
    """Load the read-only methods allowlist from JSON file."""
    import json
    try:
        with open(ALLOWLIST_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback: return empty allowlist if file not found
        return {"methods": []}

