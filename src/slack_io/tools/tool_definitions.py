"""
OpenAI function/tool definitions for read-only Slack API tools.
These schemas define what tools GPT-4o can call.
"""
from typing import List, Dict, Any

# Tool definitions in OpenAI function calling format
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all channels in the workspace. Use this to discover channel names and IDs, or to find channels by type (public, private, DMs, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "types": {
                        "type": "string",
                        "description": "Comma-separated list of channel types: public_channel, private_channel, mpim, im",
                        "enum": ["public_channel", "private_channel", "mpim", "im"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of channels to return (default: 200, max: 1000)",
                        "minimum": 1,
                        "maximum": 1000
                    },
                    "exclude_archived": {
                        "type": "boolean",
                        "description": "Set to true to exclude archived channels (default: false)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_history",
            "description": "Get message history from a channel. Use this to read messages in a channel. You must know the channel ID (use list_channels first if you only have a channel name).",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel ID (e.g., C1234567890). Required."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default: 50, max: 200)",
                        "minimum": 1,
                        "maximum": 200
                    },
                    "oldest": {
                        "type": "string",
                        "description": "Only messages after this Unix timestamp (e.g., '1609459200.000000')"
                    },
                    "latest": {
                        "type": "string",
                        "description": "Only messages before this Unix timestamp (e.g., '1609545600.000000')"
                    },
                    "inclusive": {
                        "type": "boolean",
                        "description": "Include messages with oldest or latest timestamps in results (default: false)"
                    }
                },
                "required": ["channel"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_members",
            "description": "Get list of members in a channel. Use this to see who is in a channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel ID (e.g., C1234567890). Required."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of members to return (default: 50, max: 1000)",
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["channel"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_thread_replies",
            "description": "Get replies in a thread. Use this to read threaded messages. You need the channel ID and the thread timestamp (ts) of the parent message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel ID (e.g., C1234567890). Required."
                    },
                    "ts": {
                        "type": "string",
                        "description": "Thread timestamp (e.g., '1609459200.123456') of the parent message. Required."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of replies to return (default: 50, max: 200)",
                        "minimum": 1,
                        "maximum": 200
                    },
                    "oldest": {
                        "type": "string",
                        "description": "Only replies after this Unix timestamp"
                    },
                    "latest": {
                        "type": "string",
                        "description": "Only replies before this Unix timestamp"
                    }
                },
                "required": ["channel", "ts"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "Get information about a user. Use this to look up user details by user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "User ID (e.g., U1234567890). Required."
                    },
                    "include_locale": {
                        "type": "boolean",
                        "description": "Set to true to include locale information (default: false)"
                    }
                },
                "required": ["user"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_users",
            "description": "List all users in the workspace. Use this to discover users and their IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of users to return (default: 50, max: 200)",
                        "minimum": 1,
                        "maximum": 200
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for fetching next page"
                    },
                    "include_locale": {
                        "type": "boolean",
                        "description": "Set to true to include locale information (default: false)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_messages",
            "description": "⚠️ LIMITATION: This tool requires a user token and may not work with bot tokens. If it fails, use get_channel_history on specific channels instead. Search for messages in the workspace. IMPORTANT: For exact phrase matching (3+ words), wrap phrases in double quotes. The system will automatically optimize queries for best results. Examples: '\"exact phrase\"', 'payment gateway', 'from:@username', 'in:#channel'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query. For exact phrases (3+ words like 'prioritizing the payment gateway tests'), the system will automatically wrap them in quotes for better matching. For keywords, use space-separated terms. Supports modifiers: 'from:@user', 'in:#channel'. Examples: '\"payment gateway tests\"', 'deployment error', 'from:@alice in:#frontend'. The system will automatically optimize your query for best results."
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order: 'score' (relevance) or 'timestamp' (date)",
                        "enum": ["score", "timestamp"]
                    },
                    "sort_dir": {
                        "type": "string",
                        "description": "Sort direction: 'asc' (ascending) or 'desc' (descending)",
                        "enum": ["asc", "desc"]
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20, max: 100)",
                        "minimum": 1,
                        "maximum": 100
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number for pagination (default: 1)",
                        "minimum": 1
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_info",
            "description": "Get workspace/team information. Use this to get details about the Slack workspace.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


