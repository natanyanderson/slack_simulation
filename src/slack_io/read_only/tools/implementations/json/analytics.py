"""
Analytics tools for batch processing and incremental aggregation.
Supports multi-turn analysis by storing and merging results.

These are CUSTOM TOOLS - NOT part of the official Slack API.
They provide enhanced capabilities for analyzing exported JSON data.
"""
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict
from ...error_handler import create_error_response
from ..json_data_loader import get_loader


# Storage for aggregated results (in-memory, scoped by user and analysis type)
_aggregation_cache: Dict[str, Dict[str, Any]] = {}


def _get_cache_key(user_id: str, analysis_type: str) -> str:
    """Generate cache key for storing results."""
    return f"{user_id}:{analysis_type}"


def _timestamp_to_date(ts: float) -> str:
    """Convert Unix timestamp to YYYY-MM-DD date string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def analyze_channels_batch(
    channels: List[str],
    analysis_type: str = "thread_count",
    oldest: Optional[str] = None,
    latest: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze multiple channels in batch and return aggregated results.
    
    Args:
        channels: List of channel IDs to analyze
        analysis_type: Type of analysis - see supported types below
        oldest: Optional timestamp filter (Unix timestamp)
        latest: Optional timestamp filter (Unix timestamp)
    
    Supported analysis types:
    - "thread_count": Count threads with replies per channel
    - "message_count": Count messages per user per channel
    - "user_activity": List users who posted in each channel
    - "daily_activity": Messages per day per channel
    - "user_channels": Which channels each user posted in
    - "thread_depth": Average thread depth per channel
    - "engagement_rate": Replies per message ratio
    """
    try:
        loader = get_loader()
        results = {}
        
        # Parse timestamp filters
        oldest_ts = float(oldest) if oldest else None
        latest_ts = float(latest) if latest else None
        
        for channel_id in channels:
            channel_info = loader.get_channel_by_id(channel_id)
            if not channel_info:
                continue
                
            channel_name = channel_info.get("name")
            if not channel_name:
                continue
            
            # Load all messages for this channel
            messages = loader.load_channel_messages(channel_name)
            
            # Apply timestamp filters
            if oldest_ts:
                messages = [m for m in messages if float(m.get("ts", "0")) >= oldest_ts]
            if latest_ts:
                messages = [m for m in messages if float(m.get("ts", "0")) <= latest_ts]
            
            # Perform analysis based on type
            if analysis_type == "thread_count":
                # Count threads with replies
                threads_with_replies = sum(
                    1 for m in messages 
                    if m.get("reply_count", 0) > 0 or m.get("thread_ts")
                )
                results[channel_id] = {
                    "channel_name": channel_name,
                    "threads_with_replies": threads_with_replies,
                    "total_messages": len(messages)
                }
            
            elif analysis_type == "message_count":
                # Count messages per user
                user_counts = defaultdict(int)
                for msg in messages:
                    user_id = msg.get("user")
                    if user_id:
                        user_counts[user_id] += 1
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "total_messages": len(messages),
                    "unique_users": len(user_counts),
                    "top_users": dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10])
                }
            
            elif analysis_type == "user_activity":
                # Track which users posted
                users = set()
                for msg in messages:
                    user_id = msg.get("user")
                    if user_id:
                        users.add(user_id)
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "users": list(users),
                    "user_count": len(users)
                }
            
            elif analysis_type == "daily_activity":
                # Messages per day
                daily_counts = defaultdict(int)
                for msg in messages:
                    ts = float(msg.get("ts", "0"))
                    if ts > 0:
                        date = _timestamp_to_date(ts)
                        daily_counts[date] += 1
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "daily_counts": dict(daily_counts),
                    "total_messages": len(messages),
                    "active_days": len(daily_counts),
                    "busiest_day": max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None
                }
            
            elif analysis_type == "user_channels":
                # Which channels each user posted in (for cross-channel analysis)
                user_channels_map = defaultdict(set)
                for msg in messages:
                    user_id = msg.get("user")
                    if user_id:
                        user_channels_map[user_id].add(channel_id)
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "user_channels": {uid: list(chans) for uid, chans in user_channels_map.items()},
                    "users_in_channel": list(user_channels_map.keys())
                }
            
            elif analysis_type == "thread_depth":
                # Average thread depth (replies per thread)
                thread_depths = []
                thread_parents = {}  # ts -> message
                
                for msg in messages:
                    thread_ts = msg.get("thread_ts")
                    if thread_ts and thread_ts != msg.get("ts"):
                        # This is a reply
                        if thread_ts not in thread_parents:
                            thread_parents[thread_ts] = {"reply_count": 0}
                        thread_parents[thread_ts]["reply_count"] += 1
                
                for thread_ts, data in thread_parents.items():
                    thread_depths.append(data["reply_count"])
                
                avg_depth = sum(thread_depths) / len(thread_depths) if thread_depths else 0
                max_depth = max(thread_depths) if thread_depths else 0
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "threads_analyzed": len(thread_depths),
                    "average_thread_depth": round(avg_depth, 2),
                    "max_thread_depth": max_depth,
                    "total_messages": len(messages)
                }
            
            elif analysis_type == "engagement_rate":
                # Replies per message ratio
                total_messages = len(messages)
                messages_with_replies = sum(1 for m in messages if m.get("reply_count", 0) > 0)
                total_replies = sum(m.get("reply_count", 0) for m in messages)
                
                engagement_rate = (messages_with_replies / total_messages * 100) if total_messages > 0 else 0
                replies_per_message = (total_replies / total_messages) if total_messages > 0 else 0
                
                results[channel_id] = {
                    "channel_name": channel_name,
                    "total_messages": total_messages,
                    "messages_with_replies": messages_with_replies,
                    "total_replies": total_replies,
                    "engagement_rate_percent": round(engagement_rate, 2),
                    "replies_per_message": round(replies_per_message, 2)
                }
            
            else:
                return {
                    "success": False,
                    "error": {
                        "type": "invalid_analysis_type",
                        "message": f"Unknown analysis_type: {analysis_type}. Supported: thread_count, message_count, user_activity, daily_activity, user_channels, thread_depth, engagement_rate",
                        "tool": "analyze_channels_batch"
                    },
                    "data": None
                }
        
        return {
            "success": True,
            "data": {
                "analysis_type": analysis_type,
                "channels_analyzed": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Error in batch analysis: {str(e)}",
                "tool": "analyze_channels_batch"
            },
            "data": None
        }


