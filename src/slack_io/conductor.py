# conductor.py
import time, random, json, logging
from typing import Dict, List
from .slack_client import app as bolt_app
from .persona_registry import PERSONAS, CHANNEL_POLICY, CHANNEL_ID_TO_NAME, CHANNEL_NAME_TO_ID
from .user_registry import load_user_personas
from .slack_user_post import user_post_message
from .agent_engine import generate_reply
from .channel_queue import ChannelQueue
from .progression import load_states, get_or_create_state, advance_phase, PHASE_ORDER

logger = logging.getLogger(__name__)

STRICT_HINT = "\n(If you did not include [[ref:TIMESTAMP]] for at least one context line, add them now.)"
USER_PERSONAS = load_user_personas()  # persona_name -> PersonaIdentity (with xoxp token)
THREAD_STATES = load_states()  # Global thread states cache

# No strict citation requirements - let messages flow naturally

CHANNEL_QUEUES: Dict[str, ChannelQueue] = {}
THREAD_STATE: Dict[str, dict] = {}  # key: thread_ts -> {turns, last_persona, last_ts}
PERSONA_COOLDOWN: Dict[str, float] = {}  # persona -> epoch seconds when they can speak again

# knobs
MAX_TURNS_PER_THREAD = 8
MIN_DELAY_S, MAX_DELAY_S = 1, 3         # Reduced from 2-8s to 1-3s for faster responses
PERSONA_COOLDOWN_S = 12                 # Reduced from 25s to 12s for more activity
SELF_REPLY_GRACE_S = 2                  # Reduced from 4s to 2s for quicker replies
MAX_ACTIVE_THREADS = 8                  # Increased from 5 to 8 for more concurrent threads

# Time-based response latency
WORK_HOURS_MIN_DELAY = 15  # Minimum 15s during work hours
WORK_HOURS_MAX_DELAY = 120  # Maximum 120s during work hours
NON_OWNER_DELAY_MULTIPLIER = 1.5  # Non-owners take 1.5x longer
WEEKEND_DELAY_MULTIPLIER = 3.0  # Weekend responses are much slower

# Handoff & ownership tracking
OWNER_SILENCE_THRESHOLD_M = 15  # If owner silent for N minutes, escalate

# Proactive posting (to create more conversation opportunities)
PROACTIVE_POST_INTERVAL_S = 90  # Reduced from 180s to 90s - check every 1.5 minutes
LAST_PROACTIVE_CHECK = 0  # Last time we checked for proactive posts

# Track persona message counts per thread
PERSONA_THREAD_MSG_COUNT: Dict[str, Dict[str, int]] = {}  # thread_key -> {persona: count}

# Track closed threads to prevent follow-ups
CLOSED_THREAD_FOLLOWUPS: set = set()  # Set of closed thread keys

# Track message lengths for variation
LAST_MESSAGE_LENGTH: str = "medium"  # Track to alternate

def maybe_add_lurker_reactions(channel_id: str, thread_ts: str):
    """Randomly add reactions from lurkers to make threads feel alive"""
    import random
    
    if random.random() > 0.3:  # 30% chance
        return
    
    # Pick a random lurker who isn't the owner
    from .persona_registry import PERSONAS
    all_personas = list(PERSONAS.keys())
    
    # Get thread state to avoid owner
    state = get_state(channel_id, thread_ts, THREAD_STATES)
    if state and state.owner:
        all_personas = [p for p in all_personas if p != state.owner]
    
    if not all_personas:
        return
    
    lurker = random.choice(all_personas[:3])  # Pick from first 3 eligible
    identity = USER_PERSONAS.get(lurker)
    
    if identity and random.random() > 0.5:  # 50% chance to react
        reactions = [":+1:", ":eyes:", ":white_check_mark:", ":rocket:"]
        reaction = random.choice(reactions)
        
        try:
            identity.client.reactions_add(channel=channel_id, timestamp=thread_ts, name=reaction)
            logger.info(f"[REACTIONS] {lurker} added {reaction} to thread")
        except Exception as e:
            logger.debug(f"[REACTIONS] Error adding reaction: {e}")

