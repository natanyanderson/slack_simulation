"""
Configuration for read-only Slack API tools.
"""
import os
from typing import Dict, Any, Optional
from .workspace_config import get_workspace_paths

# Get project root (4 levels up from this file: tools -> read_only -> slack_io -> src -> project_root)
_config_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_config_dir))))
ALLOWLIST_PATH = os.path.join(_project_root, 'read_only_methods.json')

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

def get_max_iterations() -> int:
    """Get max_iterations dynamically from environment variable."""
    return int(os.getenv("MAX_ITERATIONS", "10"))

TOOL_CONFIG: Dict[str, Any] = {
    "idempotency": {  # Fixed typo: was "idemptotency"
        "enabled": True,
        "ttl_seconds": 300,
        "cache_size": 1000,
    },
    "truncation": {
        "max_items": 200,  # Increased to allow more channels
        "max_tokens": 2000,
        "strategy": "smart"
    },
    "planning": {
        "max_steps": 10,  # Maximum steps for explicit planning validation
        # Note: max_iterations is read dynamically to allow .env changes without restart
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Log the path being used for debugging
        logger.debug(f"Loading allowlist from: {ALLOWLIST_PATH}")
        logger.debug(f"Allowlist file exists: {os.path.exists(ALLOWLIST_PATH)}")
        
        with open(ALLOWLIST_PATH, 'r') as f:
            allowlist = json.load(f)
            methods_count = len(allowlist.get("methods", []))
            logger.info(f"Loaded allowlist with {methods_count} methods from {ALLOWLIST_PATH}")
            return allowlist
    except FileNotFoundError:
        # Fallback: return empty allowlist if file not found
        logger.error(f"Allowlist file not found at: {ALLOWLIST_PATH}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"Config file location: {os.path.abspath(__file__)}")
        return {"methods": []}
    except Exception as e:
        logger.error(f"Error loading allowlist from {ALLOWLIST_PATH}: {e}")
        return {"methods": []}

