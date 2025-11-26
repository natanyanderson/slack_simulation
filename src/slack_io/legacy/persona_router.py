import random
from typing import Dict, Any
from ..shared.slack_client import post_message

PERSONAS = {
    "Gabriella_PM": ("Gabriella_PM", ":memo:"),
    "Mike_BE": ("Mike_BE", ":gear:"),
    "Sarah_FE": ("Sarah_FE", ":art:"),
    "Kevin_QA":     ("Kevin_QA", ":mag:"),
    "Nina_SRE":     ("Nina_SRE", ":helmet_with_white_cross:"),
    "Ravi_Staff":   ("Ravi_Staff", ":compass:"),
    "Dana_DS":      ("Dana_DS", ":bar_chart:"),
    "Zoey_UX":      ("Zoey_UX", ":lipstick:"),
    "Tara_TPM":     ("Tara_TPM", ":calendar:"),
}

def choose_responder(channel: str, event_text: str) -> str:
    if channel.startswith("C"):
        pass
    pool = list(PERSONAS.keys())
    return random.choice(pool)


def generate_reply_text(persona: str, event_text: str, recent_context: str) -> str:
    return f"Ack - looking into this. {recent_context[:80]}"


def maybe_reply(channel: str, thread_ts: str, event_text: str, recent_context: str):
    persona = choose_responder(channel, event_text)
    username, icon = PERSONAS[persona]
    text = generate_reply_text(persona, event_text, recent_context)
    post_message(channel=channel, text=text, username=username, icon_emoji=icon, thread_ts=thread_ts)