def is_within_office_hours(persona: str) -> bool:
    """Check if current time is within persona's office hours"""
    from datetime import datetime
    from .persona_registry import PERSONAS
    
    persona_cfg = PERSONAS.get(persona)
    if not persona_cfg or "office_hours" not in persona_cfg:
        return True  # Default to allowed
    
    # Special case: SRE is available 24/7 for pages
    if persona == "Nina_SRE":
        return True
    
    start_hour, end_hour = persona_cfg["office_hours"]
    current_hour = datetime.now().hour
    current_weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
    
    # Auto-silence nights/weekends (except SRE)
    if current_weekday >= 5:  # Saturday or Sunday
        return False
    
    return start_hour <= current_hour < end_hour

def calculate_response_latency(persona: str, is_owner: bool = False) -> float:
    """Calculate response latency based on persona and owner status"""
    import random
    from datetime import datetime
    
    # Base delay during work hours
    base_delay = random.uniform(WORK_HOURS_MIN_DELAY, WORK_HOURS_MAX_DELAY)
    
    # Non-owners take longer
    if not is_owner:
        base_delay *= NON_OWNER_DELAY_MULTIPLIER
    
    # Weekend responses are much slower (if SRE)
    current_weekday = datetime.now().weekday()
    if current_weekday >= 5 and persona != "Nina_SRE":
        base_delay *= WEEKEND_DELAY_MULTIPLIER
    
    return base_delay

def persona_quota_exceeded(persona: str, thread_state) -> bool:
    """Check if persona has exceeded their quota for this phase"""
    from .persona_registry import PERSONAS
    from .progression import PHASE_ORDER
    
    persona_cfg = PERSONAS.get(persona)
    if not persona_cfg or "quota_per_phase" not in persona_cfg:
        return False  # Default to not exceeded
    
    quota = persona_cfg["quota_per_phase"]
    
    # Count messages from this persona in this thread
    thread_key = f"{thread_state.chan}:{thread_state.root_ts}"
    if thread_key not in PERSONA_THREAD_MSG_COUNT:
        PERSONA_THREAD_MSG_COUNT[thread_key] = {}
    
    persona_count = PERSONA_THREAD_MSG_COUNT[thread_key].get(persona, 0)
    
    # Reset count when phase changes
    if thread_state.phase not in PERSONA_THREAD_MSG_COUNT.get("phase", ""):
        PERSONA_THREAD_MSG_COUNT[thread_key] = {persona: 0}
        return False
    
    return persona_count >= quota

def role_should_speak(persona: str, phase: str) -> bool:
    """Check if persona's role should speak in this phase"""
    from .persona_registry import PERSONAS
    
    persona_cfg = PERSONAS.get(persona)
    if not persona_cfg or "role_triggers" not in persona_cfg:
        return True  # Default to allowed
    
    role_triggers = persona_cfg["role_triggers"]
    return phase in role_triggers

def _queue_for(channel_id: str) -> ChannelQueue:
    if channel_id not in CHANNEL_QUEUES:
        CHANNEL_QUEUES[channel_id] = ChannelQueue(bolt_app.client, cooldown=0.8)  # Reduced from 1.1s to 0.8s
    return CHANNEL_QUEUES[channel_id]

def _channel_name(channel_id: str) -> str:
    name = CHANNEL_ID_TO_NAME.get(channel_id)
    if name: return name
    try:
        info = bolt_app.client.conversations_info(channel=channel_id)
        name = info["channel"]["name"]
        CHANNEL_ID_TO_NAME[channel_id] = name
        return name
    except Exception:
        return channel_id

def _eligible_personas(ch_name: str, exclude: List[str]) -> List[str]:
    policy = CHANNEL_POLICY.get(ch_name)
    if not policy:
        return []
    pool = [p for p in policy["candidates"] if p not in exclude]
    now = time.time()
    pool = [p for p in pool if PERSONA_COOLDOWN.get(p, 0) < now]
    return pool

