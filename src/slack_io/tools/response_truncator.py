"""
Response truncation for context window management.
"""
import json
from typing import Dict, Any, List
from .config import TOOL_CONFIG

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    ENCODING = tiktoken.encoding_for_model("gpt-4o")
    USE_TIKTOKEN = True
except ImportError:
    USE_TIKTOKEN = False


def estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    if USE_TIKTOKEN:
        return len(ENCODING.encode(text))
    else:
        # Fallback: rough estimate (4 chars per token)
        return len(text) // 4


def estimate_response_tokens(response: Dict[str, Any]) -> int:
    """Estimate total tokens in a response."""
    response_str = json.dumps(response)
    return estimate_tokens(response_str)


def truncate_items(items: List[Any], max_items: int, strategy: str = "recent") -> List[Any]:
    """
    Truncate a list of items based on strategy.
    Strategies: "recent" (keep most recent), "first" (keep first N), "relevant" (keep most relevant)
    """
    if len(items) <= max_items:
        return items
    
    if strategy == "recent":
        # Keep most recent items (for messages, this makes sense)
        return items[-max_items:]
    elif strategy == "first":
        # Keep first N items
        return items[:max_items]
    else:
        # Default: keep first N
        return items[:max_items]


def truncate_response(
    response: Dict[str, Any],
    max_items: int = None,
    max_tokens: int = None
) -> Dict[str, Any]:
    """
    Truncate response to fit within limits.
    Modifies response in place and adds metadata.
    """
    config = TOOL_CONFIG["truncation"]
    max_items = max_items or config["max_items"]
    max_tokens = max_tokens or config["max_tokens"]
    strategy = config["strategy"]
    
    # Get items list (assuming standard structure)
    items = response.get("items", [])
    if not items:
        return response
    
    # Step 1: Apply hard item limit
    original_count = len(items)
    if len(items) > max_items:
        items = truncate_items(items, max_items, strategy)
        response["items"] = items
        response["truncated"] = True
    
    # Step 2: Check token limit
    estimated_tokens = estimate_response_tokens(response)
    if estimated_tokens > max_tokens:
        # Need to truncate further
        # Rough calculation: how many items can we keep?
        items_per_token = len(items) / estimated_tokens if estimated_tokens > 0 else 1
        target_items = int(max_tokens * items_per_token * 0.9)  # 90% to be safe
        
        if target_items < len(items):
            items = truncate_items(items, target_items, strategy)
            response["items"] = items
            response["truncated"] = True
    
    # Step 3: Add metadata
    response["meta"] = response.get("meta", {})
    response["meta"].update({
        "truncated": response.get("truncated", False),
        "items_shown": len(items),
        "items_total": original_count,
        "estimated_tokens": estimate_response_tokens(response)
    })
    
    return response
