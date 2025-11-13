"""
Data loader for exported Slack JSON files.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache


class SlackJSONDataLoader:
    """Loads and caches exported Slack JSON data."""
    
    def __init__(self, export_path: str, compiled_messages_path: Optional[str] = None):
        self.export_path = Path(export_path)
        self.compiled_messages_path = compiled_messages_path
        self._channels_cache = None
        self._users_cache = None
        self._messages_cache = None
        self._channel_messages_index = {}
    
    @property
    def channels(self) -> List[Dict[str, Any]]:
        """Load channels.json"""
        if self._channels_cache is None:
            channels_file = self.export_path / "channels.json"
            if channels_file.exists():
                try:
                    with open(channels_file, 'r', encoding='utf-8') as f:
                        self._channels_cache = json.load(f)
                except Exception as e:
                    print(f"Error loading channels.json: {e}")
                    self._channels_cache = []
            else:
                self._channels_cache = []
        return self._channels_cache
    
    @property
    def users(self) -> List[Dict[str, Any]]:
        """Load users.json"""
        if self._users_cache is None:
            users_file = self.export_path / "users.json"
            if users_file.exists():
                try:
                    with open(users_file, 'r', encoding='utf-8') as f:
                        self._users_cache = json.load(f)
                except Exception as e:
                    print(f"Error loading users.json: {e}")
                    self._users_cache = []
            else:
                self._users_cache = []
        return self._users_cache
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel by ID."""
        for channel in self.channels:
            if channel.get("id") == channel_id:
                return channel
        return None
    
    def get_channel_by_name(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Get channel by name (without # prefix)."""
        for channel in self.channels:
            if channel.get("name") == channel_name:
                return channel
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        for user in self.users:
            if user.get("id") == user_id:
                return user
        return None
    
    def load_channel_messages(self, channel_name: str) -> List[Dict[str, Any]]:
        """Load all messages for a channel from date-based JSON files."""
        # Check cache first
        if channel_name in self._channel_messages_index:
            return self._channel_messages_index[channel_name]
        
        channel_dir = self.export_path / channel_name
        if not channel_dir.exists() or not channel_dir.is_dir():
            self._channel_messages_index[channel_name] = []
            return []
        
        all_messages = []
        # Load all date-based JSON files in the channel directory
        for json_file in sorted(channel_dir.glob("*.json")):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
                    if isinstance(messages, list):
                        all_messages.extend(messages)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")
        
        # Sort by timestamp (ascending - oldest first)
        all_messages.sort(key=lambda m: float(m.get("ts", "0")))
        
        # Cache the result
        self._channel_messages_index[channel_name] = all_messages
        return all_messages
    
    def load_compiled_messages(self) -> List[Dict[str, Any]]:
        """Load compiled_messages.json if available."""
        if self._messages_cache is not None:
            return self._messages_cache
        
        if self.compiled_messages_path and os.path.exists(self.compiled_messages_path):
            try:
                with open(self.compiled_messages_path, 'r', encoding='utf-8') as f:
                    self._messages_cache = json.load(f)
                    return self._messages_cache
            except Exception as e:
                print(f"Error loading compiled_messages.json from {self.compiled_messages_path}: {e}")
        
        # Fallback: try in export path
        compiled_path = self.export_path / "compiled_messages.json"
        if compiled_path.exists():
            try:
                with open(compiled_path, 'r', encoding='utf-8') as f:
                    self._messages_cache = json.load(f)
                    return self._messages_cache
            except Exception as e:
                print(f"Error loading compiled_messages.json: {e}")
        
        return []
    
    def get_messages_by_channel_id(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a channel ID from compiled_messages.json."""
        # First try to find channel name
        channel = self.get_channel_by_id(channel_id)
        if channel:
            channel_name = channel.get("name")
            if channel_name:
                return self.load_channel_messages(channel_name)
        
        # Fallback: search compiled_messages.json
        messages = self.load_compiled_messages()
        # Note: compiled_messages.json may not have channel_id directly
        # This would need to be adapted based on actual structure
        return [m for m in messages if m.get("channel") == channel_id or m.get("channel_id") == channel_id]
    
    def get_all_channel_names(self) -> List[str]:
        """Get list of all channel names from directory structure."""
        if not self.export_path.exists():
            return []
        
        channel_names = []
        for item in self.export_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it looks like a channel directory (has JSON files)
                if any(item.glob("*.json")):
                    channel_names.append(item.name)
        
        return sorted(channel_names)


# Global loader instance (will be initialized by implementations)
_loader: Optional[SlackJSONDataLoader] = None


def get_loader() -> SlackJSONDataLoader:
    """Get or create the global data loader."""
    global _loader
    if _loader is None:
        from ..config import TOOL_CONFIG
        export_path = TOOL_CONFIG.get("data_source", {}).get("json", {}).get("export_path", "")
        compiled_path = TOOL_CONFIG.get("data_source", {}).get("json", {}).get("compiled_messages_path")
        _loader = SlackJSONDataLoader(export_path, compiled_path)
    return _loader