def _update_state(thread_ts: str, persona: str, ts: float):
    st = THREAD_STATE.setdefault(thread_ts, {"turns": 0, "last_persona": None, "last_ts": 0.0})
    st["turns"] += 1
    st["last_persona"] = persona
    st["last_ts"] = ts
    PERSONA_COOLDOWN[persona] = time.time() + PERSONA_COOLDOWN_S

def _count_active_threads(channel_id: str, within_seconds: float = 60) -> int:
    """Count threads that have been active recently in this channel"""
    now = time.time()
    count = 0
    for thread_ts, state in THREAD_STATE.items():
        # Simple heuristic: if thread had activity in last N seconds, it's active
        if state.get("last_ts", 0) > (now - within_seconds):
            # We don't track channel_id in thread state, so this is approximate
            # but sufficient for basic throttling
            count += 1
    return count

def _should_skip(event: dict) -> bool:
    # Avoid infinite loops and bursts
    thread_ts = event.get("thread_ts") or event.get("ts")
    st = THREAD_STATE.get(thread_ts)
    if st and st["turns"] >= MAX_TURNS_PER_THREAD:
        logger.info(f"[CONDUCTOR] Thread {thread_ts} reached max turns ({MAX_TURNS_PER_THREAD})")
        return True
    # If the last post in thread is very recent, back off a bit
    if st and (time.time() - st["last_ts"] < SELF_REPLY_GRACE_S):
        logger.info(f"[CONDUCTOR] Thread {thread_ts} too recent (grace period)")
        return True
    
    # Check if we have too many active threads
    active_threads = _count_active_threads(event.get("channel", ""))
    if active_threads >= MAX_ACTIVE_THREADS:
        logger.info(f"[CONDUCTOR] Too many active threads ({active_threads} >= {MAX_ACTIVE_THREADS})")
        return True
    
    return False

def _fanout_count(ch_name: str) -> int:
    # 1–3 responders based on channel “busyness”
    if ch_name in ("sre-ops","eng-backend","deployments"): return random.choice([1,2,2,3])
    if ch_name in ("product","qa-testing","eng-frontend"): return random.choice([1,2])
    return 1

