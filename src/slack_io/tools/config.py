"""
Configuration for read-only Slack API tools.
"""
import os
from typing import Dict, Any, Optional
from .workspace_config import get_workspace_paths

ALLOWLIST_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'read_only_methods.json'
)

def _get_json_export_path() -> str:
    """Get JSON export path from workspace config or environment variable."""
    # Try workspace config first
    workspace_paths = get_workspace_paths()
    if workspace_paths.get("export_path"):
        return workspace_paths["export_path"]
    
    # Fallback to environment variable
    return os.getenv(
        "SLACK_JSON_EXPORT_PATH",
        "/Users/jay./Downloads/Formula Electric at Berkeley Slack export Sep 1 2025 - Nov 9 2025"
    )

def _get_compiled_messages_path() -> str:
    """Get compiled messages path from workspace config or environment variable."""
    # Try workspace config first
    workspace_paths = get_workspace_paths()
    if workspace_paths.get("compiled_messages_path"):
        return workspace_paths["compiled_messages_path"]
    
    # Fallback to environment variable
    return os.getenv(
        "SLACK_COMPILED_MESSAGES_PATH",
        "/Users/jay./Desktop/Algoverse/SlackBench/slackbench_real_sim/compiled_messages.json"
    )

def get_data_source_type() -> str:
    """Get data source type dynamically from environment variable."""
    return os.getenv("SLACK_DATA_SOURCE", "api")

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
    },
    "data_source": {
        # Note: "type" is read dynamically via get_data_source_type() function
        "json": {
            "export_path": _get_json_export_path(),
            "compiled_messages_path": _get_compiled_messages_path(),
            "cache_size": 1000,
        },
        "api": {
            "rate_limiting": {
                "cooldown": 1.1,
                "retry_after_429": True,
            },
            "retry_config": {
                "max_retries": 3,
                "backoff_factor": 1.0,
            }
        }
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

