"""
Data loader for exported Slack JSON files.
Uses streaming JSON parsing to avoid loading large files into memory.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterator
from functools import lru_cache

try:
    import ijson
    IJSON_AVAILABLE = True
except ImportError:
    IJSON_AVAILABLE = False
    print("Warning: ijson not available. Falling back to regular JSON loading. Install with: pip install ijson")


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
    
    def stream_compiled_messages(self) -> Iterator[Dict[str, Any]]:
        """
        Stream compiled_messages.json using ijson to avoid loading entire file into memory.
        Returns a generator that yields messages one at a time.
        """
        compiled_path = None
        
        # Determine which file to use
        if self.compiled_messages_path and os.path.exists(self.compiled_messages_path):
            compiled_path = self.compiled_messages_path
        else:
            # Fallback: try in export path
            fallback_path = self.export_path / "compiled_messages.json"
            if fallback_path.exists():
                compiled_path = str(fallback_path)
        
        if not compiled_path:
            return
        
        if IJSON_AVAILABLE:
            try:
                with open(compiled_path, 'rb') as f:
                    # Stream parse the JSON array
                    # Assuming compiled_messages.json is a JSON array: [...]
                    parser = ijson.items(f, 'item')
                    for message in parser:
                        yield message
            except Exception as e:
                print(f"Error streaming compiled_messages.json from {compiled_path}: {e}")
        else:
            # Fallback: try to load in chunks (not ideal but better than loading everything)
            print("Warning: ijson not available, attempting to load file in chunks (may still use significant memory)")
            try:
                with open(compiled_path, 'r', encoding='utf-8') as f:
                    # Try to parse as streaming JSON array
                    # This is a workaround - not truly streaming but better error handling
                    data = json.load(f)
                    if isinstance(data, list):
                        for message in data:
                            yield message
            except MemoryError:
                print(f"Error: File too large to load. Please install ijson: pip install ijson")
                raise
            except Exception as e:
                print(f"Error loading compiled_messages.json: {e}")
    
    def load_compiled_messages(self) -> List[Dict[str, Any]]:
        """
        Load compiled_messages.json if available.
        WARNING: This loads the entire file into memory. Use stream_compiled_messages() for large files.
        For backward compatibility, this method is kept but should be avoided for large files.
        """
        if self._messages_cache is not None:
            return self._messages_cache
        
        # For small files or when ijson is not available, use the old method
        # But warn if the file is large
        compiled_path = None
        if self.compiled_messages_path and os.path.exists(self.compiled_messages_path):
            compiled_path = self.compiled_messages_path
        else:
            fallback_path = self.export_path / "compiled_messages.json"
            if fallback_path.exists():
                compiled_path = str(fallback_path)
        
        if not compiled_path:
            self._messages_cache = []
            return []
        
        # Check file size - warn if > 100MB
        file_size = os.path.getsize(compiled_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            print(f"Warning: compiled_messages.json is {file_size / (1024*1024):.1f}MB. "
                  f"Consider using stream_compiled_messages() to avoid memory issues.")
        
        if IJSON_AVAILABLE and file_size > 50 * 1024 * 1024:  # 50MB
            # For large files, use streaming and convert to list (still uses memory but safer)
            print("Using streaming parser for large file...")
            try:
                self._messages_cache = list(self.stream_compiled_messages())
                return self._messages_cache
            except Exception as e:
                print(f"Error streaming compiled_messages.json: {e}")
                self._messages_cache = []
                return []
        
        # For smaller files, use regular JSON loading
        try:
            with open(compiled_path, 'r', encoding='utf-8') as f:
                self._messages_cache = json.load(f)
                return self._messages_cache
        except MemoryError:
            print(f"Error: File too large to load into memory. Please install ijson: pip install ijson")
            print("Or use stream_compiled_messages() method instead.")
            self._messages_cache = []
            return []
        except Exception as e:
            print(f"Error loading compiled_messages.json from {compiled_path}: {e}")
            self._messages_cache = []
            return []
    
    def get_messages_by_channel_id(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a channel ID from compiled_messages.json using streaming."""
        # First try to find channel name
        channel = self.get_channel_by_id(channel_id)
        if channel:
            channel_name = channel.get("name")
            if channel_name:
                return self.load_channel_messages(channel_name)
        
        # Fallback: search compiled_messages.json using streaming
        # Use streaming to avoid loading entire file
        messages = []
        try:
            for msg in self.stream_compiled_messages():
                # Check if message belongs to this channel
                if msg.get("channel") == channel_id or msg.get("channel_id") == channel_id:
                    messages.append(msg)
        except Exception as e:
            print(f"Error streaming messages for channel {channel_id}: {e}")
            # Fallback to non-streaming method (may cause memory issues)
            try:
                all_messages = self.load_compiled_messages()
                messages = [m for m in all_messages if m.get("channel") == channel_id or m.get("channel_id") == channel_id]
            except Exception as e2:
                print(f"Error loading messages: {e2}")
        
        return messages
    
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