def maybe_handle_event(event: dict):
    logger.info(f"{'='*60}")
    logger.info(f"[CONDUCTOR] NEW EVENT RECEIVED")
    logger.info(f"[CONDUCTOR] Channel: {event.get('channel')}")
    logger.info(f"[CONDUCTOR] Timestamp: {event.get('ts')}")
    logger.info(f"[CONDUCTOR] Thread TS: {event.get('thread_ts')}")
    logger.info(f"[CONDUCTOR] Text: {event.get('text', '')[:100]}")
    logger.info(f"[CONDUCTOR] Subtype: {event.get('subtype')}")
    logger.info(f"[CONDUCTOR] Username: {event.get('username')}")
    logger.info(f"{'='*60}")
    
    # Periodically check if we should trigger proactive posts
    maybe_trigger_proactive_post()
    
    channel_id = event["channel"]
    ts = event["ts"]
    text = event.get("text","") or ""
    thread_ts = event.get("thread_ts") or ts
    ch_name = _channel_name(channel_id)
    
    # Only skip if this is a known non-persona bot message
    # We WANT personas to be able to reply to each other
    subtype = event.get("subtype")
    username = event.get("username") or ""
    user = event.get("user", "")
    
    # Get list of persona usernames for matching
    persona_usernames = [PERSONAS[p]["username"] for p in PERSONAS]
    
    logger.info(f"[CONDUCTOR] Event details - subtype: {subtype}, username: {username}, user: {user}")
    logger.info(f"[CONDUCTOR] Persona usernames: {persona_usernames}")
    
    # Skip only if this is a bot message from a bot we don't know about
    if subtype == "bot_message":
        # Allow if username matches a persona
        if username in persona_usernames:
            logger.info(f"[CONDUCTOR] Allowing bot message from persona: {username}")
        elif user and user.startswith("B"):  # Slack bot user IDs start with 'B'
            logger.info(f"[CONDUCTOR] Skipping bot message from unknown bot (user: {user})")
            return
        # If no clear indicator, be permissive and allow it
        else:
            logger.info(f"[CONDUCTOR] Ambiguous bot message, allowing: subtype={subtype}, username={username}, user={user}")
    

    # Gate by channel policy & reply probability
    policy = CHANNEL_POLICY.get(ch_name)
    if not policy:
        logger.info(f"[CONDUCTOR] No policy for #{ch_name} ({channel_id})")
        return
    if random.random() > policy["p_reply"]:
        logger.info(f"[CONDUCTOR] Random skip (p_reply threshold)")
        return
    if _should_skip(event):
        return

    # Check if message is from a known persona (to avoid self-replies)
    sender_username = event.get("username") or event.get("user", "")
    sender_is_persona = sender_username and any(PERSONAS[p]["username"] == sender_username for p in PERSONAS)
    
    # If the sender is one of our personas, we need to be more careful
    # Allow replies to persona messages, but exclude the sender from replying
    logger.info(f"[CONDUCTOR] Processing event from {'persona ' + sender_username if sender_is_persona else 'human'} in #{ch_name}")

    # Determine how many personas reply
    n_repliers = _fanout_count(ch_name)

    # Avoid the same persona replying twice in a row
    exclude = []
    st = THREAD_STATE.get(thread_ts)
    if st and st.get("last_persona"):
        exclude.append(st["last_persona"])
    
    # Also exclude the sender if they're a persona
    if sender_is_persona:
        for p in PERSONAS:
            if PERSONAS[p]["username"] == sender_username:
                exclude.append(p)
                break

    eligible = _eligible_personas(ch_name, exclude)
    if not eligible:
        logger.info(f"[CONDUCTOR] No eligible personas for #{ch_name}")
        logger.info(f"[CONDUCTOR] Excluded personas: {exclude}")
        logger.info(f"[CONDUCTOR] Persona cooldowns: {[(p, round(PERSONA_COOLDOWN.get(p, 0) - time.time(), 1)) for p in PERSONAS if PERSONA_COOLDOWN.get(p, 0) > time.time()]}")
        return

    repliers = random.sample(eligible, k=min(n_repliers, len(eligible)))
    logger.info(f"[CONDUCTOR] Selected {len(repliers)} repliers: {repliers}")

    # For each chosen persona, generate + post with small staggered delay
    # Determine if this is a thread reply (thread_ts != ts means it's a reply in a thread)
    is_thread = event.get("thread_ts") is not None
    original_ts = event.get("thread_ts") if is_thread else ts
    
    logger.info(f"[CONDUCTOR] Scheduling {len(repliers)} replies")
    logger.info(f"[CONDUCTOR] is_thread: {is_thread}, original_ts: {original_ts}")
    
    for i, persona in enumerate(repliers):
        delay = random.uniform(MIN_DELAY_S, MAX_DELAY_S) + i * 0.5  # Reduced stagger from 1.2s to 0.5s
        logger.info(f"[CONDUCTOR] Scheduling {persona} with {delay:.1f}s delay, is_thread={is_thread}")
        _schedule_reply(persona, ch_name, channel_id, text, original_ts, delay, is_thread)


def mark_persona_cooldown(persona: str, seconds: float = PERSONA_COOLDOWN_S):
    PERSONA_COOLDOWN[persona] = time.time() + seconds

def schedule_followups_for_thread(ch_name: str, channel_id: str, starter_persona: str, event_text: str, thread_ts: str, max_repliers: int | None = None):

    exclude = [starter_persona]
    eligible = _eligible_personas(ch_name, exclude)
    if not eligible:
        return
    
    n = max_repliers or _fanout_count(ch_name)
    repliers = random.sample(eligible, k=min(n, len(eligible)))

    for i, persona in enumerate(repliers):
        delay =  random.uniform(MIN_DELAY_S, MAX_DELAY_S) + i * 1.2
        _schedule_reply(persona, ch_name, channel_id, event_text, thread_ts, delay, is_thread=True)

