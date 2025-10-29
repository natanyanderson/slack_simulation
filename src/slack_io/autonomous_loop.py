"""
Autonomous simulation loop that mimics slackbench_sim but posts to real Slack.
This creates a hybrid: autonomous conversation generation + real Slack interaction.
"""
import time, random, logging, threading
from typing import List, Dict
from .slack_client import app as bolt_app
from .persona_registry import PERSONAS, CHANNEL_POLICY, CHANNEL_ID_TO_NAME, CHANNEL_NAME_TO_ID
from .agent_engine import generate_reply
from .queue import ChannelQueue
from .user_registry import load_user_personas
from .slack_user_post import user_post_message

logger = logging.getLogger(__name__)

# Load user personas for posting as real users
USER_PERSONAS = load_user_personas()

# Track what's been posted to avoid duplicating
posted_messages = {}  # track recent messages
SIMULATION_HISTORY = []  # in-memory conversation history

TURN_INTERVAL_S = 25  # Reduced from 45s to 25s - more frequent messages
PERSONA_COOLDOWN_S = 30  # Reduced from 60s to 30s - more persona activity

def _get_channel_id(channel_name: str) -> str:
    """Get channel ID from name"""
    if channel_name in CHANNEL_NAME_TO_ID:
        return CHANNEL_NAME_TO_ID[channel_name]
    try:
        resp = bolt_app.client.conversations_list(types="public_channel,private_channel")
        for ch in resp.get("channels", []):
            if ch["name"] == channel_name:
                CHANNEL_ID_TO_NAME[ch["id"]] = ch["name"]
                CHANNEL_NAME_TO_ID[ch["name"]] = ch["id"]
                return ch["id"]
    except Exception:
        pass
    return None

def _format_history_for_prompt(sim_history: List[Dict], channel: str, limit: int = 10) -> str:
    """Format simulation history for LLM prompt"""
    relevant = [m for m in sim_history if m.get("channel") == channel][-limit:]
    lines = []
    for m in relevant:
        user = m.get("user", "unknown")
        text = m.get("text", "")[:120].replace("\n", " ")
        lines.append(f"[{user}] {text}")
    return "\n".join(lines[-limit:])

