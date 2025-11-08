# export_history.py
import os
import json
import time
from dotenv import load_dotenv
from src.slack_io.slack_client import app
from src.slack_io.persona_registry import CHANNEL_NAME_TO_ID

# Load .env file (SLACK_BOT_TOKEN)
load_dotenv()

# --- Configuration ---
# Add all channels you want to export
CHANNELS_TO_EXPORT = ["sre-ops", "eng-backend", "product", "deployments"]


# ---------------------

def get_channel_id(channel_name):
    """Helper to get channel ID from the registry."""
    return CHANNEL_NAME_TO_ID.get(channel_name)


def export_channel_history(channel_id):
    """Fetches all messages from a single channel."""
    all_messages = []
    cursor = None

    while True:
        try:
            print(f"Fetching history for {channel_id} (cursor: {cursor})...")
            # Use the app.client from slack_client.py
            response = app.client.conversations_history(
                channel=channel_id,
                limit=200,  # Max limit
                cursor=cursor
            )

            if not response.get("ok"):
                print(f"  Error fetching history: {response.get('error')}")
                break

            messages = response.get("messages", [])
            all_messages.extend(messages)

            # Handle pagination
            if response.get("has_more"):
                cursor = response.get("response_metadata", {}).get("next_cursor")
                time.sleep(1.2)  # Respect rate limits
            else:
                break

        except Exception as e:
            print(f"  An error occurred: {e}")
            break

    # Reverse messages to be in chronological order (oldest first)
    all_messages.reverse()
    return all_messages


def main():
    # Load all channel maps first (in case they aren't populated)
    # This logic is from bolt_app.py
    try:
        print("Loading all channel maps...")
        cursor = None
        while True:
            resp = app.client.conversations_list(limit=200, cursor=cursor, types="public_channel,private_channel")
            for ch in resp.get("channels", []):
                CHANNEL_NAME_TO_ID[ch["name"]] = ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except Exception as e:
        print(f"Failed to load full channel list: {e}")

    print(f"Found {len(CHANNEL_NAME_TO_ID)} channels.")

    # Full export data
    export_data = {
        "channels": {},
        "export_timestamp": time.time()
    }

    for channel_name in CHANNELS_TO_EXPORT:
        channel_id = get_channel_id(channel_name)
        if not channel_id:
            print(f"WARNING: Could not find channel ID for '{channel_name}'. Skipping.")
            continue

        print(f"--- Starting export for #{channel_name} ({channel_id}) ---")
        messages = export_channel_history(channel_id)
        export_data["channels"][channel_name] = {
            "id": channel_id,
            "messages": messages
        }
        print(f"--- Finished export for #{channel_name}. Found {len(messages)} messages. ---")

    # Save to a local JSON file
    output_filename = "slack_export.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Export complete. All data saved to {output_filename}")


if __name__ == "__main__":
    main()