def maybe_trigger_proactive_post():
    """Periodically have a persona post something new to keep conversations going"""
    import time as time_module
    global LAST_PROACTIVE_CHECK
    
    now = time_module.time()
    if now - LAST_PROACTIVE_CHECK < PROACTIVE_POST_INTERVAL_S:
        return
    
    LAST_PROACTIVE_CHECK = now
    
    try:
        # Pick a random channel and persona
        active_channels = [ch for ch, pol in CHANNEL_POLICY.items() if pol.get("p_reply", 0) > 0.4]
        if not active_channels:
            return
        
        ch_name = random.choice(active_channels)
        ch_id = CHANNEL_ID_TO_NAME.get(ch_name)
        if not ch_id:
            # Try to get it
            ch_id = _channel_name_inverse(ch_name)
        
        if not ch_id:
            logger.info(f"[CONDUCTOR] Could not get ID for channel {ch_name}")
            return
        
        # Get eligible personas for this channel
        eligible = _eligible_personas(ch_name, [])
        if not eligible:
            logger.info(f"[CONDUCTOR] No eligible personas for proactive post in {ch_name}")
            return
        
        persona = random.choice(eligible)
        
        # Generate a proactive message (e.g., status update, question, observation)
        prompts = [
            "Share a brief status update about your current work",
            "Ask for help or input on something you're working on",
            "Share an observation or insight related to your work",
            "Post a quick update about progress on your tasks",
        ]
        
        digest = _get_recent_digest(ch_id, limit=8)
        prompt = random.choice(prompts)
        
        from .agent_engine import generate_reply
        result = generate_reply(persona, ch_name, ch_id, prompt, thread_ts=None)
        
        # Post it AS THE USER (xoxp)
        identity = USER_PERSONAS.get(persona)
        if not identity:
            logger.warning(f"[CONDUCTOR] No user token for {persona}; skipping proactive post in #{ch_name}")
            return
        user_post_message(identity, ch_id, result["text"], thread_ts=None)
        mark_persona_cooldown(persona)
        logger.info(f"[CONDUCTOR] {persona} (user) posted proactive message in #{ch_name}")
        
    except Exception as e:
        logger.error(f"[CONDUCTOR] Error in proactive post: {e}", exc_info=True)

def _channel_name_inverse(ch_name: str) -> str:
    """Get channel ID from name"""
    ch_id = CHANNEL_NAME_TO_ID.get(ch_name)
    if ch_id:
        return ch_id
    # Try to look it up
    try:
        for ch_id, cached_name in CHANNEL_ID_TO_NAME.items():
            if cached_name == ch_name:
                return ch_id
        
        # If not found, try the API
        resp = bolt_app.client.conversations_list(types="public_channel,private_channel")
        for ch in resp.get("channels", []):
            if ch["name"] == ch_name:
                CHANNEL_ID_TO_NAME[ch["id"]] = ch["name"]
                CHANNEL_NAME_TO_ID[ch["name"]] = ch["id"]
                return ch["id"]
    except Exception:
        pass
    return None

def detect_fix_complete(text: str) -> bool:
    """Detect if a FIX message contains PR link and deployment artifact"""
    import re
    
    # Look for PR links: #123, PR#456, pull/123
    pr_pattern = r'#\d+|PR\s*#\d+|pull/\d+'
    has_pr = bool(re.search(pr_pattern, text))
    
    # Look for deployment artifacts: deployed, merged, released, version numbers
    deployment_keywords = ['deployed', 'merged', 'released', 'version', 'v\d+\.\d+']
    has_deployment = any(re.search(kw, text, re.IGNORECASE) for kw in deployment_keywords)
    
    return has_pr and has_deployment

def is_positive_review(text: str) -> bool:
    """Detect if review message is positive/approving"""
    positive_keywords = ['lgtm', 'approved', 'looks good', 'verified', 'passed', 'confirmed', 'working', 'resolve']
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in positive_keywords)

