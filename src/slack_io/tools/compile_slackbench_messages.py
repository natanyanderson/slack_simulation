# compile_slackbench_messages.py
"""
Compiler for SlackBench message compilation.
Combines selective channel compilation with SlackBench's flat array format.
"""
import os
import json
from datetime import datetime
from pathlib import Path

# --- CONFIGURE THIS ---
# Path to unzipped Slack export folder
UNZIPPED_EXPORT_PATH = "/Users/jay./Downloads/Formula Electric at Berkeley Slack export Sep 1 2025 - Nov 9 2025"

# List of channel names to compile (use exact folder names)
# Set to None or empty list to compile all channels
CHANNELS_TO_COMPILE = [
    "general",
    "testing",
    "logistics"
]

# Output directory (default: project root)
# None = project root, or specify absolute/relative path
OUTPUT_DIR = "data/Compiled_JSON"
# -------------------------


def load_json_file(filepath):
    """Safely loads a single JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return None


def get_project_root():
    """Get the project root directory (where this script is located, go up 3 levels)."""
    # This script is in src/slack_io/tools/
    # Project root is 3 levels up
    script_dir = Path(__file__).parent
    return script_dir.parent.parent.parent


def get_all_channel_names(export_path):
    """Get all channel names from the export directory structure."""
    export_path_obj = Path(export_path)
    if not export_path_obj.exists():
        return []
    
    channel_names = []
    for item in export_path_obj.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if it looks like a channel directory (has JSON files)
            if any(item.glob("*.json")):
                channel_names.append(item.name)
    
    return sorted(channel_names)


def compile_messages(export_path, channel_names, output_dir):
    """
    Compile messages from Slack export into SlackBench-compatible format.
    
    Args:
        export_path: Path to unzipped Slack export folder
        channel_names: List of channel names to compile, or None/empty for all
        output_dir: Directory to write output file, or None for project root
    
    Returns:
        Path to output file if successful, None otherwise
    """
    print(f"Starting compilation of Slack export from: {export_path}")
    
    # Validate export path
    if not os.path.exists(export_path):
        print(f"ERROR: Export path does not exist: {export_path}")
        return None
    
    # 1. Load channels.json to map names to IDs
    print("Loading channels.json...")
    channels_list = load_json_file(os.path.join(export_path, "channels.json"))
    if not channels_list:
        print("ERROR: channels.json not found in the export path. Cannot proceed.")
        return None
    
    channel_map = {channel["name"]: channel["id"] for channel in channels_list}
    print(f"Found {len(channel_map)} channels in the export.")
    
    # 2. Determine which channels to compile
    if not channel_names:
        # Compile all channels
        print("No channels specified, compiling all channels...")
        channel_names = get_all_channel_names(export_path)
        if not channel_names:
            print("ERROR: No channels found in export directory.")
            return None
        print(f"Found {len(channel_names)} channels to compile.")
    else:
        print(f"Compiling {len(channel_names)} specified channel(s).")
    
    # 3. Collect all messages with channel metadata
    all_messages = []
    channels_processed = 0
    
    for channel_name in channel_names:
        if channel_name not in channel_map:
            print(f"WARNING: Channel '{channel_name}' not found in channels.json. Skipping.")
            continue
        
        channel_id = channel_map[channel_name]
        channel_dir = os.path.join(export_path, channel_name)
        
        if not os.path.isdir(channel_dir):
            print(f"WARNING: Directory '{channel_name}' not found. Skipping.")
            continue
        
        print(f"\n--- Compiling channel: #{channel_name} ---")
        
        channel_messages = []
        
        # 4. Get all daily JSON files and sort them chronologically
        try:
            # Sort files by name (e.g., 2025-01-01.json before 2025-01-02.json)
            # This is CRITICAL for keeping messages in chronological order
            daily_json_files = sorted([f for f in os.listdir(channel_dir) if f.endswith(".json")])
        except FileNotFoundError:
            print(f"  No files found for channel '{channel_name}'.")
            continue
        
        print(f"  Found {len(daily_json_files)} daily message files.")
        
        # 5. Read each daily file and append its messages
        for filename in daily_json_files:
            filepath = os.path.join(channel_dir, filename)
            messages = load_json_file(filepath)
            
            if messages:
                # A daily file is a LIST of messages
                if isinstance(messages, list):
                    channel_messages.extend(messages)
                else:
                    print(f"  WARNING: {filename} is not a list, skipping.")
        
        # 6. Add channel metadata to each message
        for msg in channel_messages:
            # Create a copy to avoid modifying the original
            msg_copy = msg.copy()
            # Add channel metadata
            msg_copy["channel"] = {
                "id": channel_id,
                "name": channel_name
            }
            all_messages.append(msg_copy)
        
        print(f"  Successfully compiled {len(channel_messages)} messages for #{channel_name}.")
        channels_processed += 1
    
    if not all_messages:
        print("\nERROR: No messages were compiled. Check your channel selection and export path.")
        return None
    
    # 7. Sort all messages by timestamp (ascending - oldest first)
    print(f"\nSorting {len(all_messages)} messages chronologically...")
    all_messages.sort(key=lambda m: float(m.get("ts", "0")))
    
    # 8. Generate timestamped output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"compiled_messages_{timestamp}.json"
    
    # 9. Determine output directory
    if output_dir is None:
        output_dir = get_project_root()
    else:
        output_dir = Path(output_dir)
        if not output_dir.is_absolute():
            # Relative to project root
            output_dir = get_project_root() / output_dir
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename
    
    # 10. Write the flat JSON array to file
    print(f"\nWriting compiled messages to: {output_path}")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_messages, f, indent=2, ensure_ascii=False)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        
        print(f"\n✅ Success! Compiled messages written to: {output_path}")
        print(f"   - Channels processed: {channels_processed}")
        print(f"   - Total messages: {len(all_messages)}")
        print(f"   - File size: {file_size_mb:.2f} MB")
        print(f"\nTo use this file, update workspace_config.yaml with:")
        print(f"   compiled_messages_path: \"{output_path}\"")
        
        return str(output_path)
    
    except Exception as e:
        print(f"\nERROR: Failed to write output file: {e}")
        return None


def main():
    """Main entry point."""
    # Get project root for relative paths
    project_root = get_project_root()
    
    # Resolve export path (handle relative paths)
    export_path = Path(UNZIPPED_EXPORT_PATH)
    if not export_path.is_absolute():
        export_path = project_root / export_path
    export_path = str(export_path.resolve())
    
    # Resolve output directory
    output_dir = OUTPUT_DIR
    if output_dir is not None:
        output_dir = Path(output_dir)
        if not output_dir.is_absolute():
            output_dir = project_root / output_dir
        output_dir = str(output_dir.resolve())
    
    # Compile messages
    result = compile_messages(
        export_path=export_path,
        channel_names=CHANNELS_TO_COMPILE if CHANNELS_TO_COMPILE else None,
        output_dir=output_dir
    )
    
    if result:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())

