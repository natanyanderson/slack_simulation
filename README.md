# SlackBench Real-Time Simulation

A real-time Slack workspace simulation system that uses AI agents to autonomously interact in a real Slack workspace, creating natural conversations between different engineering personas.

## Features

- ✅ **Autonomous Agent Conversations**: AI-powered personas interact naturally in Slack
- ✅ **Real Slack Integration**: Uses Slack's Bot API for authentic messaging
- ✅ **Multiple Personas**: 9 different engineering roles (BE, FE, QA, SRE, PM, TPM, Staff, UX, DS)
- ✅ **Smart Context Gathering**: Agents read and respond to actual channel history
- ✅ **Thread Support**: Full support for threaded conversations
- ✅ **Rate Limit Safe**: Respects Slack's API rate limits
- ✅ **Natural Language**: Enhanced prompts for more human-like responses

## Project Structure

```
slackbench_real_sim/
├── src/slack_io/
│   ├── agent_engine.py      # LLM-powered message generation
│   ├── autonomous_loop.py   # Background conversation generation
│   ├── bolt_app.py          # Slack Bolt app and event handling
│   ├── conductor.py         # Orchestrates agent interactions
│   ├── persona_registry.py  # Persona definitions and channel policies
│   ├── queue.py             # Rate-limited message queue
│   └── slack_client.py      # Slack API client
├── test_connection.py       # Test/startup script
└── run_app.sh              # Startup script

```

## Setup

1. **Install Dependencies:**
```bash
pip install slack-bolt slack-sdk openai python-dotenv
```

2. **Environment Variables:**
Create a `.env` file in the project root:
```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
OPENAI_API_KEY=sk-your-openai-key
MODEL_NAME=gpt-4o-mini
```

3. **Configure Slack App:**
- Create a new Slack app at https://api.slack.com/apps
- Enable Socket Mode
- Add OAuth scopes: `chat:write`, `channels:read`, `groups:read`
- Install to your workspace
- Copy the tokens to `.env`

4. **Run:**
```bash
python test_connection.py
```

## Configuration

### Speed Controls (in `conductor.py` and `autonomous_loop.py`):
- `MIN_DELAY_S, MAX_DELAY_S`: Reply timing (default: 1-3s)
- `PERSONA_COOLDOWN_S`: Time between same persona (default: 12s)
- `TURN_INTERVAL_S`: Autonomous posting interval (default: 25s)

### Persona Definitions (in `persona_registry.py`):
Each persona has:
- Username and icon
- Role and expertise areas
- Communication style (tone_ticks)
- Example messages (seed_snippets)
- Knowledge domains

## How It Works

1. **Autonomous Loop**: Posts a message every 25 seconds to random channels
2. **Event Handler**: Responds to real Slack messages
3. **Context Fetcher**: Reads channel/thread history for context
4. **LLM Generator**: Uses OpenAI to generate role-appropriate responses
5. **Queue System**: Manages posting rate to respect Slack limits

## Slack API Method Scraper

The `scraper/` folder contains a comprehensive scraper for extracting Slack API method documentation.

### Scraper Features

- Extracts method name, description, parameters, and response schemas
- Handles nested objects and arrays in response structures
- Extracts error definitions
- Supports batch processing of all methods
- Outputs in standardized JSON format

### Usage

#### Scrape a Single Method

```bash
# From the scraper directory
cd scraper
python slack_method_scraper.py --method admin.analytics.getFile

# Or from the root directory
python scraper/slack_method_scraper.py --method admin.analytics.getFile
```

#### Scrape All Methods

```bash
# From the scraper directory
cd scraper
python slack_method_scraper.py --all --input ../slack_api_all_methods.json

# Or from the root directory
python scraper/slack_method_scraper.py --all
```

#### Advanced Options

```bash
# Custom rate limiting (default: 1.0 seconds)
python scraper/slack_method_scraper.py --all --rate-limit 2.0

# Skip methods that already exist in output file
python scraper/slack_method_scraper.py --all --skip-existing

# Resume from a specific method if scraping was interrupted
python scraper/slack_method_scraper.py --all --resume-from admin.apps.approve

# Custom input/output files
python scraper/slack_method_scraper.py --all --input ../slack_api_all_methods.json --output my_output.json
```

### Output Format

The scraper outputs JSON files with the following structure:

```json
{
  "name": "method.name",
  "description": "Method description",
  "parameters": {
    "type": "dict",
    "properties": {
      "param_name": {
        "type": "string",
        "description": "Parameter description"
      }
    },
    "required": ["param_name"]
  },
  "response": {
    "type": "dict",
    "properties": {
      "field_name": {
        "type": "string",
        "description": "Field description"
      }
    }
  },
  "errors": {
    "type": "dict",
    "properties": {
      "error_name": {
        "type": "string",
        "description": "Error description"
      }
    }
  }
}
```