def trigger_review_phase(state, ch_name: str, channel_id: str, thread_ts: str, fix_persona: str):
    """Trigger REVIEW phase when FIX is complete"""
    from .progression import advance_phase, reassign_owner
    from .agent_engine import generate_reply
    import random
    
    # Advance to REVIEW phase
    advance_phase(state)
    
    # Reassign to reviewer (not the fixer)
    reviewers = ["Kevin_QA", "Nina_SRE", "Ravi_Staff"]
    reviewers = [r for r in reviewers if r != fix_persona]
    reviewer = random.choice(reviewers)
    reassign_owner(state, reviewer)
    
    # Generate review request
    message = f"Fix complete with PR and deployment. @{reviewer} please review and verify."
    result = generate_reply(
        "Tara_TPM",
        ch_name,
        channel_id,
        message,
        thread_ts=thread_ts,
        phase_context=""
    )
    
    identity = USER_PERSONAS.get("Tara_TPM")
    if identity:
        try:
            user_post_message(identity, channel_id, result["text"], thread_ts=thread_ts)
            logger.info(f"[CLOSEOUT] Triggered REVIEW phase with reviewer {reviewer}")
        except Exception as e:
            logger.error(f"[CLOSEOUT] Error triggering review: {e}")

def trigger_postmortem_and_close(state, ch_name: str, channel_id: str, thread_ts: str):
    """Trigger POSTMORTEM phase and then close the thread"""
    from .progression import advance_phase, reassign_owner, PHASE_ORDER
    from .agent_engine import generate_reply
    import random
    
    # Advance to POSTMORTEM phase
    advance_phase(state)
    
    # Reassign to PM or TPM for postmortem
    postmortem_persona = random.choice(["Gabriella_PM", "Tara_TPM"])
    reassign_owner(state, postmortem_persona)
    
    # Generate postmortem request
    message = f"Review approved. Post brief postmortem summary: root cause, fix, and prevention."
    result = generate_reply(
        postmortem_persona,
        ch_name,
        channel_id,
        message,
        thread_ts=thread_ts,
        phase_context=""
    )
    
    identity = USER_PERSONAS.get(postmortem_persona)
    if identity:
        try:
            user_post_message(identity, channel_id, result["text"], thread_ts=thread_ts)
            logger.info(f"[CLOSEOUT] Triggered POSTMORTEM phase with {postmortem_persona}")
            
            # Close the thread after brief delay
            def close_thread():
                import time as time_module
                time_module.sleep(10)  # Wait 10s for any final message
                
                # Advance to CLOSED
                advance_phase(state)
                closed_key = f"{state.chan}:{state.root_ts}"
                CLOSED_THREAD_FOLLOWUPS.add(closed_key)
                logger.info(f"[CLOSEOUT] Thread {closed_key} set to CLOSED")
            
            import threading
            threading.Thread(target=close_thread, daemon=True).start()
        except Exception as e:
            logger.error(f"[CLOSEOUT] Error triggering postmortem: {e}")

