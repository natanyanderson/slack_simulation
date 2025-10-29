"""
Scheduled Events - Daily standups, status summaries, and time-based triggers
"""
import threading
import time
from datetime import datetime, timedelta
from .progression import get_or_create_state, PHASE_ORDER
from .user_registry import load_user_personas
from .slack_user_post import user_post_message
from .persona_registry import PERSONAS, CHANNEL_NAME_TO_ID

USER_PERSONAS = load_user_personas()

def schedule_daily_standup():
    """Schedule daily standup at 9:30 AM"""
    def run():
        while True:
            now = datetime.now()
            # Schedule for 9:30 AM if not already passed today
            target_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
            
            if now > target_time:
                # Move to tomorrow
                target_time += timedelta(days=1)
            
            # Calculate seconds until target time
            seconds_until = (target_time - now).total_seconds()
            time.sleep(seconds_until)
            
            # Trigger standup
            trigger_standup()
            
            # Sleep for 24 hours minus the wait time
            time.sleep(86400 - seconds_until)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("[SCHEDULED] Daily standup scheduled for 9:30 AM")

def schedule_status_summary():
    """Schedule status summary at 5:30 PM"""
    def run():
        while True:
            now = datetime.now()
            # Schedule for 5:30 PM if not already passed today
            target_time = now.replace(hour=17, minute=30, second=0, microsecond=0)
            
            if now > target_time:
                # Move to tomorrow
                target_time += timedelta(days=1)
            
            # Calculate seconds until target time
            seconds_until = (target_time - now).total_seconds()
            time.sleep(seconds_until)
            
            # Trigger status summary
            trigger_status_summary()
            
            # Sleep for 24 hours minus the wait time
            time.sleep(86400 - seconds_until)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("[SCHEDULED] Status summary scheduled for 5:30 PM")

def trigger_standup():
    """Trigger a daily standup post"""
    from .agent_engine import generate_reply
    
    channels = ["eng-backend", "eng-frontend", "product"]
    channel_name = channels[datetime.now().weekday() % len(channels)]  # Rotate channels
    
    ch_id = CHANNEL_NAME_TO_ID.get(channel_name)
    if not ch_id:
        print(f"[SCHEDULED] Channel {channel_name} not found")
        return
    
    # PM or TPM typically posts standup
    persona = "Gabriella_PM" if channel_name == "product" else "Tara_TPM"
    
    prompt = "Post a daily standup: Ask the team to share what they're working on today and any blockers."
    result = generate_reply(persona, channel_name, ch_id, prompt, thread_ts=None, phase_context="")
    
    identity = USER_PERSONAS.get(persona)
    if identity:
        try:
            user_post_message(identity, ch_id, result["text"], thread_ts=None)
            print(f"[SCHEDULED] Standup triggered in #{channel_name}")
        except Exception as e:
            print(f"[SCHEDULED] Error posting standup: {e}")

def trigger_status_summary():
    """Trigger an end-of-day status summary"""
    from .agent_engine import generate_reply
    
    ch_name = "product"
    ch_id = CHANNEL_NAME_TO_ID.get(ch_name)
    if not ch_id:
        print(f"[SCHEDULED] Channel {ch_name} not found")
        return
    
    # TPM posts status summaries
    persona = "Tara_TPM"
    
    prompt = "Post an end-of-day status summary: Brief overview of progress, blockers, and tomorrow's priorities."
    result = generate_reply(persona, ch_name, ch_id, prompt, thread_ts=None, phase_context="")
    
    identity = USER_PERSONAS.get(persona)
    if identity:
        try:
            user_post_message(identity, ch_id, result["text"], thread_ts=None)
            print(f"[SCHEDULED] Status summary triggered in #{ch_name}")
        except Exception as e:
            print(f"[SCHEDULED] Error posting status summary: {e}")

def start_scheduled_events():
    """Start all scheduled event threads"""
    schedule_daily_standup()
    schedule_status_summary()
    print("[SCHEDULED] All scheduled events started")

