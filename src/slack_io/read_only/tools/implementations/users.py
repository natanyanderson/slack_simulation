"""
Users API implementations.
"""
from typing import Dict, Any, Optional
from slack_sdk.errors import SlackApiError
from ....shared.slack_client import app as bolt_app
from ..error_handler import normalize_slack_error, create_error_response
from ..validators import validate_user_id, validate_limit
from ..cache import set_user_info, get_user_info


def get_user_info(
    user: str,
    include_locale: bool = False
) -> Dict[str, Any]:
    """
    Get user information.
    Returns: {
        "success": bool,
        "data": {
            "user": Dict,
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Check cache first
        cached_user = get_user_info(user)
        if cached_user:
            return {
                "success": True,
                "data": {
                    "user": cached_user,
                    "meta": {"cached": True}
                },
                "error": None
            }
        
        # Validate user ID
        valid, err = validate_user_id(user)
        if not valid:
            return create_error_response("invalid_user_id", err or "Invalid user ID", "get_user_info")
        
        # Build parameters
        params = {
            "user": user,
            "include_locale": include_locale
        }
        
        # Call Slack API
        response = bolt_app.client.users_info(**params)
        
        user_data = response.get("user", {})
        
        # Cache user info
        set_user_info(user, user_data)
        
        return {
            "success": True,
            "data": {
                "user": user_data,
                "meta": {"cached": False}
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "get_user_info"
        )
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "get_user_info"
            },
            "data": None
        }


def list_users(
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    include_locale: bool = False
) -> Dict[str, Any]:
    """
    List users in the workspace.
    Returns: {
        "success": bool,
        "data": {
            "users": List[Dict],
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate limit
        limit, _ = validate_limit(limit or 50, "users.list", default=50)
        
        # Build parameters
        params = {
            "limit": limit,
            "include_locale": include_locale
        }
        
        if cursor:
            params["cursor"] = cursor
        
        # Call Slack API
        response = bolt_app.client.users_list(**params)
        
        users = response.get("members", [])
        
        # Cache user info
        for user in users:
            user_id = user.get("id")
            if user_id:
                set_user_info(user_id, user)
        
        return {
            "success": True,
            "data": {
                "users": users,
                "meta": {
                    "total": len(users),
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
            "list_users"
        )
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "list_users"
            },
            "data": None
        }

