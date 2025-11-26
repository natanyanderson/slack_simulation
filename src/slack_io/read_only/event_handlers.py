"""
Event handlers for read-only assistant.
Handles DMs, @mentions, and slash commands.
"""
import logging
import time
from typing import Set
from slack_bolt import App
from .assistant import handle_dm, handle_mention, handle_slash_command

logger = logging.getLogger(__name__)

# Track processed events to prevent duplicate processing
# Format: {event_id: timestamp} or {(channel_id, ts): timestamp}
_processed_events: Set[str] = set()
_event_cache_ttl = 300  # 5 minutes
_last_cleanup = time.time()


def _get_event_key(body: dict, event: dict) -> str:
    """
    Generate a unique key for an event to track duplicates.
    Uses event_id from body if available, otherwise falls back to channel+ts.
    """
    # Try to get event_id from the body payload (Socket Mode structure)
    # body structure: {"payload": {"event_id": "...", "event": {...}}}
    payload = body.get("payload", {})
    event_id = payload.get("event_id")
    if event_id:
        return f"event_id:{event_id}"
    
    # Also check top-level body for event_id
    event_id = body.get("event_id")
    if event_id:
        return f"event_id:{event_id}"
    
    # Fallback to channel + ts (unique per message)
    channel = event.get("channel")
    ts = event.get("ts")
    if channel and ts:
        return f"channel_ts:{channel}:{ts}"
    
    # Last resort: use client_msg_id if available
    client_msg_id = event.get("client_msg_id")
    if client_msg_id:
        return f"client_msg_id:{client_msg_id}"
    
    # Final fallback: use text hash + user + channel (for DMs without ts)
    text = event.get("text", "")
    user = event.get("user")
    if text and user and channel:
        text_hash = hash(text[:100])  # Use first 100 chars
        return f"text_hash:{user}:{channel}:{text_hash}"
    
    return None


def _is_duplicate_event(event_key: str) -> bool:
    """
    Check if an event has already been processed.
    Also cleans up old entries periodically.
    """
    global _last_cleanup, _processed_events
    
    # Clean up old entries every 5 minutes
    current_time = time.time()
    if current_time - _last_cleanup > _event_cache_ttl:
        _processed_events.clear()
        _last_cleanup = current_time
        logger.debug(f"[BOLT] Cleared event cache (size was {len(_processed_events)})")
    
    if not event_key:
        return False
    
    if event_key in _processed_events:
        logger.info(f"[BOLT] Duplicate event detected, skipping: {event_key}")
        return True
    
    # Mark as processed
    _processed_events.add(event_key)
    return False


def register_event_handlers(app: App, bot_user_id: str = None):
    """
    Register event handlers for read-only assistant.
    
    Args:
        app: Slack Bolt App instance
        bot_user_id: Bot user ID for mention detection (optional)
    """
    
    @app.event("message")
    def handle_message_events(body, event, logger, say):
        """
        Handle all messages. Check for DMs first, then mentions.
        """
        # Check for duplicate events
        event_key = _get_event_key(body, event)
        if event_key and _is_duplicate_event(event_key):
            logger.info(f"[BOLT] Duplicate event skipped: {event_key}")
            return  # Skip duplicate
        elif not event_key:
            ch = event.get("channel")
            ts = event.get("ts")
            logger.warning(f"[BOLT] Could not generate event key for message - Channel: {ch}, TS: {ts}. Proceeding anyway.")
        
        ch = event.get("channel")
        ts = event.get("ts")
        subtype = event.get("subtype")
        username = event.get("username", "unknown")
        text_preview = event.get("text", "")[:50]
        channel_type = event.get("channel_type")
        
        logger.info(f"[BOLT] Received message - Channel: {ch}, TS: {ts}, Subtype: {subtype}, User: {username}, Channel Type: {channel_type}, Text: {text_preview}..., Event Key: {event_key}")
        
        # Check if this is a DM (channel IDs starting with 'D' are DMs)
        # Also check channel_type for 'im'
        is_dm = (channel_type == "im") or (ch and ch.startswith("D"))
        if is_dm and not subtype:
            # This is a direct message to the bot
            logger.info(f"[BOLT] Detected DM (channel={ch}), routing to read-only assistant")
            try:
                handle_dm(event, say)
            except Exception as e:
                logger.error(f"[BOLT] Error handling DM: {e}", exc_info=True)
            return
        
        # Check if bot is mentioned in the message
        text = event.get("text", "")
        if bot_user_id and f"<@{bot_user_id}>" in text and not subtype:
            logger.info(f"[BOLT] Detected @mention, routing to read-only assistant")
            try:
                handle_mention(event, say)
            except Exception as e:
                logger.error(f"[BOLT] Error handling mention: {e}", exc_info=True)
            return


    @app.event("app_mention")
    def handle_app_mention(body, event, say, logger):
        """
        Handle @mentions of the bot (alternative handler).
        This is more reliable than parsing mentions in message handler.
        """
        # Check for duplicate events
        event_key = _get_event_key(body, event)
        if _is_duplicate_event(event_key):
            return  # Skip duplicate
        
        logger.info(f"[BOLT] Received app_mention event")
        try:
            handle_mention(event, say)
        except Exception as e:
            logger.error(f"[BOLT] Error handling app_mention: {e}", exc_info=True)


    @app.command("/slackbench")
    def handle_slackbench_command(ack, command, respond, logger):
        """
        Handle /slackbench slash command.
        """
        logger.info(f"[BOLT] Received /slackbench command from {command.get('user_id')}")
        try:
            handle_slash_command(ack, command, respond)
        except Exception as e:
            logger.error(f"[BOLT] Error handling slash command: {e}", exc_info=True)
            respond(text=f"Error: {str(e)}", response_type="ephemeral")

