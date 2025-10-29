# src/slack_io/slack_user_post.py
from typing import Optional
from slack_sdk.errors import SlackApiError

def user_post_message(identity, channel_id: str, text: str, thread_ts: Optional[str] = None):
    """
    Posts a message to Slack AS THE USER represented by `identity`.
    The identity is a PersonaIdentity instance loaded from user_registry.py,
    containing the xoxp user token (not the bot token).

    Args:
        identity: PersonaIdentity object (has .client, .persona, .user_token)
        channel_id: Slack channel ID (e.g., 'C09PL1Q6EG0')
        text: Message content
        thread_ts: (optional) Slack thread timestamp to reply in a thread

    Returns:
        API response (dict) or None if it fails
    """
    args = {"channel": channel_id, "text": text}
    if thread_ts:
        args["thread_ts"] = thread_ts

    try:
        resp = identity.client.chat_postMessage(**args)
        return resp
    except SlackApiError as e:
        error_msg = e.response.get('error', 'unknown')
        # Skip if user is not in channel - not fatal
        if error_msg == 'not_in_channel':
            print(f"[user_post_message] {identity.persona} not in channel {channel_id}, skipping")
            return None
        print(f"[user_post_message] Slack API error for {identity.persona}: {error_msg}")
        return None
    except Exception as e:
        print(f"[user_post_message] Unexpected error posting as {identity.persona}: {e}")
        return None