"""
Scenario Manager - Seeds conversations with specific topics and contexts
"""
import yaml
import os
import random
from typing import Dict, List, Optional
from .persona_registry import PERSONAS, CHANNEL_NAME_TO_ID
from .user_registry import load_user_personas
from .slack_user_post import user_post_message
from .agent_engine import generate_reply

USER_PERSONAS = load_user_personas()

class ScenarioManager:
    def __init__(self, scenarios_dir: str = None):
        if scenarios_dir is None:
            # Get the directory two levels up from this file
            _DIR = os.path.dirname(os.path.abspath(__file__))
            _PROJECT_ROOT = os.path.dirname(os.path.dirname(_DIR))
            scenarios_dir = os.path.join(_PROJECT_ROOT, "configs", "scenarios")
        
        self.scenarios_dir = scenarios_dir
        self.scenarios = self._load_scenarios()
    
    def _load_scenarios(self) -> List[Dict]:
        """Load all scenario YAML files"""
        scenarios = []
        if not os.path.exists(self.scenarios_dir):
            return scenarios
        
        for filename in os.listdir(self.scenarios_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.scenarios_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        scenario = yaml.safe_load(f)
                        scenarios.append(scenario)
                except Exception as e:
                    print(f"Error loading scenario {filename}: {e}")
        
        return scenarios
    
    def get_random_scenario(self) -> Optional[Dict]:
        """Return a random scenario"""
        if not self.scenarios:
            return None
        return random.choice(self.scenarios)
    
    def seed_scenario_opener(self, scenario: Dict) -> bool:
        """Post the initial message for a scenario"""
        opener = scenario.get("opener")
        if not opener:
            return False
        
        persona_name = opener.get("persona")
        channel_name = opener.get("channel")
        message = opener.get("message")
        
        if not all([persona_name, channel_name, message]):
            return False
        
        # Get the persona identity
        identity = USER_PERSONAS.get(persona_name)
        if not identity:
            print(f"[SCENARIO] No user token for {persona_name}")
            return False
        
        # Get channel ID
        channel_id = CHANNEL_NAME_TO_ID.get(channel_name)
        if not channel_id:
            print(f"[SCENARIO] Channel {channel_name} not found")
            return False
        
        # Post the message
        try:
            user_post_message(identity, channel_id, message, thread_ts=None)
            print(f"[SCENARIO] Seeded '{scenario['title']}' in #{channel_name} as {persona_name}")
            return True
        except Exception as e:
            print(f"[SCENARIO] Error seeding scenario: {e}")
            return False
    
    def get_scenario_context(self, scenario: Dict) -> str:
        """Get the initial context for a scenario"""
        return scenario.get("initial_context", "")

