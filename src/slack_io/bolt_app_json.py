"""
JSON-only Slack Bolt app.
Uses exported JSON files instead of Slack API for data queries.
"""
# CRITICAL: Set environment variable FIRST, before any imports that might read config
import os
os.environ["SLACK_DATA_SOURCE"] = "json"

import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from .artifact_server import start_server as start_artifact_server
from .artifacts import load_artifacts
from .event_handlers import register_event_handlers

# Load environment variables from .env file (same tokens as API app)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize Slack Bolt App
app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),                 # xoxb-...
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),   # required even in Socket Mode
    process_before_response=True,
)

# Preflight auth check to surface bad tokens early
try:
    whoami = app.client.auth_test()
    bot_user_id = whoami.get('user_id')
    logging.info(f"[startup] Bot connected as user_id={bot_user_id} team={whoami.get('team')} ({whoami.get('team_id')})")
except Exception as e:
    logging.error(f"[startup] auth_test failed. Check SLACK_BOT_TOKEN / installation. Error: {e}")
    bot_user_id = None

# Store bot user ID for mention detection
BOT_USER_ID = bot_user_id

# Log JSON data source configuration
from .tools.config import TOOL_CONFIG, get_data_source_type
data_source = get_data_source_type()
logging.info(f"[startup] Data source mode: {data_source}")
if data_source == "json":
    export_path = TOOL_CONFIG.get("data_source", {}).get("json", {}).get("export_path", "")
    compiled_path = TOOL_CONFIG.get("data_source", {}).get("json", {}).get("compiled_messages_path", "")
    logging.info(f"[startup] JSON export path: {export_path}")
    logging.info(f"[startup] Compiled messages path: {compiled_path}")
    
    # Verify paths exist
    if export_path and not os.path.exists(export_path):
        logging.warning(f"[startup] Warning: Export path does not exist: {export_path}")
    if compiled_path and not os.path.exists(compiled_path):
        logging.warning(f"[startup] Warning: Compiled messages path does not exist: {compiled_path}")
else:
    logging.warning(f"[startup] Warning: Expected JSON mode but config shows: {data_source}")

# Register event handlers (must be after app initialization)
register_event_handlers(app, bot_user_id)

# Load artifacts from disk (optional)
load_artifacts()
logging.info("Loaded artifacts from disk")

# Start artifact server (optional)
start_artifact_server()

logging.info("JSON-only app initialized - read-only assistant active")


def run_socket_mode(workspace_name: str = None):
    """
    Run the JSON app in Socket Mode.
    
    Args:
        workspace_name: Optional workspace name to use from config
    """
    app_token = os.getenv("SLACK_APP_TOKEN")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    
    if not app_token:
        raise ValueError("SLACK_APP_TOKEN not found in environment variables")
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
    
    # Set workspace name if provided
    if workspace_name:
        os.environ["SLACK_WORKSPACE"] = workspace_name
        logging.info(f"[startup] Using workspace: {workspace_name}")
    
    logging.info("Starting JSON-only Slack app in Socket Mode...")
    logging.info(f"App token: {app_token[:10]}...")
    logging.info(f"Bot token: {bot_token[:10]}...")
    
    # Log workspace config
    from .tools.workspace_config import get_workspace_paths, list_workspaces
    workspace_paths = get_workspace_paths(workspace_name)
    if workspace_paths:
        logging.info(f"[startup] Workspace export path: {workspace_paths.get('export_path', 'N/A')}")
        logging.info(f"[startup] Workspace compiled messages: {workspace_paths.get('compiled_messages_path', 'N/A')}")
    else:
        logging.warning("[startup] No workspace config found, using environment variables")
        available_workspaces = list_workspaces()
        if available_workspaces:
            logging.info(f"[startup] Available workspaces: {', '.join(available_workspaces)}")
    
    handler = SocketModeHandler(app, app_token)
    handler.start()


if __name__ == "__main__":
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else None
    run_socket_mode(workspace)