### Scraper Files

- `scraper/slack_method_scraper.py` - Main scraper script
- `scraper/slack_api_all_methods_scraped.json` - Complete scraped results (all methods)
- `slack_api_all_methods.json` - Input file with list of all Slack API methods

## Function Calling Architecture

The read-only assistant uses OpenAI's function calling feature to interact with Slack data. The system supports two data sources: **API mode** (live Slack API) and **JSON mode** (exported Slack data).

### How Function Calling Works

1. **User Query**: User sends a message via DM, @mention, or `/slackbench` command
2. **GPT-4o Processing**: The assistant receives the query and decides which tools to call
3. **Tool Execution**: Tools are executed via the router, which selects the appropriate implementation
4. **Response Generation**: GPT-4o uses tool results to generate a natural language response

### Architecture Overview

```
User Query
    ↓
read_only_assistant.py (GPT-4o)
    ↓
Tool Definitions (OpenAI function schemas)
    ↓
read_only_router.py (Router)
    ↓
┌─────────────────┬─────────────────┐
│   API Mode      │   JSON Mode     │
│                 │                 │
│ implementations/│ implementations/│
│  conversations  │  json/          │
│  users          │   conversations │
│  search         │   users         │
│                 │   search        │
│                 │                 │
│ → Slack API     │ → JSON Files    │
└─────────────────┴─────────────────┘
```

### Data Source Selection

The system automatically selects between API and JSON implementations based on the `SLACK_DATA_SOURCE` environment variable:

- **API Mode** (`SLACK_DATA_SOURCE=api`): Uses live Slack API calls
- **JSON Mode** (`SLACK_DATA_SOURCE=json`): Uses exported JSON files

The selection happens dynamically via `tool_definitions.py` → `_get_implementation_path()`, which reads from `config.py` → `get_data_source_type()`.

### API Mode Implementation

**How it works:**
1. Router receives tool call (e.g., `search_messages`)
2. Router loads implementation from `implementations/search.py`
3. Implementation makes HTTP request to Slack API
4. Response is formatted and returned to GPT-4o

**Example Flow:**
```
search_messages("SN4")
    ↓
implementations/search.py
    ↓
bolt_app.client.search_messages(query="SN4")
    ↓
Slack API (live workspace)
    ↓
Formatted response → GPT-4o
```

**Available Tools (API Mode):**
- `list_channels` - Calls `conversations.list`
- `get_channel_history` - Calls `conversations.history`
- `get_channel_members` - Calls `conversations.members`
- `get_thread_replies` - Calls `conversations.replies`
- `get_user_info` - Calls `users.info`
- `list_users` - Calls `users.list`
- `search_messages` - Calls `search.messages` (⚠️ requires user token)
- `get_team_info` - Calls `team.info`

**Limitations:**
- `search.messages` requires a user token (xoxp-), not a bot token (xoxb-)
- Rate limits apply (Slack API rate limits)
- Requires active Slack workspace connection

### JSON Mode Implementation

**How it works:**
1. Router receives tool call (e.g., `search_messages`)
2. Router loads implementation from `implementations/json/search.py`
3. Implementation loads data from JSON files (compiled or per-channel)
4. In-memory search/filtering is performed
5. Response is formatted and returned to GPT-4o

**Example Flow:**
```
search_messages("SN4")
    ↓
implementations/json/search.py
    ↓
json_data_loader.py → load_compiled_messages()
    ↓
compiled_messages.json (or channel directories)
    ↓
In-memory text search
    ↓
Formatted response → GPT-4o
```

**Data Loading Strategy:**
1. **Primary**: Uses `compiled_messages.json` if available (fast, single file)
2. **Fallback**: Loads from per-channel directories (`channel_name/YYYY-MM-DD.json`)

**Available Tools (JSON Mode):**
- `list_channels` - Reads from `channels.json`
- `get_channel_history` - Reads from `channel_name/*.json` files
- `get_channel_members` - Extracts from channel messages
- `get_thread_replies` - Extracts from message threads
- `get_user_info` - Reads from `users.json`
- `list_users` - Reads from `users.json`
- `search_messages` - Searches compiled messages or all channel files
- `get_team_info` - Extracts from workspace metadata

**Advantages:**
- ✅ No API rate limits
- ✅ Works offline (no Slack connection needed)
- ✅ `search_messages` always works (no token restrictions)
- ✅ Faster for large searches (in-memory)
- ✅ Can work with historical data

### Message Compiler

