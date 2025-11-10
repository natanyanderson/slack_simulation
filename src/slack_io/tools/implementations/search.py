"""
Search API implementations.
"""
from typing import Dict, Any, Optional
from slack_sdk.errors import SlackApiError
from ...slack_client import app as bolt_app
from ..error_handler import normalize_slack_error, create_error_response
from ..timestamp_formatter import format_message_timestamps
from ..query_optimizer import optimize_search_query, validate_search_result


def search_messages(
    query: str,
    sort: str = "score",
    sort_dir: str = "desc",
    count: Optional[int] = None,
    page: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search for messages.
    Returns: {
        "success": bool,
        "data": {
            "messages": Dict,  # Slack search results structure
            "meta": Dict
        },
        "error": Optional[Dict]
    }
    """
    try:
        # Validate parameters
        if not query or not query.strip():
            return create_error_response("invalid_query", "Search query is required", "search_messages")
        
        # Optimize query for Slack's search syntax
        optimized_query = optimize_search_query(query)
        
        # Validate count
        count = count or 20
        if count < 1:
            count = 20
        if count > 100:
            count = 100
        
        # Validate sort
        if sort not in ["score", "timestamp"]:
            sort = "score"
        
        # Validate sort_dir
        if sort_dir not in ["asc", "desc"]:
            sort_dir = "desc"
        
        # Build parameters
        params = {
            "query": optimized_query,  # Use optimized query
            "sort": sort,
            "sort_dir": sort_dir,
            "count": count
        }
        
        if page:
            params["page"] = page
        
        # Call Slack API
        response = bolt_app.client.search_messages(**params)
        
        messages = response.get("messages", {})
        matches = messages.get("matches", [])
        
        # Validate and filter results for relevance
        validated_matches = []
        filtered_count = 0
        for match in matches:
            is_relevant, relevance_score = validate_search_result(match, query)
            
            if is_relevant:
                # Format timestamps
                formatted_match = format_message_timestamps(match)
                # Add relevance score for debugging/ranking
                formatted_match["_relevance_score"] = relevance_score
                validated_matches.append(formatted_match)
            else:
                filtered_count += 1
        
        # Update messages dict with validated and formatted matches
        formatted_messages = messages.copy()
        formatted_messages["matches"] = validated_matches
        
        return {
            "success": True,
            "data": {
                "messages": formatted_messages,
                "meta": {
                    "total": messages.get("total", 0),
                    "matches_count": len(validated_matches),
                    "filtered_count": filtered_count,  # How many were filtered out
                    "original_query": query,
                    "optimized_query": optimized_query,  # Show what was actually searched
                    "query": optimized_query,  # Keep for backwards compatibility
                    "pagination": messages.get("pagination", {})
                }
            },
            "error": None
        }
    except SlackApiError as e:
        error_info = normalize_slack_error(e)
        return create_error_response(
            error_info["error_type"],
            error_info["user_message"],
            "search_messages"
        )
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Unexpected error: {str(e)}",
                "tool": "search_messages"
            },
            "data": None
        }

