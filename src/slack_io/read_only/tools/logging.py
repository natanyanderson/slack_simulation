"""
Structured logging for tool calls.
"""
import json
import logging
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from .config import TOOL_CONFIG


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add any extra fields
        if hasattr(record, "tool_call"):
            log_entry["tool_call"] = record.tool_call
        if hasattr(record, "execution"):
            log_entry["execution"] = record.execution
        
        return json.dumps(log_entry)


# Configure logger
logger = logging.getLogger("slack_tools")
logger.setLevel(getattr(logging, TOOL_CONFIG["logging"]["log_level"]))

# Create file handler if logging is enabled
if TOOL_CONFIG["logging"]["enabled"]:
    handler = logging.FileHandler(TOOL_CONFIG["logging"]["log_file"])
    if TOOL_CONFIG["logging"]["log_format"] == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    logger.addHandler(handler)


def hash_params(params: Dict[str, Any]) -> str:
    """Create a hash of parameters (for logging, not storing raw params)."""
    # Sort keys for consistent hashing
    sorted_params = json.dumps(params, sort_keys=True)
    return hashlib.sha256(sorted_params.encode()).hexdigest()[:16]


def log_tool_call_start(
    request_id: str,
    user_id: str,
    channel_id: Optional[str],
    tool_name: str,
    endpoint: str,
    params: Dict[str, Any]
):
    """Log the start of a tool call."""
    params_hash = hash_params(params)
    params_summary = {
        k: v for k, v in params.items() 
        if k not in ["token", "auth", "password"]  # Exclude sensitive fields
    }
    
    log_data = {
        "request_id": request_id,
        "user_id": user_id,
        "channel_id": channel_id,
        "tool_call": {
            "name": tool_name,
            "endpoint": endpoint,
            "params_hash": f"sha256:{params_hash}",
            "params_summary": params_summary
        }
    }
    
    extra = {"tool_call": log_data}
    logger.info("Tool call started", extra=extra)


def log_tool_call_complete(
    request_id: str,
    duration_ms: float,
    success: bool,
    error_type: Optional[str],
    items_returned: int,
    pages_fetched: int = 1
):
    """Log the completion of a tool call."""
    log_data = {
        "request_id": request_id,
        "execution": {
            "duration_ms": duration_ms,
            "success": success,
            "error_type": error_type,
            "items_returned": items_returned,
            "pages_fetched": pages_fetched
        }
    }
    
    extra = {"execution": log_data}
    level = logging.INFO if success else logging.ERROR
    logger.log(level, "Tool call completed", extra=extra)