# Map tool names to Slack API endpoints
TOOL_TO_ENDPOINT: Dict[str, str] = {
    "list_channels": "conversations.list",
    "get_channel_history": "conversations.history",
    "get_channel_members": "conversations.members",
    "get_thread_replies": "conversations.replies",
    "get_user_info": "users.info",
    "list_users": "users.list",
    "search_messages": "search.messages",
    "get_team_info": "team.info"
}


# Map tool names to implementation functions
# This will be used by the router to call the correct function
def _get_implementation_path():
    """Get implementation path based on config."""
    from .config import get_data_source_type
    data_source = get_data_source_type()
    
    if data_source == "json":
        # Use JSON implementations
        return {
            "list_channels": ("implementations.json.conversations", "list_channels"),
            "get_channel_history": ("implementations.json.conversations", "get_channel_history"),
            "get_channel_members": ("implementations.json.conversations", "get_channel_members"),
            "get_thread_replies": ("implementations.json.conversations", "get_thread_replies"),
            "get_user_info": ("implementations.json.users", "get_user_info"),
            "list_users": ("implementations.json.users", "list_users"),
            "search_messages": ("implementations.json.search", "search_messages"),
            "get_team_info": ("implementations.json.files", "get_team_info")
        }
    else:
        # Use API implementations (default)
        return {
            "list_channels": ("implementations.conversations", "list_channels"),
            "get_channel_history": ("implementations.conversations", "get_channel_history"),
            "get_channel_members": ("implementations.conversations", "get_channel_members"),
            "get_thread_replies": ("implementations.conversations", "get_thread_replies"),
            "get_user_info": ("implementations.users", "get_user_info"),
            "list_users": ("implementations.users", "list_users"),
            "search_messages": ("implementations.search", "search_messages"),
            "get_team_info": ("implementations.files", "get_team_info")
        }

# Cache the implementations dict
_TOOL_IMPLEMENTATIONS_CACHE = None

def _get_tool_implementations():
    """Get cached tool implementations, refreshing if needed."""
    global _TOOL_IMPLEMENTATIONS_CACHE
    # For now, always refresh to pick up config changes
    # Could optimize to cache and invalidate on config change
    _TOOL_IMPLEMENTATIONS_CACHE = _get_implementation_path()
    return _TOOL_IMPLEMENTATIONS_CACHE

# Expose as dict-like access for backwards compatibility
# This is a callable that returns the dict
class _ToolImplementationsDict:
    """Dict-like wrapper for tool implementations."""
    def get(self, key, default=None):
        return _get_tool_implementations().get(key, default)
    
    def __getitem__(self, key):
        return _get_tool_implementations()[key]
    
    def __contains__(self, key):
        return key in _get_tool_implementations()
    
    def keys(self):
        return _get_tool_implementations().keys()
    
    def values(self):
        return _get_tool_implementations().values()
    
    def items(self):
        return _get_tool_implementations().items()

TOOL_IMPLEMENTATIONS = _ToolImplementationsDict()


def get_tool_definition(tool_name: str) -> Dict[str, Any]:
    """Get tool definition by name."""
    for tool in TOOL_DEFINITIONS:
        if tool["function"]["name"] == tool_name:
            return tool
    raise ValueError(f"Tool {tool_name} not found")


def get_endpoint(tool_name: str) -> str:
    """Get Slack API endpoint for a tool."""
    return TOOL_TO_ENDPOINT.get(tool_name, "")


def get_implementation(tool_name: str):
    """Get implementation module and function name for a tool."""
    implementations = _get_tool_implementations()
    return implementations.get(tool_name, (None, None))


def is_valid_tool(tool_name: str) -> bool:
    """Check if a tool name is valid."""
    return tool_name in TOOL_TO_ENDPOINT

