"""
Thread Progression API - Simple state machine for thread lifecycle management
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import json
import time
import os

# Get the project root directory
_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_DIR))
STATE_PATH = os.path.join(_PROJECT_ROOT, "data", "threads_state.jsonl")

# Create data directory if it doesn't exist
os.makedirs(os.path.join(_PROJECT_ROOT, "data"), exist_ok=True)

PHASE_ORDER = ["DETECT", "TRIAGE", "HYPOTHESIS", "EXPERIMENT", "FIX", "REVIEW", "POSTMORTEM", "CLOSED"]

@dataclass
class ThreadState:
    chan: str
    root_ts: str
    phase: str = "DETECT"
    owner: Optional[str] = None
    checklist: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    last_owner_activity: float = field(default_factory=time.time)  # Track when owner last spoke

def load_states() -> Dict[str, ThreadState]:
    """Load all thread states from JSONL file"""
    d = {}
    if not os.path.exists(STATE_PATH):
        return d
    with open(STATE_PATH) as f:
        for line in f:
            o = json.loads(line)
            d[f"{o['chan']}:{o['root_ts']}"] = ThreadState(**o)
    return d

def save_state(s: ThreadState):
    """Append-only log (simple & traceable)"""
    with open(STATE_PATH, "a") as f:
        f.write(json.dumps(s.__dict__) + "\n")

def advance_phase(s: ThreadState):
    """Advance thread to next phase in lifecycle"""
    i = PHASE_ORDER.index(s.phase)
    if i < len(PHASE_ORDER) - 1:
        s.phase = PHASE_ORDER[i + 1]
        save_state(s)

def mark_check(s: ThreadState, label: str, done: bool = True):
    """Mark a checklist item as complete or incomplete"""
    # store as "label ✅/❌"
    base = label.split(" ✅")[0].split(" ❌")[0]
    s.checklist = [c for c in s.checklist if not c.startswith(base)]
    s.checklist.append(f"{base} {'✅' if done else '❌'}")
    save_state(s)

def get_state(chan: str, root_ts: str, states: Dict[str, ThreadState]) -> Optional[ThreadState]:
    """Get state for a specific thread"""
    key = f"{chan}:{root_ts}"
    return states.get(key)

def init_state(chan: str, root_ts: str, owner: Optional[str] = None) -> ThreadState:
    """Initialize a new thread state"""
    s = ThreadState(chan=chan, root_ts=root_ts, owner=owner)
    save_state(s)
    return s

def get_or_create_state(chan: str, root_ts: str, owner: Optional[str] = None, states: Dict[str, ThreadState] = None) -> ThreadState:
    """Get existing state or create new one"""
    if states is None:
        states = load_states()
    
    state = get_state(chan, root_ts, states)
    if state is None:
        state = init_state(chan, root_ts, owner)
    return state

def reassign_owner(s: ThreadState, new_owner: str):
    """Reassign thread to a new owner"""
    s.owner = new_owner
    s.last_owner_activity = time.time()
    save_state(s)

def reset_phase(s: ThreadState):
    """Reset thread to DETECT phase"""
    s.phase = PHASE_ORDER[0]
    save_state(s)

