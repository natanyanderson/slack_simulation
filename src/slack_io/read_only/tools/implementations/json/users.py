"""
JSON-based Users API implementations.
Mirrors the API implementations but reads from exported JSON files.
"""
from typing import Dict, Any, Optional
from ...error_handler import create_error_response
from ...validators import validate_user_id, validate_limit
from ...cache import set_user_info, get_user_info
from ..json_data_loader import get_loader


def get_user_info(
    user: str,
    include_locale: bool = False
) -> Dict[str, Any]:
    """
    Get user information from exported JSON.
    Returns the same format as the API implementation.
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
        
        loader = get_loader()
        user_data = loader.get_user_by_id(user)
        
        if not user_data:
            return create_error_response("user_not_found", f"User {user} not found in export", "get_user_info")
        
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
    List users from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        users = loader.users.copy()
        
        # Validate limit
        limit, _ = validate_limit(limit or 50, "users.list", default=50)
        
        # Note: cursor/pagination not fully supported in JSON mode
        # For now, just apply limit
        users = users[:limit]
        
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
                "tool": "list_users"
            },
            "data": None
        }

