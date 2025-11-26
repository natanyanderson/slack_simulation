"""
Team/Workspace API implementations.
Note: This file is named 'files.py' but contains team info for now.
Future: Add file operations here.
"""
from typing import Dict, Any
from slack_sdk.errors import SlackApiError
from ....shared.slack_client import app as bolt_app
from ..error_handler import normalize_slack_error, create_error_response


def get_team_info() -> Dict[str, Any]:
    """
    Get team/workspace information.
    Returns: {
        "success": bool,
        "data": {
            "team": Dict,
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Call Slack API
        response = bolt_app.client.team_info()
        
        team = response.get("team", {})
        
        return {
            "success": True,
            "data": {
                "team": team,
                "meta": {}
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "get_team_info"
        )
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "get_team_info"
            },
            "data": None
        }

