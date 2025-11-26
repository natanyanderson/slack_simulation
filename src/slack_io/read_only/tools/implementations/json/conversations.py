"""
JSON-based Conversations API implementations.
Mirrors the API implementations but reads from exported JSON files.
"""
from typing import Dict, Any, Optional, List
from ...error_handler import create_error_response
from ...validators import validate_channel_id, validate_limit
from ...cache import set_channel_id, get_channel_id
from ...timestamp_formatter import format_messages_timestamps
from ..json_data_loader import get_loader
from datetime import datetime


def _parse_timestamp(ts: str) -> float:
    """
    Parse a timestamp that could be either:
    - Unix timestamp string (e.g., "1757434763.000000")
    - Formatted date string (e.g., "2025-09-09 12:19:23")
    
    Returns:
        Unix timestamp as float
    """
    try:
        # Try parsing as Unix timestamp first
        return float(ts)
    except ValueError:
        # Try parsing as formatted date string
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except ValueError:
            # If both fail, raise an error
            raise ValueError(f"Could not parse timestamp: {ts}")


def list_channels(
    types: Optional[str] = None,
    limit: Optional[int] = None,
    exclude_archived: bool = False
) -> Dict[str, Any]:
    """
    List channels from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        channels = loader.channels.copy()
        
        # Filter by archived status
        if exclude_archived:
            channels = [ch for ch in channels if not ch.get("is_archived", False)]
        
        # Filter by types if specified
        if types:
            type_list = [t.strip() for t in types.split(",")]
            filtered = []
            for ch in channels:
                is_private = ch.get("is_private", False)
                is_mpim = ch.get("is_mpim", False)
                is_im = ch.get("is_im", False)
                
                if "private_channel" in type_list and is_private:
                    filtered.append(ch)
                elif "public_channel" in type_list and not is_private and not is_mpim and not is_im:
                    filtered.append(ch)
                elif "mpim" in type_list and is_mpim:
                    filtered.append(ch)
                elif "im" in type_list and is_im:
                    filtered.append(ch)
            channels = filtered
        
        # Validate and apply limit
        limit, _ = validate_limit(limit or 200, "conversations.list", default=200)
        channels = channels[:limit]
        
        # Cache channel name -> ID mappings
        for channel in channels:
            channel_id = channel.get("id")
            channel_name = channel.get("name")
            if channel_id and channel_name:
                set_channel_id(channel_name, channel_id)
        
        return {
            "success": True,
            "data": {
                "channels": channels,
                "meta": {
                    "total": len(channels),
                    "has_more": False,  # JSON export is static
                    "next_cursor": None
                }
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "list_channels"
            },
            "data": None
        }


def get_channel_history(
    channel: str,
    limit: Optional[int] = None,
    oldest: Optional[str] = None,
    latest: Optional[str] = None,
    inclusive: bool = False
) -> Dict[str, Any]:
    """
    Get channel message history from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_channel_history")
        
        # Get channel info to find channel name
        channel_info = loader.get_channel_by_id(channel)
        if not channel_info:
            return create_error_response("channel_not_found", f"Channel {channel} not found in export", "get_channel_history")
        
        channel_name = channel_info.get("name")
        if not channel_name:
            return create_error_response("channel_not_found", "Channel name not found", "get_channel_history")
        
        # Load messages for this channel
        messages = loader.load_channel_messages(channel_name)
        
        # Filter by timestamp
        if oldest:
            oldest_ts = float(oldest)
            if inclusive:
                messages = [m for m in messages if float(m.get("ts", "0")) >= oldest_ts]
            else:
                messages = [m for m in messages if float(m.get("ts", "0")) > oldest_ts]
        
        if latest:
            latest_ts = float(latest)
            if inclusive:
                messages = [m for m in messages if float(m.get("ts", "0")) <= latest_ts]
            else:
                messages = [m for m in messages if float(m.get("ts", "0")) < latest_ts]
        
        # Sort by timestamp (descending - most recent first, like Slack API)
        messages.sort(key=lambda m: float(m.get("ts", "0")), reverse=True)
        
        # In JSON mode, we have all the data, so only apply limit if explicitly requested
        # Otherwise return all messages (no artificial limits)
        if limit is not None:
            # Validate limit but allow much higher values for JSON mode
            # Cap at 100,000 for JSON mode (vs 200 for API mode)
            if limit < 1:
                limit = 50
            elif limit > 100000:
                limit = 100000
            messages = messages[:limit]
        # If no limit specified, return all messages (JSON mode advantage)
        
        # Format timestamps
        formatted_messages = format_messages_timestamps(messages)
        
        return {
            "success": True,
            "data": {
                "messages": formatted_messages,
                "meta": {
                    "total": len(formatted_messages),
                    "has_more": False,  # JSON export is static
                    "next_cursor": None
                }
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "get_channel_history"
            },
            "data": None
        }