def autonomous_turn():
    """Generate and post one autonomous message (one simulation turn)"""
    try:
        # Pick a random active channel
        active_channels = [ch for ch, pol in CHANNEL_POLICY.items() if pol.get("p_reply", 0) > 0.3]
        if not active_channels:
            logger.info("[AUTONOMOUS] No active channels available")
            return
        
        channel_name = random.choice(active_channels)
        channel_id = _get_channel_id(channel_name)
        
        if not channel_id:
            logger.warning(f"[AUTONOMOUS] Could not find channel ID for {channel_name}")
            return
        
        # Get eligible personas for this channel
        policy = CHANNEL_POLICY.get(channel_name)
        if not policy:
            return
        
        eligible_personas = [p for p in policy.get("candidates", [])]
        if not eligible_personas:
            return
        
        # Pick a persona
        persona = random.choice(eligible_personas)
        persona_cfg = PERSONAS[persona]
        
        # Decide if this is a new message or reply to thread
        is_reply = len(SIMULATION_HISTORY) > 0 and random.random() < 0.6
        
        if is_reply and SIMULATION_HISTORY:
            # Reply to recent message
            recent_msg = random.choice(SIMULATION_HISTORY[-5:])
            thread_ts = recent_msg.get("thread_ts") or recent_msg.get("ts")
            parent_text = recent_msg.get("text", "")
            
            # Generate reply
            context = _format_history_for_prompt(SIMULATION_HISTORY, channel_name, limit=8)
            
            # Use the agent engine to generate reply
            result = generate_reply(
                persona, 
                channel_name, 
                channel_id,
                f"In response to: {parent_text[:150]}", 
                thread_ts=thread_ts
            )
            
            post_text = result["text"]
            
            # Post to Slack in thread AS THE USER (xoxp token)
            identity = USER_PERSONAS.get(persona)
            if not identity:
                logger.warning(f"[AUTONOMOUS] No user token for {persona}; skipping reply in #{channel_name}")
                return
            
            user_post_message(identity, channel_id, post_text, thread_ts=thread_ts)
            
            username = persona_cfg["username"]
            
            logger.info(f"[AUTONOMOUS] {persona} replied in thread in #{channel_name}")
            
            # Add to simulation history
            SIMULATION_HISTORY.append({
                "user": username,
                "text": post_text,
                "channel": channel_name,
                "thread_ts": thread_ts,
                "ts": thread_ts,
                "timestamp": time.time()
            })
            
        else:
            # New top-level message
            context = _format_history_for_prompt(SIMULATION_HISTORY, channel_name, limit=6)
            
            # Generate a proactive message based on role
            from .agent_engine import _get_role_guidance
            
            role = persona_cfg.get("role", "")
            guidance = _get_role_guidance(role)
            prompt = f"Contribute to the channel discussion with your perspective."
            
            result = generate_reply(
                persona,
                channel_name,
                channel_id,
                prompt,  # Simple, natural prompt
                thread_ts=None
            )
            
            post_text = result["text"]
            
            # Post to Slack AS THE USER (xoxp token)
            identity = USER_PERSONAS.get(persona)
            if not identity:
                logger.warning(f"[AUTONOMOUS] No user token for {persona}; skipping message in #{channel_name}")
                return
            
            resp = user_post_message(identity, channel_id, post_text, thread_ts=None)
            
            ts = resp["ts"] if resp else None
            username = persona_cfg["username"]
            
            logger.info(f"[AUTONOMOUS] {persona} posted new message in #{channel_name}")
            
            # Add to simulation history
            SIMULATION_HISTORY.append({
                "user": username,
                "text": post_text,
                "channel": channel_name,
                "thread_ts": ts,
                "ts": ts,
                "timestamp": time.time()
            })
        
        # Trim history to keep it manageable (last 100 messages)
        if len(SIMULATION_HISTORY) > 100:
            SIMULATION_HISTORY[:] = SIMULATION_HISTORY[-100:]
            
    except Exception as e:
        logger.error(f"[AUTONOMOUS] Error in autonomous turn: {e}", exc_info=True)

def start_autonomous_loop():
    """Start the autonomous simulation loop in a background thread"""
    def run_loop():
        logger.info("[AUTONOMOUS] Starting autonomous conversation loop")
        while True:
            try:
                time.sleep(TURN_INTERVAL_S)
                autonomous_turn()
            except Exception as e:
                logger.error(f"[AUTONOMOUS] Error in loop: {e}", exc_info=True)
                time.sleep(5)  # Brief pause before retry
    
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    logger.info(f"[AUTONOMOUS] Autonomous loop started (turn interval: {TURN_INTERVAL_S}s)")

def add_real_message_to_history(event: dict):
    """Add a real Slack message to the simulation history (for hybrid mode)"""
    try:
        text = event.get("text", "")
        user = event.get("username") or event.get("user", "unknown")
        channel_id = event.get("channel")
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        
        # Get channel name
        channel_name = CHANNEL_ID_TO_NAME.get(channel_id, channel_id)
        
        SIMULATION_HISTORY.append({
            "user": user,
            "text": text,
            "channel": channel_name,
            "thread_ts": thread_ts or ts,
            "ts": ts,
            "timestamp": time.time(),
            "real": True  # Mark as real message
        })
        
        # Trim if needed
        if len(SIMULATION_HISTORY) > 100:
            SIMULATION_HISTORY[:] = SIMULATION_HISTORY[-100:]
            
    except Exception as e:
        logger.error(f"[AUTONOMOUS] Error adding message to history: {e}", exc_info=True)
