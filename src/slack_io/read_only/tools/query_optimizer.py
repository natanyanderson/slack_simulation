"""
Query optimization and result validation for Slack search.
"""
import re
from typing import Dict, Any, Tuple


def optimize_search_query(query: str) -> str:
    """
    Optimize search query for Slack's search API.
    
    Slack search syntax:
    - Quoted strings for exact phrases: "exact phrase"
    - Individual keywords work but may return fuzzy matches
    - For exact phrase matching, wrap in quotes
    
    Args:
        query: Original search query
    
    Returns:
        Optimized query string
    """
    query = query.strip()
    
    # If query already has quotes or modifiers, return as-is
    if '"' in query or query.startswith('from:') or query.startswith('in:'):
        return query
    
    # Detect if user wants exact phrase matching
    # Common patterns: "about X", "related to X", "messages about X"
    phrase_patterns = [
        r'about\s+"([^"]+)"',  # about "phrase"
        r'about\s+(.+)',        # about phrase
        r'related to\s+"([^"]+)"',
        r'related to\s+(.+)',
        r'messages about\s+"([^"]+)"',
        r'messages about\s+(.+)',
    ]
    
    for pattern in phrase_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            phrase = match.group(1) if match.groups() else match.group(0)
            # Extract the actual phrase
            if match.groups():
                phrase = match.group(1)
            else:
                # Extract everything after "about" or "related to"
                phrase = re.sub(r'^(about|related to|messages about)\s+', '', query, flags=re.IGNORECASE).strip()
            
            # Wrap in quotes for exact phrase matching
            return f'"{phrase}"'
    
    # If query has 3+ words, treat as phrase and wrap in quotes
    words = query.split()
    if len(words) >= 3:
        # Remove common prefixes
        cleaned = re.sub(r'^(find|search|look for|messages about|about|related to)\s+', '', query, flags=re.IGNORECASE).strip()
        return f'"{cleaned}"'
    
    # For shorter queries, return as-is (keyword search)
    return query


def validate_search_result(match: Dict[str, Any], original_query: str, min_relevance: float = 0.4) -> Tuple[bool, float]:
    """
    Validate if a search result is relevant to the query.
    
    Args:
        match: Search result match from Slack API
        original_query: Original search query (before optimization)
        min_relevance: Minimum relevance score (0.0 to 1.0)
    
    Returns:
        (is_relevant, relevance_score)
    """
    # Get message text
    text = match.get("text", "").lower()
    if not text:
        return False, 0.0
    
    # Extract key terms from query (remove quotes, stop words)
    query_lower = original_query.lower()
    
    # Extract phrase from quotes if present (in optimized query)
    quoted_phrase = None
    if '"' in query_lower:
        quote_match = re.search(r'"([^"]+)"', query_lower)
        if quote_match:
            quoted_phrase = quote_match.group(1).lower()
    
    # If no quotes, check if it's a multi-word phrase that should be treated as exact
    # (This handles cases where the optimizer wrapped it in quotes)
    if not quoted_phrase:
        # Check if original query has 3+ words (likely a phrase)
        words = original_query.split()
        if len(words) >= 3:
            # Treat as phrase - remove common prefixes
            cleaned = re.sub(r'^(find|search|look for|messages about|about|related to)\s+', '', original_query, flags=re.IGNORECASE).strip()
            quoted_phrase = cleaned.lower()
    
    # Extract individual keywords (for fallback matching)
    # Remove common stop words
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "about", "related", "to", "messages"}
    words = re.findall(r'\b\w+\b', query_lower)
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Calculate relevance
    relevance_score = 0.0
    
    # Check for exact phrase match (highest relevance)
    if quoted_phrase:
        # Remove quotes if present
        quoted_phrase = quoted_phrase.strip('"')
        
        if quoted_phrase in text:
            relevance_score = 0.9
        else:
            # Check how many words from phrase are present
            phrase_words = quoted_phrase.split()
            words_found = sum(1 for word in phrase_words if word in text)
            if phrase_words:
                # Calculate partial match score
                partial_score = words_found / len(phrase_words)
                # For 3+ word phrases, require at least 2/3 of words
                if len(phrase_words) >= 3:
                    if words_found >= len(phrase_words) * 0.67:  # At least 2/3 of words
                        relevance_score = partial_score * 0.8
                    else:
                        relevance_score = partial_score * 0.5  # Lower score for partial matches
                else:
                    relevance_score = partial_score * 0.7
    
    # Check for keyword matches (fallback)
    if keywords and relevance_score < 0.6:
        keywords_found = sum(1 for keyword in keywords if keyword in text)
        keyword_score = keywords_found / len(keywords) if keywords else 0.0
        # Only use keyword score if phrase matching didn't give good results
        if relevance_score < 0.5:
            relevance_score = max(relevance_score, keyword_score * 0.6)
    
    # If no keywords extracted and no phrase, assume relevant (can't validate)
    if not keywords and not quoted_phrase:
        relevance_score = 0.5
    
    is_relevant = relevance_score >= min_relevance
    
    return is_relevant, relevance_score

