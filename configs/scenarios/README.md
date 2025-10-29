# Scenarios

Scenarios provide structured ways to seed conversations in your Slack workspace. Each scenario defines:

- **Context**: A situation or incident that needs discussion
- **Personas**: Which team members should participate
- **Opener**: An initial message to kickstart the conversation
- **Keywords**: Terms that guide the conversation naturally

## Adding Scenarios

1. Create a new YAML file in this directory (e.g., `S003_feature_launch.yaml`)
2. Follow the format from existing scenarios
3. The autonomous loop will periodically seed random scenarios

## Example Scenario

```yaml
id: "S001_search_latency"
title: "SKU Search p95 regression in prod"
description: "Production latency spike on search endpoint"

channels: ["sre-ops", "eng-backend"]

personas: ["Mike_BE", "Nina_SRE", "Kevin_QA"]

opener:
  persona: "Kevin_QA"
  channel: "sre-ops"
  message: "Heads-up: p95 latency on search spiked to 4200ms. @Mike_BE can you check logs?"

keywords: ["latency", "database", "monitoring"]
```

## Using Scenarios

In your code, you can manually trigger scenarios:

```python
from scenario_manager import ScenarioManager

manager = ScenarioManager()
scenario = manager.get_random_scenario()
manager.seed_scenario_opener(scenario)
```

Or configure them to trigger automatically in your autonomous loop.