The `compile_slackbench_messages.py` script allows you to compile messages from a Slack export into SlackBench's expected format with selective channel compilation.

**Features:**
- **Selective Channel Compilation**: Compile only specific channels (useful for testing/development)
- **SlackBench-Compatible Format**: Outputs flat JSON array format expected by SlackBench
- **Channel Metadata**: Automatically adds channel ID and name to each message
- **Timestamped Output**: Generates files with timestamps (e.g., `compiled_messages_20251112_143022.json`)

**Usage:**

1. **Configure the script** (`src/slack_io/tools/compile_slackbench_messages.py`):
   ```python
   # --- CONFIGURE THIS ---
   UNZIPPED_EXPORT_PATH = "/path/to/slack/export"
   CHANNELS_TO_COMPILE = ["general", "testing", "logistics"]
   OUTPUT_DIR = None  # None = project root
   ```

2. **Run the compiler**:
   ```bash
   python src/slack_io/tools/compile_slackbench_messages.py
   ```

3. **Update workspace config** to use the new file:
   ```yaml
   workspaces:
     default:
       compiled_messages_path: "/path/to/compiled_messages_20251112_143022.json"
   ```

**Compiling All Channels:**
Set `CHANNELS_TO_COMPILE = []` or `CHANNELS_TO_COMPILE = None` to compile all channels found in the export.

**Output Format:**
- Flat JSON array: `[{message1}, {message2}, ...]`
- Each message includes: `{"channel": {"id": "...", "name": "..."}}`
- Messages sorted chronologically by timestamp

**Configuration:**
Set paths in `workspace_config.yaml` or environment variables:
```yaml
workspaces:
  default:
    export_path: "/path/to/slack/export"
    compiled_messages_path: "/path/to/compiled_messages.json"
```

### Router Mechanism

The `ReadOnlyRouter` class (`read_only_router.py`) handles:

1. **Tool Validation**: Checks if tool exists and is in allowlist
2. **Parameter Validation**: Validates tool parameters against schemas
3. **Idempotency**: Prevents duplicate tool calls (5-minute TTL)
4. **Implementation Selection**: Dynamically loads API or JSON implementation
5. **Error Handling**: Formats errors consistently
6. **Response Truncation**: Limits response size to prevent token overflow
7. **Logging**: Logs all tool calls for debugging

**Implementation Selection Logic:**
```python
# In tool_definitions.py
def _get_implementation_path():
    data_source = get_data_source_type()  # Reads SLACK_DATA_SOURCE env var
    
    if data_source == "json":
        return {
            "search_messages": ("implementations.json.search", "search_messages"),
            # ... other JSON implementations
        }
    else:
        return {
            "search_messages": ("implementations.search", "search_messages"),
            # ... other API implementations
        }
```

### Tool Execution Flow

```
1. User: "Can you find messages about SN4?"
   ↓
2. GPT-4o: Decides to call search_messages("SN4")
   ↓
3. Router: Validates tool, checks idempotency
   ↓
4. Router: Gets implementation path based on SLACK_DATA_SOURCE
   ↓
5. Implementation: Executes (API call or JSON search)
   ↓
6. Router: Formats response, applies truncation
   ↓
7. GPT-4o: Receives tool result, generates natural language response
   ↓
8. User: Receives formatted answer
```

### Running in Different Modes

**API Mode:**
```bash
# Set in .env or environment
export SLACK_DATA_SOURCE=api
python test_connection.py
```

**JSON Mode:**
```bash
# Set in .env or use dedicated script
export SLACK_DATA_SOURCE=json
python run_json_app.py
```

**JSON Mode with Workspace Config:**
```bash
python run_json_app.py --workspace default
python run_json_app.py --list-workspaces  # See available workspaces
```

### Tool Definitions

All tools are defined in `src/slack_io/tools/tool_definitions.py` using OpenAI's function calling schema format. Each tool has:
- `name`: Tool identifier
- `description`: Natural language description for GPT-4o
- `parameters`: JSON schema defining inputs

The same tool definitions work for both API and JSON modes - only the implementation changes.

## Documentation

- `AUTONOMOUS_APPROACH.md` - How the autonomous loop works
- `MESSAGE_IMPROVEMENTS_SUMMARY.md` - Natural language enhancements
- `SPEED_OPTIMIZATIONS.md` - Performance tuning guide
- `BOT_CAPABILITIES.md` - Slack API capabilities
- `READ_ONLY_TOOLS_INTEGRATION.md` - Read-only tools integration details

## Requirements

- Python 3.8+
- Slack workspace
- Slack app with Bot/App tokens
- OpenAI API key

## License

This project is part of the SlackBench research project.