def get_channel_members(
    channel: str,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get channel members from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_channel_members")
        
        # Get channel info
        channel_info = loader.get_channel_by_id(channel)
        if not channel_info:
            return create_error_response("channel_not_found", f"Channel {channel} not found in export", "get_channel_members")
        
        # Get members from channel data
        members = channel_info.get("members", [])
        
        # Apply limit
        limit, _ = validate_limit(limit or 50, "conversations.members", default=50)
        members = members[:limit]
        
        return {
            "success": True,
            "data": {
                "members": members,
                "meta": {
                    "total": len(members),
                    "has_more": False,  # JSON export is static
                    "next_cursor": None
                }
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "get_channel_members"
            },
            "data": None
        }


def get_thread_replies(
    channel: str,
    ts: str,
    limit: Optional[int] = None,
    oldest: Optional[str] = None,
    latest: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get thread replies from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_thread_replies")
        
        # Get channel info to find channel name
        channel_info = loader.get_channel_by_id(channel)
        if not channel_info:
            return create_error_response("channel_not_found", f"Channel {channel} not found in export", "get_thread_replies")
        
        channel_name = channel_info.get("name")
        if not channel_name:
            return create_error_response("channel_not_found", "Channel name not found", "get_thread_replies")
        
        # Load messages for this channel
        all_messages = loader.load_channel_messages(channel_name)
        
        # Find thread replies (messages with thread_ts matching the parent ts)
        # Handle both Unix timestamp and formatted date string
        thread_ts = _parse_timestamp(ts)
        replies = []
        
        for msg in all_messages:
            msg_thread_ts = msg.get("thread_ts")
            if msg_thread_ts:
                # Handle both Unix timestamp and formatted date string
                try:
                    msg_thread_ts_float = _parse_timestamp(str(msg_thread_ts))
                    # Use a small tolerance for floating point comparison
                    if abs(msg_thread_ts_float - thread_ts) < 0.0001:
                        # This is a reply in the thread
                        msg_ts = float(msg.get("ts", "0"))
                        
                        # Filter by timestamp if specified
                        if oldest:
                            oldest_ts = float(oldest)
                            if msg_ts < oldest_ts:
                                continue
                        if latest:
                            latest_ts = float(latest)
                            if msg_ts > latest_ts:
                                continue
                        
                        replies.append(msg)
                except (ValueError, TypeError):
                    # Skip if we can't parse the timestamp
                    continue
        
        # Sort by timestamp (ascending - oldest first, like Slack API)
        replies.sort(key=lambda m: float(m.get("ts", "0")))
        
        # Apply limit
        limit, _ = validate_limit(limit or 50, "conversations.replies", default=50)
        replies = replies[:limit]
        
        # Format timestamps
        formatted_replies = format_messages_timestamps(replies)
        
        return {
            "success": True,
            "data": {
                "messages": formatted_replies,
                "meta": {
                    "total": len(formatted_replies),
                    "has_more": False,  # JSON export is static
                    "next_cursor": None
                }
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "get_thread_replies"
            },
            "data": None
        }

