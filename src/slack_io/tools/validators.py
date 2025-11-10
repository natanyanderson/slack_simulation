"""
Parameter validation for Slack API tool calls.
"""
import re
from typing import Dict, Any, Optional, Tuple
from .config import SLACK_LIMITS

# Channel ID format: C[0-9A-Z]+ (e.g., C1234567890)
CHANNEL_ID_PATTERN = re.compile(r'^C[0-9A-Z]+$')
# User ID format: U[0-9A-Z]+ (e.g., U1234567890)
USER_ID_PATTERN = re.compile(r'^U[0-9A-Z]+$')
# Timestamp format: digits.digits (e.g., 1730071234.567890)
TIMESTAMP_PATTERN = re.compile(r'^\d{10,}\.\d{1,6}$')


def validate_channel_id(channel_id: str) -> Tuple[bool, Optional[str]]:
    """Validate Slack channel ID format."""
    if not channel_id:
        return False, "Channel ID is required"
    if not CHANNEL_ID_PATTERN.match(channel_id):
        return False, f"Invalid channel ID format: {channel_id}"
    return True, None


def validate_user_id(user_id: str) -> Tuple[bool, Optional[str]]:
    """Validate Slack user ID format."""
    if not user_id:
        return False, "User ID is required"
    if not USER_ID_PATTERN.match(user_id):
        return False, f"Invalid user ID format: {user_id}"
    return True, None


def validate_timestamp(ts: str) -> Tuple[bool, Optional[str]]:
    """Validate Slack timestamp format."""
    if not ts:
        return False, "Timestamp is required"
    if not TIMESTAMP_PATTERN.match(ts):
        return False, f"Invalid timestamp format: {ts}"
    return True, None


def validate_limit(limit: int, endpoint: str, default: int = 50) -> Tuple[int, Optional[str]]:
    """Validate and normalize limit parameter."""
    if limit is None:
        return default, None
    
    if limit < 1:
        return default, "Limit must be >= 1, using default"
    
    max_limit = SLACK_LIMITS.get(endpoint, {}).get("limit", 200)
    if limit > max_limit:
        return max_limit, f"Limit exceeds max ({max_limit}), capped"
    
    return limit, None


def validate_tool_params(tool_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate parameters for a specific tool.
    Returns: (is_valid, error_message, sanitized_params)
    """
    sanitized = params.copy()
    errors = []
    
    # Validate based on tool name
    if tool_name == "list_channels":
        if "limit" in params:
            limit, err = validate_limit(params["limit"], "conversations.list")
            sanitized["limit"] = limit
            if err:
                errors.append(err)
    
    elif tool_name == "get_channel_history":
        if "channel" in params:
            valid, err = validate_channel_id(params["channel"])
            if not valid:
                errors.append(err)
        
        if "limit" in params:
            limit, err = validate_limit(params["limit"], "conversations.history")
            sanitized["limit"] = limit
            if err:
                errors.append(err)
    
    elif tool_name == "get_user_info":
        if "user" in params:
            valid, err = validate_user_id(params["user"])
            if not valid:
                errors.append(err)
    
    # Add more tool validations as needed
    
    if errors:
        return False, "; ".join(errors), sanitized
    
    return True, None, sanitized
