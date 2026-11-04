#!/usr/bin/env python3
"""Gate and forge a human message before submitting any working-agent turn."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prompt-forge/scripts"))
from forge import forge, ForgeError, ForgeCallError, MAX_INPUT

RAW = re.compile(r"^raw:\s*", re.I)
FORCE = re.compile(r"^forge:\s*", re.I)
SLASH = re.compile(r"^/[\w:-]+(?:\s|$)")
BASH = re.compile(r"^<bash-(?:input|stdout|stderr)>")
GOAL = re.compile(r"^/goal(?:\s+|$)", re.I)
GOAL_CONTROL = re.compile(r"^(clear|off|none|status|show|pause|resume)$", re.I)


def remove_override(raw: str, name: str) -> str:
    """Remove the control prefix without trimming verbatim source material."""
    match = re.match(r"^\s*" + name + r":", raw, re.I)
    if not match:
        return raw
    rest = raw[match.end():]
    newline = re.match(r"^[ \t]*\r?\n", rest)
    if newline:
        return rest[newline.end():]
    return rest[1:] if rest.startswith((" ", "\t")) else rest


def classify(raw: str, *, first=False, goal=False, source="user") -> dict:
    def result(decision, reason, text=raw, mode=None):
        return {"decision": decision, "reason": reason, "prompt": text, "mode": mode, "is_goal": goal}
    if source != "user":
        return result("skipped", "not a human message")
    typed = raw.strip()
    if GOAL.match(typed):
        goal = True
        raw = GOAL.sub("", typed, count=1)
        typed = raw.strip()
    if goal:
        if not typed or typed.startswith('-') or GOAL_CONTROL.fullmatch(typed):
            return result("skipped", "goal control", raw)
        if RAW.match(typed):
            return result("skipped", "raw override", remove_override(raw, "raw"))
        if len(typed) > MAX_INPUT:
            return result("skipped", "over 24000 characters", raw)
        return result("eligible", "goal", raw, "goal")
    if not typed or SLASH.match(typed) or BASH.match(typed):
        return result("skipped", "empty, command, or bash input")
    if RAW.match(typed):
        return result("skipped", "raw override", remove_override(raw, "raw"))
    forced = bool(FORCE.match(typed))
    text = remove_override(raw, "forge") if forced else raw
    count = len(text.split())
    reason = "forge override" if forced else "large prompt" if count >= 50 else "first prompt" if first and count >= 4 else None
    if reason is None:
        return result("skipped", "short first prompt or small follow-up", text)
    if len(text.strip()) > MAX_INPUT:
        return result("skipped", "over 24000 characters", text)
    return result("eligible", reason, text, "forced" if forced else "gated")


def preprocess(raw: str, *, first=False, goal=False, source="user", model=None, timeout=150, call=forge) -> dict:
    decision = classify(raw, first=first, goal=goal, source=source)
    if decision["decision"] != "eligible":
        return decision
    try:
        for attempt in range(2):
            try:
                brief = call(decision["prompt"], mode=decision["mode"], model=model, timeout=timeout)
                break
            except ForgeCallError:
                if attempt:
                    raise
        if brief is None:
            return {**decision, "decision": "pass", "reason": "simple, clear request"}
        return {**decision, "decision": "forged", "prompt": brief}
    except (ForgeError, OSError, UnicodeError, ValueError):
        # An eligible request must never reach the worker after a forge failure.
        return {"decision": "error", "reason": "Isolated forge failed. Nothing was submitted. Retry or explicitly use raw: to bypass.", "mode": decision["mode"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", action="store_true")
    parser.add_argument("--goal", action="store_true")
    parser.add_argument("--source", choices=("user", "agent", "system"), default="user")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args()
    # JSON avoids shell interpolation and retains the input's exact text/line endings.
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    raw = data["text"]
    if not isinstance(raw, str):
        raise SystemExit("text must be a string")
    result = preprocess(raw, first=args.first, goal=args.goal, source=args.source,
                       model=args.model, timeout=args.timeout)
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
