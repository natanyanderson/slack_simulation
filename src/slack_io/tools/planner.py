"""
Multi-step planning for tool execution.
GPT-4o can plan multi-step tool calls natively, but this module provides
helpers and system prompts to guide the planning process.
"""
from typing import List, Dict, Any, Optional, Tuple
from .config import TOOL_CONFIG
from .tool_definitions import TOOL_DEFINITIONS

# System prompt enhancements for multi-step planning
PLANNING_SYSTEM_PROMPT = """You have access to Slack read-only tools. When answering questions:

1. **Channel Resolution**: If the user mentions a channel by name (e.g., "#frontend"), first call list_channels 
   to find the channel ID, then use that ID in other calls.

2. **User Resolution**: If you need user information but only have a name, use search_messages or list_users 
   to find the user ID first.

3. **Multi-step Queries**: For questions about messages, you may need to:
   - First: list_channels (to find channel ID if channel name is given)
   - Then: get_channel_history (to get messages)
   - Then: get_user_info (to resolve user IDs to names if needed)

4. **Search Strategy**: 
   - **IMPORTANT**: The search_messages API requires a user token and may fail with bot tokens.
   - If search_messages fails, use an alternative approach: list_channels to find relevant channels, 
     then use get_channel_history on those channels to search manually
   - For search queries, try search_messages first, but if it fails with "not_allowed_token_type" 
     or "missing_scope", fall back to searching specific channels using get_channel_history
   
   **Search Query Tips**:
   - For exact phrases (like "prioritizing the payment gateway tests"), the system will automatically 
     wrap them in quotes for better matching
   - For keyword searches, use space-separated terms
   - Use modifiers: 'from:@user' for specific users, 'in:#channel' for specific channels
   - After getting search results, validate that they're relevant to the user's question
   
   **Alternative Search Method** (when search_messages fails):
   - Use list_channels to find channels that might contain the information
   - Use get_channel_history on those channels to search for messages containing the keywords
   - This works with bot tokens and is more reliable
   - **CRITICAL**: After getting channel history, you MUST filter messages to only include those 
     that actually contain the search keywords. Do NOT return all messages - only return messages 
     that match the user's query. If no messages match, report that clearly.

5. **Thread Access**: For thread-related questions, you need:
   - Channel ID (from list_channels if needed)
   - Thread timestamp (ts) from the parent message
   - Then: get_thread_replies to get all replies

Plan your tool calls efficiently - minimize API calls while getting complete answers.
Use the tools available to you, and call them in the correct order based on dependencies.
"""


def get_planning_prompt() -> str:
    """Get the planning system prompt."""
    return PLANNING_SYSTEM_PROMPT


def validate_plan(planned_tools: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate a planned sequence of tool calls.
    Returns: (is_valid, error_message)
    """
    max_steps = TOOL_CONFIG["planning"]["max_steps"]
    
    if len(planned_tools) > max_steps:
        return False, f"Plan exceeds maximum steps ({max_steps}). Please simplify your query."
    
    # Check if all tools are valid
    from .tool_definitions import is_valid_tool
    for tool in planned_tools:
        if not is_valid_tool(tool):
            return False, f"Invalid tool: {tool}"
    
    return True, None


def suggest_next_tool(
    current_tools: List[str],
    user_query: str,
    available_data: Dict[str, Any]
) -> Optional[str]:
    """
    Suggest the next tool to call based on current state.
    This is a simple heuristic - GPT-4o's native planning is usually better.
    """
    # If we have channel name but no ID, suggest list_channels
    if "#" in user_query and not available_data.get("channel_id"):
        if "list_channels" not in current_tools:
            return "list_channels"
    
    # If we have channel ID but no messages, suggest get_channel_history
    if available_data.get("channel_id") and not available_data.get("messages"):
        if "get_channel_history" not in current_tools:
            return "get_channel_history"
    
    # If user query contains "search" or "find", suggest search_messages
    if any(word in user_query.lower() for word in ["search", "find", "look for"]):
        if "search_messages" not in current_tools:
            return "search_messages"
    
    return None


def format_tool_results_for_next_step(
    tool_name: str,
    result: Dict[str, Any],
    previous_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format tool results to help with next step planning.
    Extracts useful data that might be needed for subsequent tool calls.
    """
    formatted = previous_data.copy()
    
    if tool_name == "list_channels" and result.get("success"):
        channels = result.get("data", {}).get("channels", [])
        # Extract channel name -> ID mappings
        formatted["channels"] = {
            ch.get("name"): ch.get("id")
            for ch in channels
            if ch.get("name") and ch.get("id")
        }
    
    elif tool_name == "get_channel_history" and result.get("success"):
        messages = result.get("data", {}).get("messages", [])
        formatted["messages"] = messages
        # Extract user IDs that might need resolution
        user_ids = set()
        for msg in messages:
            if msg.get("user"):
                user_ids.add(msg["user"])
        formatted["user_ids_to_resolve"] = list(user_ids)
    
    elif tool_name == "get_user_info" and result.get("success"):
        user = result.get("data", {}).get("user", {})
        user_id = user.get("id")
        if user_id:
            formatted.setdefault("resolved_users", {})[user_id] = user
    
    elif tool_name == "search_messages" and result.get("success"):
        messages_data = result.get("data", {}).get("messages", {})
        matches = messages_data.get("matches", [])
        formatted["search_results"] = matches
        # Extract channel IDs from search results
        channel_ids = set()
        for match in matches:
            if match.get("channel", {}).get("id"):
                channel_ids.add(match["channel"]["id"])
        formatted["channel_ids_from_search"] = list(channel_ids)
    
    return formatted

