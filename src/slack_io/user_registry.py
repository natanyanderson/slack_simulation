import json, os
from slack_sdk import WebClient

# Get the project root directory (two levels up from this file)
_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_DIR))

TOKENS_PATH = os.path.join(_PROJECT_ROOT, "secrets", "personas.tokens.json")
MAP_PATH    = os.path.join(_PROJECT_ROOT, "secrets", "personas.map.json")

class PersonaIdentity:
    def __init__(self, persona, user_id, user_token):
        self.persona = persona
        self.user_id = user_id
        self.user_token = user_token
        self.client = WebClient(token=user_token)

def load_user_personas():
    if not (os.path.exists(TOKENS_PATH) and os.path.exists(MAP_PATH)):
        return {}
    tokens = json.load(open(TOKENS_PATH))
    mapping = json.load(open(MAP_PATH))
    out = {}
    for persona, meta in mapping.items():
        uid = meta["user_id"]
        tok = tokens.get(uid, {}).get("user_token")
        if tok:
            out[persona] = PersonaIdentity(persona, uid, tok)
    return out