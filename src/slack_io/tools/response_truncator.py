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
    
    # Store original items for safety checks
    original_items = items.copy()
    original_count = len(items)
    
    # Step 1: Apply hard item limit
    if len(items) > max_items:
        items = truncate_items(items, max_items, strategy)
        response["items"] = items
        response["truncated"] = True
    
    # Safety check: never truncate to 0 if we started with items
    if original_count > 0 and len(items) == 0:
        # Keep at least the first item from original
        items = [original_items[0]]
        response["items"] = items
    else:
        # Update response with current items
        response["items"] = items
    
    # Step 2: Check token limit
    # Get current items from response (may have been modified in Step 1)
    items = response.get("items", [])
    estimated_tokens = estimate_response_tokens(response)
    if estimated_tokens > max_tokens:
        # Need to truncate further
        # Calculate tokens per item (approximate)
        if len(items) > 0:
            # Estimate tokens for a single item by sampling
            sample_item = items[0] if items else {}
            sample_tokens = estimate_tokens(json.dumps(sample_item))
            if sample_tokens > 0:
                # Calculate how many items we can fit
                # Reserve some tokens for response structure (metadata, etc.)
                structure_tokens = estimated_tokens - (sample_tokens * len(items))
                available_tokens = max_tokens - structure_tokens
                target_items = max(1, int(available_tokens / sample_tokens * 0.9))  # 90% to be safe, at least 1
            else:
                # Fallback: keep at least 1 item
                target_items = max(1, len(items))
        else:
            target_items = 0
        
        if target_items < len(items) and target_items > 0:
            items = truncate_items(items, target_items, strategy)
            response["items"] = items
            response["truncated"] = True
        elif target_items == 0 and len(items) > 0:
            # Safety: if calculation says 0 but we have items, keep at least 1
            items = [items[0]] if items else []
            response["items"] = items
            response["truncated"] = True
    
    # Final safety check: never end up with 0 items if we started with items
    if original_count > 0 and len(response.get("items", [])) == 0:
        response["items"] = [original_items[0]]
        response["truncated"] = True
    
    # Step 3: Add metadata
    # Get final items count after all truncation
    final_items = response.get("items", [])
    response["meta"] = response.get("meta", {})
    response["meta"].update({
        "truncated": response.get("truncated", False),
        "items_shown": len(final_items),
        "items_total": original_count,
        "estimated_tokens": estimate_response_tokens(response)
    })
    
    return response
