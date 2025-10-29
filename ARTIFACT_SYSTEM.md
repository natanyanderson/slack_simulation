# Artifact Persistence and Serving System

## Overview

The artifact system generates, persists, and serves realistic synthetic artifacts (PRs, logs, SQL tables, docs) that agents can reference in Slack threads.

## Key Features

### 1. Structured Artifacts
- Each artifact has metadata: ID, type, title, author, summary, tags, timestamp
- Content is stored separately for rendering
- Unique IDs per artifact (e.g., `PR-1234`, `LOG-5678`)

### 2. Persistence
- **JSON files**: `data/artifacts/{type}/{id}.json` (full metadata + content)
- **HTML files**: `data/artifacts/{type}/{id}.html` (human-readable pages)
- Auto-creates directory structure on first use

### 3. Web Server
- Lightweight Flask server on `http://localhost:8000/artifacts/`
- Serves HTML pages with proper styling
- CORS enabled for local testing
- Runs in background thread (non-blocking)

### 4. Search & Indexing
- In-memory index of all loaded artifacts
- Search by keyword in title or summary
- Fast lookups for LLM grounding

### 5. LLM Integration
- Artifacts are searched based on conversation context
- Relevant artifacts included as hidden grounding context
- Agents can reference artifacts naturally in responses

## Usage

### Generate an Artifact
```python
from src.slack_io.artifacts import generate_artifact, save_artifact

# Generate and persist automatically
artifact = generate_artifact("Mike_BE", artifact_type="pr")
url = artifact.url()  # Returns: http://localhost:8000/artifacts/pr/PR-1234.html
```

### Search Artifacts
```python
from src.slack_io.artifacts import search_artifacts

results = search_artifacts("error", limit=5)
for artifact in results:
    print(artifact.title, artifact.url())
```

### Access in Code
```python
from src.slack_io.artifacts import ARTIFACT_INDEX

# Get specific artifact by ID
artifact = ARTIFACT_INDEX.get("PR-1234")

# Slack formatting
slack_link = artifact.slug()  # Returns: <http://localhost:8000/artifacts/pr/PR-1234.html|PR-1234: Bugfix for NullPointer>
```

## Artifact Types

1. **PR** - Code diffs with syntax highlighting
2. **Log** - Error logs with stack traces
3. **SQL** - Query results formatted as tables
4. **Doc** - Decision documents (ADRs, rollback plans, priorities)

## HTML Rendering

Each artifact gets a beautiful HTML page with:
- Header with title, author, timestamp, tags
- Summary section
- Content rendered with appropriate formatting:
  - PRs: Color-coded diff (+green, -red)
  - Logs: Monospace formatting
  - SQL: Tables with headers
  - Docs: Markdown-style formatting

## Startup Integration

The artifact server starts automatically with the Slack app in `bolt_app.py`:
1. Loads existing artifacts from disk
2. Starts Flask server in background thread
3. Agents can generate and reference artifacts immediately

## File Structure

```
slackbench_real_sim/
  data/
    artifacts/
      pr/          # PR diffs
      logs/        # Error logs
      sql/         # Query results
      docs/        # Decision docs
      issues/      # GitHub-style issues (future)
  src/slack_io/
    artifacts.py          # Generation, persistence, index
    artifact_server.py    # Flask web server
```

## Example Workflow

1. Agent decides to include a PR in a message
2. Calls `generate_artifact(persona="Mike_BE", type="pr")`
3. Artifact is saved to disk (JSON + HTML)
4. Returns URL: `http://localhost:8000/artifacts/pr/PR-1234.html`
5. Agent includes link in Slack message
6. User clicks link → sees beautiful HTML page

## Future Enhancements

- Support for ngrok for external HTTPS URLs
- Artifact versioning
- Artifact relationships/chains
- User-generated artifacts
- Metrics and analytics

