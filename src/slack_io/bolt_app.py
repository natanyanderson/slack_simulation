import os, logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from .conductor import maybe_handle_event
from .persona_registry import CHANNEL_ID_TO_NAME, CHANNEL_NAME_TO_ID
from .seed_scheduler import start_seeders
from .autonomous_loop import start_autonomous_loop, add_real_message_to_history
from .artifact_server import start_server as start_artifact_server
from .artifacts import load_artifacts

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Initialize a single-workspace Bolt App here (no OAuth / MultiTeamsAuthorization)
app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),                 # xoxb-...
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),   # required even in Socket Mode
    process_before_response=True,
)

# Preflight auth check to surface bad tokens early
try:
    whoami = app.client.auth_test()
    logging.info(f"[startup] Bot connected as user_id={whoami.get('user_id')} team={whoami.get('team')} ({whoami.get('team_id')})")
except Exception as e:
    logging.error(f"[startup] auth_test failed. Check SLACK_BOT_TOKEN / installation. Error: {e}")

# On app start, build channel maps (optional but recommended)
@app.event("app_home_opened")
def build_maps(event, logger):
    try:
        cursor = None
        while True:
            resp = app.client.conversations_list(limit=200, cursor=cursor, types="public_channel,private_channel")
            for ch in resp.get("channels", []):
                CHANNEL_ID_TO_NAME[ch["id"]] = ch["name"]
                CHANNEL_NAME_TO_ID[ch["name"]] = ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        logger.info(f"Loaded {len(CHANNEL_ID_TO_NAME)} channels.")
    except Exception as e:
        logger.error(f"Failed to load channels: {e}")

@app.event("message")
def handle_message_events(body, event, logger, say):
    # let the conductor decide if anyone replies
    # Don't early-return on bot_message; the conductor will guard loops.
    ch = event.get("channel")
    ts = event.get("ts")
    subtype = event.get("subtype")
    username = event.get("username", "unknown")
    text_preview = event.get("text", "")[:50]
    logger.info(f"[BOLT] Received message - Channel: {ch}, TS: {ts}, Subtype: {subtype}, User: {username}, Text: {text_preview}...")
    
    # Add to autonomous history if it's a real message
    add_real_message_to_history(event)
    
    # Pass full event to conductor
    try:
        maybe_handle_event(event)
    except Exception as e:
        logger.error(f"[BOLT] Error in conductor: {e}", exc_info=True)

# Also listen for bot messages explicitly
@app.event({"type": "message", "subtype": "bot_message"})
def handle_bot_messages(body, event, logger, say):
    # This will catch bot messages that might be skipped by the regular message handler
    logger.info(f"[BOLT] Received bot message - Channel: {event.get('channel')}, User: {event.get('username')}")
    try:
        maybe_handle_event(event)
    except Exception as e:
        logger.error(f"[BOLT] Error in conductor (bot): {e}", exc_info=True)

def load_channel_maps(app, logger):
    """Build initial channel ID ↔ name mappings at startup"""
    from .persona_registry import CHANNEL_ID_TO_NAME, CHANNEL_NAME_TO_ID
    try:
        cursor = None
        while True:
            resp = app.client.conversations_list(
                limit=200,
                cursor=cursor,
                types="public_channel,private_channel"
            )
            for ch in resp.get("channels", []):
                CHANNEL_ID_TO_NAME[ch["id"]] = ch["name"]
                CHANNEL_NAME_TO_ID[ch["name"]] = ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        logger.info(f"[startup] Loaded {len(CHANNEL_ID_TO_NAME)} channels.")
    except Exception as e:
        logger.error(f"[startup] Failed to load channels: {e}")

def run_socket_mode():
    """Run the app in Socket Mode"""
    app_token = os.getenv("SLACK_APP_TOKEN")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    
    if not app_token:
        raise ValueError("SLACK_APP_TOKEN not found in environment variables")
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
    
    logging.info("Starting Slack app in Socket Mode...")
    logging.info(f"App token: {app_token[:10]}...")
    logging.info(f"Bot token: {bot_token[:10]}...")
    
    # Load channel maps at startup
    load_channel_maps(app, logging.getLogger(__name__))

    # Load artifacts from disk
    load_artifacts()
    logging.info("Loaded artifacts from disk")
    
    # Start artifact server
    start_artifact_server()
    
    # Start autonomous simulation loop (like slackbench_sim)
    start_autonomous_loop()
    
    # Start scheduled events (standups, status summaries)
    from .scheduled_events import start_scheduled_events
    start_scheduled_events()
    
    # Start seeders (optional, less needed with autonomous loop)
    # start_seeders(
    #     standup_every_min=45,      # try 45 for dev
    #     announcements_every_min=75,# dev cadence
    #     noise_every_s=20,
    #     noise_prob=0.03
    # )
    
    handler = SocketModeHandler(app, app_token)
    handler.start()

if __name__ == "__main__":
    run_socket_mode()
