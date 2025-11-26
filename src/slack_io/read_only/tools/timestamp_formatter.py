"""
Utility functions for formatting Slack timestamps.
"""
from datetime import datetime
from typing import Any, Dict, List


def format_slack_timestamp(ts: str) -> str:
    """
    Convert Slack timestamp (Unix timestamp with microseconds) to human-readable format.
    
    Args:
        ts: Slack timestamp string (e.g., "1762391270.483639")
    
    Returns:
        Human-readable date/time string (e.g., "2025-11-10 14:47:50")
    """
    try:
        # Parse the timestamp (Slack timestamps are Unix timestamps with microseconds)
        timestamp_float = float(ts)
        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp_float)
        # Format as readable date/time
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        # If parsing fails, return original timestamp
        return ts


def format_message_timestamps(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format all timestamp fields in a Slack message.
    Preserves original Unix timestamps in _original_ts and _original_thread_ts fields.
    
    Args:
        message: Slack message dictionary
    
    Returns:
        Message dictionary with formatted timestamps (and original timestamps preserved)
    """
    formatted_message = message.copy()
    
    # Format main timestamp (ts)
    if "ts" in formatted_message:
        original_ts = formatted_message["ts"]
        # Preserve original Unix timestamp before formatting
        if isinstance(original_ts, str) and "." in original_ts:
            try:
                float(original_ts)  # Check if it's a Unix timestamp
                formatted_message["_original_ts"] = original_ts
            except ValueError:
                pass  # Not a Unix timestamp, skip preserving
        formatted_message["ts"] = format_slack_timestamp(original_ts)
        # Also add a human-readable version
        formatted_message["timestamp"] = formatted_message["ts"]
    
    # Format thread timestamp if present
    if "thread_ts" in formatted_message:
        original_thread_ts = formatted_message["thread_ts"]
        # Preserve original Unix timestamp before formatting
        if isinstance(original_thread_ts, str) and "." in original_thread_ts:
            try:
                float(original_thread_ts)  # Check if it's a Unix timestamp
                formatted_message["_original_thread_ts"] = original_thread_ts
            except ValueError:
                pass  # Not a Unix timestamp, skip preserving
        formatted_message["thread_ts"] = format_slack_timestamp(original_thread_ts)
        formatted_message["thread_timestamp"] = formatted_message["thread_ts"]
    
    # Format edited timestamp if present
    if "edited" in formatted_message and "ts" in formatted_message["edited"]:
        edited_ts = formatted_message["edited"]["ts"]
        formatted_message["edited"]["ts"] = format_slack_timestamp(edited_ts)
        formatted_message["edited"]["timestamp"] = formatted_message["edited"]["ts"]
    
    return formatted_message


def format_messages_timestamps(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format timestamps in a list of messages.
    
    Args:
        messages: List of Slack message dictionaries
    
    Returns:
        List of messages with formatted timestamps
    """
    return [format_message_timestamps(msg) for msg in messages]



