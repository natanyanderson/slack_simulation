"""
Conversations API implementations.
"""
from typing import Dict, Any, Optional, List
from slack_sdk.errors import SlackApiError
from ...slack_client import app as bolt_app
from ..error_handler import normalize_slack_error, create_error_response
from ..validators import validate_channel_id, validate_limit
from ..cache import set_channel_id, get_channel_id
import time


def list_channels(
    types: Optional[str] = None,
    limit: Optional[int] = None,
    exclude_archived: bool = False
) -> Dict[str, Any]:
    """
    List channels in the workspace.
    Returns: {
        "success": bool,
        "data": {
            "channels": List[Dict],
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate limit
        limit, _ = validate_limit(limit or 200, "conversations.list", default=200)
        
        # Build parameters
        params = {
            "limit": limit,
            "exclude_archived": exclude_archived
        }
        
        if types:
            params["types"] = types
        
        # Call Slack API
        response = bolt_app.client.conversations_list(**params)
        
        channels = response.get("channels", [])
        
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
                    "has_more": response.get("response_metadata", {}).get("next_cursor") is not None,
                    "next_cursor": response.get("response_metadata", {}).get("next_cursor")
                }
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "list_channels"
        )
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
    Get channel message history.
    Returns: {
        "success": bool,
        "data": {
            "messages": List[Dict],
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_channel_history")
        
        # Validate limit
        limit, _ = validate_limit(limit or 50, "conversations.history", default=50)
        
        # Build parameters
        params = {
            "channel": channel,
            "limit": limit,
            "inclusive": inclusive
        }
        
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        
        # Call Slack API
        response = bolt_app.client.conversations_history(**params)
        
        messages = response.get("messages", [])
        
        return {
            "success": True,
            "data": {
                "messages": messages,
                "meta": {
                    "total": len(messages),
                    "has_more": response.get("has_more", False),
                    "next_cursor": response.get("response_metadata", {}).get("next_cursor")
                }
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "get_channel_history"
        )
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
    Get channel members.
    Returns: {
        "success": bool,
        "data": {
            "members": List[str],  # List of user IDs
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_channel_members")
        
        # Validate limit
        limit, _ = validate_limit(limit or 50, "conversations.members", default=50)
        
        # Build parameters
        params = {
            "channel": channel,
            "limit": limit
        }
        
        # Call Slack API
        response = bolt_app.client.conversations_members(**params)
        
        members = response.get("members", [])
        
        return {
            "success": True,
            "data": {
                "members": members,
                "meta": {
                    "total": len(members),
                    "has_more": response.get("response_metadata", {}).get("next_cursor") is not None,
                    "next_cursor": response.get("response_metadata", {}).get("next_cursor")
                }
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "get_channel_members"
        )
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
    Get thread replies.
    Returns: {
        "success": bool,
        "data": {
            "messages": List[Dict],
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate channel ID
        valid, err = validate_channel_id(channel)
        if not valid:
            return create_error_response("invalid_channel_id", err or "Invalid channel ID", "get_thread_replies")
        
        # Validate limit
        limit, _ = validate_limit(limit or 50, "conversations.replies", default=50)
        
        # Build parameters
        params = {
            "channel": channel,
            "ts": ts,
            "limit": limit
        }
        
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        
        # Call Slack API
        response = bolt_app.client.conversations_replies(**params)
        
        messages = response.get("messages", [])
        
        return {
            "success": True,
            "data": {
                "messages": messages,
                "meta": {
                    "total": len(messages),
                    "has_more": response.get("has_more", False),
                    "next_cursor": response.get("response_metadata", {}).get("next_cursor")
                }
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "get_thread_replies"
        )
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

