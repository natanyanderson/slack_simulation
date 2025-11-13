"""
JSON-based Team/Workspace API implementations.
Mirrors the API implementations but reads from exported JSON files.
"""
from typing import Dict, Any
from ...error_handler import create_error_response
from ..json_data_loader import get_loader


def get_team_info() -> Dict[str, Any]:
    """
    Get team/workspace information from exported JSON.
    Returns the same format as the API implementation.
    """
    try:
        loader = get_loader()
        channels = loader.channels
        
        # Try to extract team info from channels
        # Most channels should have team_id
        team_id = None
        team_name = None
        
        if channels:
            # Get team_id from first channel
            first_channel = channels[0]
            team_id = first_channel.get("team_id") or first_channel.get("team")
            
            # Try to infer team name from export path or use default
            team_name = "Slack Workspace"
        
        # Create minimal team object
        team = {
            "id": team_id or "T00000000",
            "name": team_name,
            "domain": "workspace",  # Default domain
        }
        
        return {
            "success": True,
            "data": {
                "team": team,
                "meta": {}
            },
            "error": None
        }
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

