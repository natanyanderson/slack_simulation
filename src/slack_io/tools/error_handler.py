"""
Error handling and normalization for Slack API errors.
"""
from typing import Dict, Any, Optional
from slack_sdk.errors import SlackApiError

# Map Slack error codes to user-friendly messages
ERROR_MESSAGES = {
    "not_in_channel": "I'm not a member of that channel. Please add me to the channel first.",
    "channel_not_found": "Channel not found. Please check the channel name or ID.",
    "invalid_auth": "Authentication failed. Please check bot token.",
    "account_inactive": "The workspace or user account is inactive.",
    "missing_scope": "I don't have the required permissions for that action.",
    "rate_limited": "Rate limited. Please try again in a moment.",
    "invalid_cursor": "Invalid pagination cursor. Starting from the beginning.",
    "user_not_found": "User not found. Please check the user ID or email.",
    "not_authed": "Not authenticated. Please check bot configuration."
}

# Errors that should be retried
RETRIABLE_ERRORS = ["rate_limited", "internal_error", "server_error"]


def normalize_slack_error(error: SlackApiError) -> Dict[str, Any]:
    """
    Normalize Slack API error to a user-friendly format.
    Returns: {
        "error_type": str,
        "user_message": str,
        "technical_details": str (for logging only),
        "retriable": bool
    }
    """
    error_code = error.response.get("error", "unknown_error")
    user_message = ERROR_MESSAGES.get(
        error_code, 
        f"An error occurred: {error_code}. Please try again or contact support."
    )
    
    return {
        "error_type": error_code,
        "user_message": user_message,
        "technical_details": str(error),
        "retriable": error_code in RETRIABLE_ERRORS
    }


def create_error_response(error_type: str, user_message: str, tool_name: str) -> Dict[str, Any]:
    """Create a standardized error response for tool calls."""
    return {
        "success": False,
        "error": {
            "type": error_type,
            "message": user_message,
            "tool": tool_name
        },
        "data": None
    }
