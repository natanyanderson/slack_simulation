import time
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from slack_sdk.errors import SlackApiError
import os, logging
from dotenv import load_dotenv
from typing import Optional

log = logging.getLogger(__name__)

# Lazy initialization to avoid loading .env at import time
_app_instance: Optional[App] = None

def get_app() -> App:
    """Get or create the Slack app instance (lazy initialization)."""
    global _app_instance
    if _app_instance is None:
        # Load environment variables from .env file
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
        _app_instance = App(token=os.getenv("SLACK_BOT_TOKEN"))
    return _app_instance

# For backward compatibility, expose app as module-level variable
# This allows `from .slack_client import app` to work
class _AppProxy:
    """Proxy to lazy-loaded app instance."""
    @property
    def client(self):
        return get_app().client
    
    def __getattr__(self, name):
        return getattr(get_app(), name)

app = _AppProxy()

def post_message(channel: str, text: str, username: str, icon_emoji: str=None, thread_ts: str=None):
    args = {
        "channel": channel,
        "text": text,
        "username": username,   
    }

    if icon_emoji:
        args["icon_emoji"] = icon_emoji
    if thread_ts:
        args["threads_ts"] = thread_ts
    while True:
        try:
            return get_app().client.chat_postMessage(**args)
        except SlackApiError as e:
            if e.response.status_code == 429:
                wait = int(e.response.headers.get("Retry-After", "1"))
                time.sleep(wait + 0.1)
                continue
            raise

def fetch_history(channel: str, oldest: str=None, latest: str=None, limit: int=200):
    return get_app().client.conversations.history(channel=channel, oldest=oldest, latest=latest, limit=limit)

def fetch_thread(channel: str, parent_ts: str, limit: int=200):
    return get_app().client.conversations.replies(channel=channel, ts=parent_ts, limit=limit)
    