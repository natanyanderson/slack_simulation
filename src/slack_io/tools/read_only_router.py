"""
Read-only Slack API tool router.
This is the main entry point for executing read-only Slack API tools.
It handles validation, idempotency, logging, error handling, and response formatting.
"""
import time
import uuid
import importlib
import logging
from typing import Dict, Any, Optional, Tuple, List
from .config import TOOL_CONFIG, load_allowlist

logger = logging.getLogger(__name__)
from .tool_definitions import (
    TOOL_DEFINITIONS,
    get_tool_definition,
    get_endpoint,
    get_implementation,
    is_valid_tool
)
from .validators import validate_tool_params
from .error_handler import create_error_response
from .logging import log_tool_call_start, log_tool_call_complete
from .idempotency import (
    generate_request_fingerprint,
    check_idempotency,
    cache_response
)
from .response_truncator import truncate_response
from .cache import get_channel_id


class ReadOnlyRouter:
    """
    Router for read-only Slack API tools.
    Handles tool execution with validation, logging, idempotency, and error handling.
    """
    
    def __init__(self):
        """Initialize the router."""
        self.allowlist = load_allowlist()
        self.allowed_methods = set(self.allowlist.get("methods", []))
    
    def is_allowed(self, endpoint: str) -> bool:
        """Check if an endpoint is in the allowlist."""
        return endpoint in self.allowed_methods
    
    def resolve_channel_name(self, channel_name: str) -> Optional[str]:
        """
        Resolve channel name to channel ID.
        Uses cache first, then falls back to list_channels if needed.
        """
        # Remove # if present
        channel_name = channel_name.lstrip("#")
        
        # Check cache
        channel_id = get_channel_id(channel_name)
        if channel_id:
            return channel_id
        
        # TODO: Could call list_channels here to populate cache
        # For now, return None and let the tool handle it
        return None
    
    def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_id: str,
        channel_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool call.
        
        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            user_id: Slack user ID making the request
            channel_id: Channel ID where the request came from (optional)
            request_id: Request ID for tracking (optional)
        
        Returns:
            Tool execution result
        """
        # Generate request ID if not provided
        if not request_id:
            request_id = str(uuid.uuid4())[:8]
        
        # Validate tool name
        if not is_valid_tool(tool_name):
            return create_error_response(
                "invalid_tool",
                f"Tool '{tool_name}' is not available",
                tool_name
            )
        
        # Get endpoint and implementation
        endpoint = get_endpoint(tool_name)
        if not endpoint:
            return create_error_response(
                "invalid_tool",
                f"Tool '{tool_name}' has no associated endpoint",
                tool_name
            )
        
        # Check allowlist
        if not self.is_allowed(endpoint):
            return create_error_response(
                "not_allowed",
                f"Endpoint '{endpoint}' is not in the allowlist",
                tool_name
            )
        
        # Validate parameters
        is_valid, error_msg, sanitized_params = validate_tool_params(tool_name, params)
        if not is_valid:
            return create_error_response(
                "invalid_parameters",
                error_msg or "Invalid parameters",
                tool_name
            )
        
        # Check idempotency
        fingerprint = generate_request_fingerprint(user_id, tool_name, sanitized_params)
        is_duplicate, cached_response = check_idempotency(fingerprint)
        if is_duplicate and cached_response:
            # Return cached response
            log_tool_call_start(
                request_id, user_id, channel_id, tool_name, endpoint, sanitized_params
            )
            log_tool_call_complete(
                request_id, 0.0, True, None, 
                len(cached_response.get("data", {}).get("items", [])),
                1
            )
            return cached_response
        
        # Log tool call start
        log_tool_call_start(
            request_id, user_id, channel_id, tool_name, endpoint, sanitized_params
        )
        
        # Execute tool
        start_time = time.time()
        try:
            # Get implementation
            module_name, function_name = get_implementation(tool_name)
            if not module_name or not function_name:
                return create_error_response(
                    "implementation_not_found",
                    f"Implementation not found for tool '{tool_name}'",
                    tool_name
                )
            
            # PRINT: Show which implementation is being used
            print(f"[ROUTER] Using implementation: {module_name}.{function_name}")
            
            # Import and call implementation using relative import
            # module_name is like "implementations.conversations" or "implementations.json.conversations"
            # Handle both 'src.slack_io.tools' and 'slack_io.tools' package structures
            parts = module_name.split('.')
            if len(parts) == 2 or len(parts) == 3:
                # Get the current package (could be 'src.slack_io.tools' or 'slack_io.tools')
                current_package = __package__
                if not current_package:
                    # Fallback detection
                    import os
                    current_file = os.path.abspath(__file__)
                    if 'src' in current_file:
                        current_package = 'src.slack_io.tools'
                    else:
                        current_package = 'slack_io.tools'
                
                # Build relative import path
                if len(parts) == 2:
                    # .implementations.conversations
                    relative_path = f'.{parts[0]}.{parts[1]}'
                else:
                    # .implementations.json.conversations
                    relative_path = f'.{parts[0]}.{parts[1]}.{parts[2]}'
                
                # Import using importlib with relative path
                # This works whether package is 'src.slack_io.tools' or 'slack_io.tools'
                try:
                    module = importlib.import_module(relative_path, package=current_package)
                    tool_function = getattr(module, function_name)
                except (ImportError, ModuleNotFoundError) as e:
                    # If relative import fails, log and re-raise with better error message
                    logger.error(f"Failed to import {relative_path} from package {current_package}: {e}")
                    raise ImportError(
                        f"Could not import {module_name} from package {current_package}. "
                        f"Ensure the implementations module exists and is accessible."
                    ) from e
            else:
                raise ValueError(f"Invalid module name format: {module_name} (expected 2 or 3 parts, got {len(parts)})")
            
            # Handle channel name resolution if needed
            if "channel" in sanitized_params:
                channel_param = sanitized_params["channel"]
                # If it looks like a channel name (starts with #), try to resolve
                if channel_param.startswith("#"):
                    resolved_id = self.resolve_channel_name(channel_param)
                    if resolved_id:
                        sanitized_params["channel"] = resolved_id
                    else:
                        # Channel not in cache, tool will need to handle it
                        pass
            
            # Call the tool function
            result = tool_function(**sanitized_params)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Truncate response if needed
            if result.get("success") and result.get("data"):
                # Determine items key based on tool
                items_key = self._get_items_key(tool_name)
                if items_key:
                    items = result["data"].get(items_key)
                    if items is not None:
                        # Handle different response structures
                        if tool_name == "search_messages":
                            # Search results have a nested structure: messages.matches
                            if isinstance(items, dict) and "matches" in items:
                                matches = items["matches"]
                                truncatable_response = {
                                    "items": matches,
                                    "meta": result["data"].get("meta", {})
                                }
                                truncated = truncate_response(truncatable_response)
                                items["matches"] = truncated["items"]
                                result["data"]["meta"].update(truncated["meta"])
                        else:
                            # Standard list-based responses
                            if isinstance(items, list):
                                truncatable_response = {
                                    "items": items,
                                    "meta": result["data"].get("meta", {})
                                }
                                truncated = truncate_response(truncatable_response)
                                result["data"][items_key] = truncated["items"]
                                result["data"]["meta"].update(truncated["meta"])
            
            # Cache response for idempotency
            cache_response(fingerprint, result)
            
            # Log completion
            items_count = self._count_items(result, tool_name)
            log_tool_call_complete(
                request_id, duration_ms, result.get("success", False),
                result.get("error", {}).get("type") if not result.get("success") else None,
                items_count, 1
            )
            
            return result
            
        except Exception as e:
            # Unexpected error - log the full exception for debugging
            duration_ms = (time.time() - start_time) * 1000
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error executing tool {tool_name}: {str(e)}\n{error_traceback}")
            
            error_result = create_error_response(
                "execution_error",
                f"Unexpected error executing tool: {str(e)}",
                tool_name
            )
            log_tool_call_complete(
                request_id, duration_ms, False, "execution_error", 0, 1
            )
            return error_result
    
    def _get_items_key(self, tool_name: str) -> Optional[str]:
        """Get the key name for items in the response data."""
        item_keys = {
            "list_channels": "channels",
            "get_channel_history": "messages",
            "get_channel_members": "members",
            "get_thread_replies": "messages",
            "list_users": "users",
            "search_messages": "messages",  # Search returns {"messages": {"matches": [...]}}
            "get_team_info": None,  # Team info doesn't have a list of items
        }
        return item_keys.get(tool_name)
    
    def _count_items(self, result: Dict[str, Any], tool_name: str) -> int:
        """Count items in the result."""
        if not result.get("success") or not result.get("data"):
            return 0
        
        items_key = self._get_items_key(tool_name)
        if items_key:
            items = result["data"].get(items_key)
            if items is None:
                return 0
            if isinstance(items, list):
                return len(items)
            elif isinstance(items, dict):
                # For search results, might be a dict with matches
                if "matches" in items:
                    return len(items.get("matches", []))
                # Could also have a "total" field
                return items.get("total", 0)
        
        # Fallback: try to count any list in data
        data = result.get("data", {})
        for key, value in data.items():
            if isinstance(value, list):
                return len(value)
            elif isinstance(value, dict) and "matches" in value:
                return len(value.get("matches", []))
        
        return 0
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions for OpenAI function calling."""
        return TOOL_DEFINITIONS


# Global router instance
_router_instance: Optional[ReadOnlyRouter] = None


def get_router() -> ReadOnlyRouter:
    """Get the global router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ReadOnlyRouter()
    return _router_instance


def execute_tool(
    tool_name: str,
    params: Dict[str, Any],
    user_id: str,
    channel_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute a tool.
    """
    router = get_router()
    return router.execute_tool(tool_name, params, user_id, channel_id)