def escalate_ownership(state, ch_name: str, channel_id: str, thread_ts: str):
    """Escalate or reassign ownership when owner is silent"""
    from .progression import reassign_owner, advance_phase, reset_phase
    from .agent_engine import generate_reply
    import random
    
    logger.warning(f"[HANDOFF] Owner {state.owner} has been silent in phase {state.phase}")
    
    # Choose escalation persona (TPM or Staff)
    escalation_personas = ["Tara_TPM", "Ravi_Staff"]
    escalation_persona = random.choice(escalation_personas)
    
    # Determine action based on phase
    if state.phase in ["DETECT", "TRIAGE"]:
        # Early phase: reassign to appropriate owner based on issue type
        new_owner = random.choice(["Mike_BE", "Nina_SRE", "Kevin_QA"])
        reassign_owner(state, new_owner)
        
        message = f"@{state.owner} has been silent. Reassigning ownership to @{new_owner}. Please take action on this issue."
    elif state.phase in ["HYPOTHESIS", "EXPERIMENT", "FIX"]:
        # Mid phase: escalate with urgency
        message = f"@{state.owner} - blocking on your progress in {state.phase} phase. Status update needed."
    else:
        # Late phase: try to advance or close
        message = f"@{state.owner} - need confirmation on {state.phase} status. Can we move forward?"
    
        # Generate and post escalation message
    result = generate_reply(
        escalation_persona,
        ch_name,
        channel_id,
        message,
        thread_ts=thread_ts,
        phase_context=""
    )
    
    identity = USER_PERSONAS.get(escalation_persona)
    if identity:
        try:
            user_post_message(identity, channel_id, result["text"], thread_ts=thread_ts)
            logger.info(f"[HANDOFF] {escalation_persona} posted escalation for silent owner {state.owner}")
            
            # Optionally add reactions from lurkers
            maybe_add_lurker_reactions(channel_id, thread_ts)
        except Exception as e:
            logger.error(f"[HANDOFF] Error posting escalation: {e}")

def _get_recent_digest(ch_id: str, limit: int = 8) -> str:
    """Get recent messages as a digest string"""
    try:
        r = bolt_app.client.conversations_history(channel=ch_id, limit=limit)
        lines = []
        for m in reversed(r.get("messages", [])):
            if m.get("subtype") in {"message_changed", "channel_join", "channel_leave"}:
                continue
            u = m.get("user") or m.get("username", "user")
            t = (m.get("text") or "").replace("\n", " ")
            lines.append(f"{u}: {t[:120]}")
        return "\n".join(lines[-limit:])
    except Exception:
        return ""

