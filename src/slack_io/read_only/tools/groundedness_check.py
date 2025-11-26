#!/usr/bin/env python3
import json, os, sys

PATH = "data/slack_runs_raw.jsonl"
if not os.path.exists(PATH):
    print("No data/slack_runs_raw.jsonl found."); sys.exit(0)

total = 0
with_refs = 0
for line in open(PATH, "r", encoding="utf-8"):
    try:
        r = json.loads(line)
    except Exception:
        continue
    total += 1
    if r.get("supports"):
        with_refs += 1

rate = (with_refs / total) if total else 0.0
print(f"Replies logged: {total}")
print(f"With supports:  {with_refs}  ({rate:.1%})")