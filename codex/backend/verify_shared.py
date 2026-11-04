"""Verify two desktop-style clients see one live chat through the SSH host."""
import argparse
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
from rpc import AppServer


def completed(events, thread_id, turn_id, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = events.get(timeout=max(1, deadline - time.monotonic()))
        params = item.get("params", {})
        if item.get("method") == "turn/completed" and params.get("threadId") == thread_id and params["turn"]["id"] == turn_id:
            assert params["turn"]["status"] == "completed"
            return
    raise RuntimeError("Shared live event did not arrive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args()
    command = ["ssh", "-T", "-o", "BatchMode=yes", args.ssh_host, "codex-forge", "app-server"]
    events_a, events_b = queue.Queue(), queue.Queue()
    a = AppServer(events_a.put, command=command)
    print("First shared client connected.", flush=True)
    b = AppServer(events_b.put, command=command)
    print("Second shared client connected.", flush=True)
    thread_id = None
    try:
        thread_id = a.call("thread/start", {"cwd": args.cwd, "approvalPolicy": "never", "sandbox": "read-only",
            "config": {"features.shell_tool": False, "features.apps": False, "features.plugins": False,
                       "features.multi_agent": False, "features.multi_agent_v2": False,
                       "features.code_mode_host": False, "web_search": "disabled"}})["thread"]["id"]
        print("Shared verification chat started.", flush=True)
        material = "SHARED_MATERIAL café 雪\t  \r\n//prompt-forge\r\n"
        raw = "forge:\r\n" + material + "Reply with exactly SHARED_FORGE_OK. Do not use tools."
        response = a.call("turn/start", {"threadId": thread_id, "input": [{"type": "text",
            "text": raw}]}, timeout=360)
        turn_id = response["turn"]["id"]
        # A new thread has no persisted rollout until its first turn starts.
        b.call("thread/resume", {"threadId": thread_id})
        print("Second client subscribed.", flush=True)
        completed(events_a, thread_id, turn_id)
        completed(events_b, thread_id, turn_id)
        first = a.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
        second = b.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
        assert first["turns"] == second["turns"], "Clients did not share the same history"
        items = [item for turn in second["turns"] for item in turn["items"]]
        assert any(item.get("text", "").strip() == "SHARED_FORGE_OK" for item in items if item["type"] == "agentMessage")
        users = [item for item in items if item["type"] == "userMessage"]
        text = "\n".join(part["text"] for part in users[0]["content"] if part["type"] == "text")
        assert text.startswith("GIVEN:"), "Shared worker received an unforged draft"
        assert text.endswith(material), "Shared material was not preserved verbatim"
        assert raw not in json.dumps(second, ensure_ascii=False), "Raw draft entered shared worker history"
        print(json.dumps({"shared_live_events": True, "shared_history": True, "isolated_forge": True,
                          "verbatim_material": True,
                          "thread_id": thread_id}))
    finally:
        if thread_id:
            try:
                a.call("thread/archive", {"threadId": thread_id})
            except Exception:
                pass
        a.close()
        b.close()


if __name__ == "__main__":
    main()