def _schedule_reply(persona: str, ch_name: str, channel_id: str, event_text: str, thread_ts: str, delay_s: float, is_thread: bool = False):
    def _do():
        logger.info(f"[CONDUCTOR] {persona} replying {'in thread' if is_thread else 'top-level'} in #{ch_name}")

        # Initialize or update thread state and create phase guidance
        phase_context = ""
        hidden_guidance = ""
        if is_thread:
            state = get_or_create_state(channel_id, thread_ts, persona, THREAD_STATES)
            
            # Apply persona guards
            if not is_within_office_hours(persona):
                logger.info(f"[CONDUCTOR] Skipping {persona} - outside office hours")
                return
            
            if persona_quota_exceeded(persona, state):
                logger.info(f"[CONDUCTOR] Skipping {persona} - quota exceeded for phase {state.phase}")
                return
            
            if not role_should_speak(persona, state.phase):
                logger.info(f"[CONDUCTOR] Skipping {persona} - role not triggered for phase {state.phase}")
                return
            
            # Increment persona message count
            thread_key = f"{channel_id}:{thread_ts}"
            if thread_key not in PERSONA_THREAD_MSG_COUNT:
                PERSONA_THREAD_MSG_COUNT[thread_key] = {}
            PERSONA_THREAD_MSG_COUNT[thread_key][persona] = PERSONA_THREAD_MSG_COUNT[thread_key].get(persona, 0) + 1
            
            # Update owner activity timestamp if this persona is the owner
            if state.owner == persona:
                state.last_owner_activity = time.time()
                THREAD_STATES[thread_key] = state
            
            # Check for owner silence and trigger escalation if needed
            if state.owner and persona in ["Tara_TPM", "Ravi_Staff"]:
                time_since_owner_activity = (time.time() - state.last_owner_activity) / 60  # in minutes
                if time_since_owner_activity > OWNER_SILENCE_THRESHOLD_M:
                    # Owner has been silent - trigger escalation/reassignment
                    escalate_ownership(state, ch_name, channel_id, thread_ts)
                    return
            
            # Extract incomplete checklist items
            incomplete_items = [item for item in state.checklist if "✅" not in item]
            
            # Create visible phase context
            phase_context = f"[THREAD PHASE: {state.phase}] Current owner: {state.owner or 'unassigned'}"
            if state.checklist:
                all_items = ", ".join(state.checklist[-3:])  # Show last 3 items
                phase_context += f". Checklist: {all_items}"
            
            # Create hidden guidance for LLM
            if incomplete_items or state.phase != "CLOSED":
                next_phase_idx = PHASE_ORDER.index(state.phase)
                next_phase = PHASE_ORDER[next_phase_idx + 1] if next_phase_idx < len(PHASE_ORDER) - 1 else None
                
                hidden_guidance = f"\n[INTERNAL GUIDANCE] Current thread phase: {state.phase}"
                if incomplete_items:
                    hidden_guidance += f"\nIncomplete tasks: {', '.join(incomplete_items)}. Consider completing one of these or providing progress update."
                if next_phase:
                    hidden_guidance += f"\nPossible next phase: {next_phase}. Advance to this phase if you have concrete results (fix, data, decision)."
                hidden_guidance += "\n"
        
        # generate grounded reply (with strict retry if no refs were cited)
        # Combine phase context and hidden guidance
        full_context = phase_context + hidden_guidance if hidden_guidance else phase_context
        out = generate_reply(persona, ch_name, channel_id, event_text, thread_ts=thread_ts if is_thread else None, phase_context=full_context)
        visible_text = out["text"]
        supports = out.get("supports", [])

        # If this is a threaded reply and we failed to cite anything, try once more with a stricter cue.
        if is_thread and not supports:
            out2 = generate_reply(persona, ch_name, channel_id, event_text + STRICT_HINT, thread_ts=thread_ts)
            if out2.get("supports"):
                visible_text, supports = out2["text"], out2["supports"]

        # Check if thread is CLOSED - only allow one follow-up
        if is_thread:
            closed_thread_key = f"{channel_id}:{thread_ts}"
            if closed_thread_key in CLOSED_THREAD_FOLLOWUPS:
                logger.info(f"[CONDUCTOR] Thread {closed_thread_key} is closed, blocking additional follow-ups")
                return
            if state.phase == "CLOSED":
                # Mark as having received a follow-up
                CLOSED_THREAD_FOLLOWUPS.add(closed_thread_key)
        
        # Post AS THE USER (xoxp); do not set username/icon (Slack uses the user's profile)
        identity = USER_PERSONAS.get(persona)
        if not identity:
            logger.warning(f"[CONDUCTOR] No user token for {persona}; skipping reply in #{ch_name}")
            return

        if is_thread:
            user_post_message(identity, channel_id, visible_text, thread_ts=thread_ts)
        else:
            user_post_message(identity, channel_id, visible_text, thread_ts=None)

        _update_state(thread_ts, persona, time.time())
        logger.info(f"[CONDUCTOR] {persona} posted reply as real user")
        
        # Check for close-out mechanics
        if is_thread and state:
            if state.phase == "FIX" and detect_fix_complete(visible_text):
                # Force REVIEW phase when FIX is complete
                trigger_review_phase(state, ch_name, channel_id, thread_ts, persona)
            elif state.phase == "REVIEW" and is_positive_review(visible_text):
                # If review is positive, trigger POSTMORTEM and then close
                trigger_postmortem_and_close(state, ch_name, channel_id, thread_ts)

        # (optional) local provenance log
        try:
            rec = {"t": time.time(), "persona": persona, "chan": ch_name, "thread_ts": thread_ts,
                   "text": visible_text, "supports": supports}
            with open("data/slack_runs_raw.jsonl","a",encoding="utf-8") as f:
                f.write(json.dumps(rec)+"\n")
        except Exception:
            pass

    # Add realistic response latency based on context
    from .progression import get_state
    is_owner = False
    if is_thread:
        state = get_state(channel_id, thread_ts, THREAD_STATES)
        if state and state.owner == persona:
            is_owner = True
    
    # Calculate realistic latency
    realistic_delay = calculate_response_latency(persona, is_owner)
    total_delay = delay_s + realistic_delay
    
    # Crude delay using the queue thread (non-blocking)
    t0 = time.time()
    while time.time() - t0 < total_delay:
        time.sleep(0.2)
    _do()