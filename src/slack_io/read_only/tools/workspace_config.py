"""
Workspace configuration loader for JSON export paths.
Supports multiple workspaces via YAML/JSON config file.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Try to import yaml, but make it optional
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Default workspace name
DEFAULT_WORKSPACE = "default"

# Config file path (in project root)
CONFIG_FILE_YAML = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'workspace_config.yaml'
)
CONFIG_FILE_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'workspace_config.json'
)

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def load_workspace_config() -> Dict[str, Any]:
    """Load workspace configuration from YAML or JSON file."""
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    # Try YAML first, then JSON
    config_path = None
    if os.path.exists(CONFIG_FILE_YAML) and HAS_YAML:
        config_path = CONFIG_FILE_YAML
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _config_cache = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading YAML config: {e}")
            _config_cache = {}
    elif os.path.exists(CONFIG_FILE_YAML) and not HAS_YAML:
        print("Warning: YAML config file found but PyYAML not installed. Install with: pip install pyyaml")
    elif os.path.exists(CONFIG_FILE_JSON):
        config_path = CONFIG_FILE_JSON
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _config_cache = json.load(f)
        except Exception as e:
            print(f"Error loading JSON config: {e}")
            _config_cache = {}
    else:
        # No config file found, return empty
        _config_cache = {}
    
    return _config_cache


def get_workspace_paths(workspace_name: Optional[str] = None) -> Dict[str, str]:
    """
    Get export paths for a workspace.
    
    Args:
        workspace_name: Name of workspace (defaults to "default" or env var)
    
    Returns:
        Dict with 'export_path' and 'compiled_messages_path'
    """
    # Get workspace name from env var or use default
    if workspace_name is None:
        workspace_name = os.getenv("SLACK_WORKSPACE", DEFAULT_WORKSPACE)
    
    config = load_workspace_config()
    workspaces = config.get("workspaces", {})
    
    # Get workspace config
    workspace_config = workspaces.get(workspace_name)
    
    if not workspace_config:
        # Fallback to default if specified workspace not found
        if workspace_name != DEFAULT_WORKSPACE:
            workspace_config = workspaces.get(DEFAULT_WORKSPACE)
        
        # If still not found, return empty dict (will use env vars as fallback)
        if not workspace_config:
            return {}
    
    return {
        "export_path": workspace_config.get("export_path", ""),
        "compiled_messages_path": workspace_config.get("compiled_messages_path", "")
    }


def list_workspaces() -> list:
    """List all available workspace names."""
    config = load_workspace_config()
    return list(config.get("workspaces", {}).keys())

