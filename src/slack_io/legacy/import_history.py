# import_history.py
import json
import time
from src.slack_io.autonomous.user_registry import load_user_personas
from src.slack_io.autonomous.persona_registry import CHANNEL_NAME_TO_ID, PERSONAS
from src.slack_io.autonomous.slack_user_post import user_post_message

# --- Configuration ---
EXPORT_FILE_TO_LOAD = "slack_export.json"
REPLAY_DELAY_SECONDS = 2.0  # Time to wait between posting messages
# ---------------------

# Load all persona identities (with their user tokens)
#
print("Loading user persona identities...")
USER_PERSONAS_IDENTITIES = load_user_personas()

# Load the persona map to link User IDs to persona names
#
print("Loading persona map...")
with open("secrets/personas.map.json", "r") as f:
    persona_map_data = json.load(f)

# Create a reverse map from User ID -> Persona Name
# e.g., "U09P91LJDA6" -> "Mike_BE"
USER_ID_TO_PERSONA_NAME = {
    details["user_id"]: persona_name
    for persona_name, details in persona_map_data.items()
}
print(f"Mapped {len(USER_ID_TO_PERSONA_NAME)} User IDs to persona names.")


def get_persona_identity(user_id):
    """Get the correct PersonaIdentity object for a given User ID."""
    persona_name = USER_ID_TO_PERSONA_NAME.get(user_id)
    if persona_name:
        return USER_PERSONAS_IDENTITIES.get(persona_name)
    return None


def replay_conversations(export_data):
    """Replays all conversations from the export file."""

    # Track original thread_ts to new_thread_ts
    thread_map = {}  # Key: old_ts, Value: new_ts

    for channel_name, channel_data in export_data["channels"].items():
        channel_id = channel_data.get("id")
        messages = channel_data.get("messages", [])

        if not channel_id or not messages:
            continue

        print(f"\n--- Replaying {len(messages)} messages in #{channel_name} ---")

        for msg in messages:
            # We only care about standard user messages
            if msg.get("subtype") or not msg.get("user"):
                continue

            # Find which persona should post this
            persona_identity = get_persona_identity(msg.get("user"))

            if not persona_identity:
                print(f"  SKIPPING message from unknown user {msg.get('user')}")
                continue

            text = msg.get("text", "")
            original_ts = msg.get("ts")
            original_thread_ts = msg.get("thread_ts")

            new_thread_ts = None
            if original_thread_ts:
                # This is a reply. Check if we've already mapped its parent.
                new_thread_ts = thread_map.get(original_thread_ts)
                if not new_thread_ts:
                    print(f"  SKIPPING reply (parent {original_thread_ts} not yet posted).")
                    continue

            print(f"  Posting as {persona_identity.persona}: {text[:50]}...")

            # Post the message as that user
            response = user_post_message(
                identity=persona_identity,
                channel_id=channel_id,
                text=text,
                thread_ts=new_thread_ts
            )

            if response and response.get("ok"):
                new_ts = response.get("ts")
                # If this was a parent message, map its original_ts to the new_ts
                if not new_thread_ts:
                    thread_map[original_ts] = new_ts

            time.sleep(REPLAY_DELAY_SECONDS)


def main():
    try:
        with open(EXPORT_FILE_TO_LOAD, "r", encoding="utf-8") as f:
            export_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Export file not found: {EXPORT_FILE_TO_LOAD}")
        print("Please run export_history.py first.")
        return

    replay_conversations(export_data)
    print("\n✅ Replay complete.")


if __name__ == "__main__":
    main()