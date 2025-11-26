"""
JSON-based Search API implementations.
Mirrors the API implementations but searches exported JSON files.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from ...error_handler import create_error_response
from ...timestamp_formatter import format_message_timestamps
from ...query_optimizer import optimize_search_query, validate_search_result
from ..json_data_loader import get_loader


def _search_messages_in_text(
    messages: List[Dict[str, Any]],
    query: str,
    optimized_query: str
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Search messages by text content.
    Returns list of (message, relevance_score) tuples.
    """
    results = []
    
    # Extract search terms
    query_lower = query.lower()
    optimized_lower = optimized_query.lower()
    
    # Check for quoted phrases
    quoted_phrase = None
    if '"' in optimized_lower:
        quote_match = re.search(r'"([^"]+)"', optimized_lower)
        if quote_match:
            quoted_phrase = quote_match.group(1).lower()
    
    # Extract keywords (remove stop words)
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "about", "related", "to", "messages"}
    words = re.findall(r'\b\w+\b', query_lower)
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # If query is very short (like "SN4") or no keywords extracted, use the query itself
    if not keywords:
        # Use the query itself as a keyword (strip and use as-is)
        query_clean = query_lower.strip()
        if query_clean:
            keywords = [query_clean]
    
    for msg in messages:
        text = msg.get("text", "").lower()
        if not text:
            continue
        
        relevance_score = 0.0
        
        # Check for exact phrase match (including 2-word phrases)
        # First check if the full query appears as a phrase
        query_phrase = query_lower.strip()
        if query_phrase in text:
            relevance_score = 0.9  # High score for exact phrase match
        elif quoted_phrase:
            phrase = quoted_phrase.strip('"')
            if phrase in text:
                relevance_score = 0.9
            else:
                # Partial phrase match
                phrase_words = phrase.split()
                words_found = sum(1 for word in phrase_words if word in text)
                if phrase_words:
                    partial_score = words_found / len(phrase_words)
                    if len(phrase_words) >= 3:
                        if words_found >= len(phrase_words) * 0.67:
                            relevance_score = partial_score * 0.8
                        else:
                            relevance_score = partial_score * 0.5
                    else:
                        relevance_score = partial_score * 0.7
        
        # Check for keyword matches
        if keywords and relevance_score < 0.6:
            keywords_found = sum(1 for keyword in keywords if keyword in text)
            keyword_score = keywords_found / len(keywords) if keywords else 0.0
            # If all keywords are found, give higher score
            if keywords_found == len(keywords) and len(keywords) > 0:
                relevance_score = max(relevance_score, 0.7)  # High score for all keywords
            elif relevance_score < 0.5:
                relevance_score = max(relevance_score, keyword_score * 0.6)
        
        # If no keywords and no phrase, check if query itself matches (for short queries like "SN4")
        if not keywords and not quoted_phrase:
            query_clean = query_lower.strip()
            if query_clean in text:
                relevance_score = 0.8  # High score for exact match
            else:
                # Try word-by-word matching as fallback
                query_words = query_lower.split()
                if query_words:
                    matches = sum(1 for word in query_words if word in text)
                    if matches > 0:
                        relevance_score = matches / len(query_words) * 0.5
        
        # Only include if relevant (score >= 0.4)
        if relevance_score >= 0.4:
            results.append((msg, relevance_score))
    
    return results


def search_messages(
    query: str,
    sort: str = "score",
    sort_dir: str = "desc",
    count: Optional[int] = None,
    page: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search for messages in exported JSON files.
    Returns the same format as the API implementation.
    """
    try:
        # Validate parameters
        if not query or not query.strip():
            return create_error_response("invalid_query", "Search query is required", "search_messages")
        
        # Optimize query (same as API implementation)
        optimized_query = optimize_search_query(query)
        
        # Validate count - in JSON mode, allow much higher limits
        count = count or 20
        if count < 1:
            count = 20
        # JSON mode: allow up to 10,000 results (vs 100 for API mode)
        if count > 10000:
            count = 10000
        
        # Validate sort
        if sort not in ["score", "timestamp"]:
            sort = "score"
        
        # Validate sort_dir
        if sort_dir not in ["asc", "desc"]:
            sort_dir = "desc"
        
        loader = get_loader()
        
        # Try to use compiled_messages.json first (faster, all messages in one place)
        # Use streaming to avoid loading entire file into memory
        all_messages = []
        
        try:
            # Use streaming to process messages incrementally
            # Note: We still collect all messages for search, but we do it incrementally
            # This is better than loading everything at once with json.load()
            compiled_messages_stream = loader.stream_compiled_messages()
            for msg in compiled_messages_stream:
                all_messages.append(msg)
        except Exception as e:
            # Streaming failed, try fallback to regular loading (with warnings)
            print(f"Streaming failed, trying fallback: {e}")
            try:
                compiled_messages = loader.load_compiled_messages()
                if compiled_messages:
                    all_messages = compiled_messages
            except Exception as e2:
                print(f"Fallback loading also failed: {e2}")
                all_messages = []
        
        # If no messages from compiled file, fallback to per-channel directories
        if not all_messages:
            channel_names = loader.get_all_channel_names()
            for channel_name in channel_names:
                messages = loader.load_channel_messages(channel_name)
                # Add channel info to each message for context
                for msg in messages:
                    msg_copy = msg.copy()
                    # Try to get channel ID
                    channel_info = loader.get_channel_by_name(channel_name)
                    if channel_info:
                        msg_copy["channel"] = {"id": channel_info.get("id"), "name": channel_name}
                    all_messages.append(msg_copy)
        
        # Check if we have any messages to search
        if not all_messages:
            return {
                "success": False,
                "error": {
                    "type": "no_data",
                    "message": "No messages found in JSON export. Please verify the export paths are correct.",
                    "tool": "search_messages"
                },
                "data": None
            }
        
        # Search messages (only call once to avoid inconsistencies)
        all_search_results = _search_messages_in_text(all_messages, query, optimized_query)
        total = len(all_search_results)
        
        # Sort results
        if sort == "score":
            # Sort by relevance score
            all_search_results.sort(key=lambda x: x[1], reverse=(sort_dir == "desc"))
        else:
            # Sort by timestamp
            all_search_results.sort(
                key=lambda x: float(x[0].get("ts", "0")),
                reverse=(sort_dir == "desc")
            )
        
        # Apply pagination
        if page and page > 1:
            start_idx = (page - 1) * count
            end_idx = start_idx + count
            search_results = all_search_results[start_idx:end_idx]
        else:
            search_results = all_search_results[:count]
        
        # Format results to match Slack API format
        matches = []
        for msg, score in search_results:
            # Format timestamp
            formatted_msg = format_message_timestamps(msg)
            # Add relevance score
            formatted_msg["_relevance_score"] = score
            matches.append(formatted_msg)
        
        return {
            "success": True,
            "data": {
                "messages": {
                    "total": total,
                    "matches": matches,
                    "pagination": {
                        "total": total,
                        "page": page or 1,
                        "per_page": count,
                        "pages": (total + count - 1) // count if total > 0 else 1
                    }
                },
                "meta": {
                    "total": total,
                    "matches_count": len(matches),
                    "filtered_count": 0,  # Not applicable for JSON search
                    "original_query": query,
                    "optimized_query": optimized_query,
                    "query": optimized_query,
                    "pagination": {
                        "total": total,
                        "page": page or 1,
                        "per_page": count,
                        "pages": (total + count - 1) // count if total > 0 else 1
                    }
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
                "tool": "search_messages"
            },
            "data": None
        }

