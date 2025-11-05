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

## Documentation

- `AUTONOMOUS_APPROACH.md` - How the autonomous loop works
- `MESSAGE_IMPROVEMENTS_SUMMARY.md` - Natural language enhancements
- `SPEED_OPTIMIZATIONS.md` - Performance tuning guide
- `BOT_CAPABILITIES.md` - Slack API capabilities

## Requirements

- Python 3.8+
- Slack workspace
- Slack app with Bot/App tokens
- OpenAI API key

## License

This project is part of the SlackBench research project.