def store_aggregation_results(
    user_id: str,
    analysis_type: str,
    results: Dict[str, Any],
    merge: bool = False
) -> Dict[str, Any]:
    """
    Store aggregated results for later retrieval/merging.
    
    Args:
        user_id: User ID for scoping results
        analysis_type: Type of analysis (e.g., "thread_count", "user_activity")
        results: Results to store (from analyze_channels_batch)
        merge: If True, merge with existing results; if False, replace
    """
    try:
        cache_key = _get_cache_key(user_id, analysis_type)
        
        if merge and cache_key in _aggregation_cache:
            # Merge results
            existing = _aggregation_cache[cache_key]
            existing_results = existing.get("data", {}).get("results", {})
            new_results = results.get("data", {}).get("results", {})
            
            # Merge channel results
            merged_results = {**existing_results, **new_results}
            
            _aggregation_cache[cache_key] = {
                "data": {
                    "analysis_type": analysis_type,
                    "channels_analyzed": len(merged_results),
                    "results": merged_results,
                    "timestamp": datetime.now().isoformat(),
                    "merged": True
                }
            }
        else:
            # Store new results
            _aggregation_cache[cache_key] = results
        
        return {
            "success": True,
            "data": {
                "stored": True,
                "cache_key": cache_key,
                "channels_in_cache": len(_aggregation_cache[cache_key].get("data", {}).get("results", {}))
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Error storing results: {str(e)}",
                "tool": "store_aggregation_results"
            },
            "data": None
        }


def get_aggregation_results(
    user_id: str,
    analysis_type: str
) -> Dict[str, Any]:
    """Retrieve previously stored aggregation results."""
    cache_key = _get_cache_key(user_id, analysis_type)
    
    if cache_key not in _aggregation_cache:
        return {
            "success": False,
            "error": {
                "type": "not_found",
                "message": f"No stored results found for {analysis_type}",
                "tool": "get_aggregation_results"
            },
            "data": None
        }
    
    return {
        "success": True,
        "data": _aggregation_cache[cache_key],
        "error": None
    }


def merge_and_rank_results(
    user_id: str,
    analysis_type: str,
    ranking_field: str = "threads_with_replies",
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Retrieve stored results, merge if needed, and return ranked results.
    
    Args:
        user_id: User ID
        analysis_type: Type of analysis
        ranking_field: Field to rank by (e.g., "threads_with_replies", "total_messages", "engagement_rate_percent")
        top_n: Number of top results to return
    """
    try:
        cache_key = _get_cache_key(user_id, analysis_type)
        
        if cache_key not in _aggregation_cache:
            return {
                "success": False,
                "error": {
                    "type": "not_found",
                    "message": "No results to rank. Run analyze_channels_batch first.",
                    "tool": "merge_and_rank_results"
                },
                "data": None
            }
        
        stored = _aggregation_cache[cache_key]
        results = stored.get("data", {}).get("results", {})
        
        # Rank channels by the specified field
        ranked = []
        for channel_id, data in results.items():
            value = data.get(ranking_field, 0)
            ranked.append({
                "channel_id": channel_id,
                "channel_name": data.get("channel_name", "unknown"),
                ranking_field: value,
                **data
            })
        
        # Sort by ranking field (descending)
        ranked.sort(key=lambda x: x.get(ranking_field, 0), reverse=True)
        
        return {
            "success": True,
            "data": {
                "analysis_type": analysis_type,
                "ranking_field": ranking_field,
                "total_channels": len(ranked),
                "top_results": ranked[:top_n],
                "all_results": ranked
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "unknown_error",
                "message": f"Error ranking results: {str(e)}",
                "tool": "merge_and_rank_results"
            },
            "data": None
        }

