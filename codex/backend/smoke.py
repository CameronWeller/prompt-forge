"""Verify the installed native backend before changing the desktop selection."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
from rpc import AppServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    events = queue.Queue()
    server = AppServer(events.put, binary=str(binary))
    settings_path = binary.parent / "prompt-forge-backend.json"
    settings = settings_path.read_bytes()
    thread_id = None
    try:
        with tempfile.TemporaryDirectory(prefix="forge-native-smoke-") as workspace:
            thread_id = server.call("thread/start", {
                "cwd": workspace, "approvalPolicy": "never", "sandbox": "read-only",
                "config": {"features.shell_tool": False, "features.apps": False,
                           "features.plugins": False, "features.multi_agent": False,
                           "features.multi_agent_v2": False,
                           "features.code_mode_host": False, "web_search": "disabled"},
            })["thread"]["id"]
            material = "NATIVE_MATERIAL café 雪\t  \r\n//prompt-forge\r\n"
            raw = material + "forge: Reply with exactly NATIVE_FORGE_OK. Do not use tools or inspect files."
            # Force through the gate without changing any source-material bytes.
            request = "forge: " + raw
            server.call("turn/start", {"threadId": thread_id, "turnTrigger": "user",
                        "input": [{"type": "text", "text": request, "text_elements": []}]}, timeout=360)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                event = events.get(timeout=max(1, deadline - time.monotonic()))
                if event.get("method") == "turn/completed" and event.get("params", {}).get("threadId") == thread_id:
                    if event["params"]["turn"].get("status") != "completed":
                        raise RuntimeError("Native worker smoke turn did not complete")
                    break
            else:
                raise RuntimeError("Native worker smoke turn timed out")
            history = server.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
            user_items = [item for turn in history["turns"] for item in turn["items"]
                          if item["type"] == "userMessage"]
            assert any(item.get("text", "").strip() == "NATIVE_FORGE_OK"
                       for turn in history["turns"] for item in turn["items"]
                       if item["type"] == "agentMessage"), "Worker did not satisfy the forged request"
            prompt = "\n".join(part["text"] for part in user_items[0]["content"] if part["type"] == "text")
            assert prompt.startswith("GIVEN:"), "Worker received an unforged draft"
            assert prompt.endswith(material), "Material did not survive verbatim"
            assert request not in json.dumps(history, ensure_ascii=False), "Raw draft entered worker history"

            # A broken processor must not become a raw-prompt fallback.
            broken = json.loads(settings)
            broken["command"] = [str(binary.parent / "intentionally-missing-processor.exe")]
            settings_path.write_text(json.dumps(broken), encoding="utf-8")
            try:
                server.call("turn/start", {"threadId": thread_id,
                            "input": [{"type": "text", "text": "forge: NEVER_SUBMIT_RAW_FAILURE_SENTINEL"}]})
            except RuntimeError as error:
                assert "Prompt Forge preprocessing failed" in str(error)
            else:
                raise AssertionError("Failed preprocessing unexpectedly started a turn")
            after = server.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
            assert "NEVER_SUBMIT_RAW_FAILURE_SENTINEL" not in json.dumps(after)
            assert len(after["turns"]) == len(history["turns"])
            proof = {"sha256": hashlib.file_digest(binary.open("rb"), "sha256").hexdigest(),
                     "thread_id": thread_id, "checks": ["native ingress", "isolated forge", "verbatim material", "worker history", "fail closed"]}
            (binary.parent / "smoke-verified.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
            print("Native backend verified: forged-only worker history, exact material, and failure blocking.")
    finally:
        settings_path.write_bytes(settings)
        if thread_id:
            try:
                server.call("thread/archive", {"threadId": thread_id})
            except Exception:
                pass
        server.close()


if __name__ == "__main__":
    main()
