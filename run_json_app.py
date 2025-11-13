#!/usr/bin/env python3
"""
Start the JSON-only Slack app.
Uses exported JSON files instead of Slack API for data queries.
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.slack_io.bolt_app_json import run_socket_mode
from src.slack_io.tools.workspace_config import list_workspaces


def main():
    parser = argparse.ArgumentParser(
        description="Start JSON-only Slack app for querying exported data"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Workspace name from workspace_config.yaml (default: 'default')"
    )
    parser.add_argument(
        "--list-workspaces",
        action="store_true",
        help="List available workspaces and exit"
    )
    
    args = parser.parse_args()
    
    if args.list_workspaces:
        workspaces = list_workspaces()
        if workspaces:
            print("Available workspaces:")
            for ws in workspaces:
                print(f"  - {ws}")
        else:
            print("No workspaces configured. Edit workspace_config.yaml to add workspaces.")
        return
    
    try:
        run_socket_mode(args.workspace)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

