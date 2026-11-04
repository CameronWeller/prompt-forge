"""Check that the native backend can still execute a read-only tool request."""
import argparse
from pathlib import Path
import queue
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
from rpc import AppServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    events = queue.Queue()
    server = AppServer(events.put, binary=str(args.binary.resolve()))
    thread_id = None
    try:
        with tempfile.TemporaryDirectory(prefix="forge-tools-smoke-") as workspace:
            expected = "NATIVE_READ_" + uuid.uuid4().hex
            (Path(workspace) / "verify.txt").write_text(expected, encoding="utf-8")
            thread_id = server.call("thread/start", {
                "cwd": workspace, "approvalPolicy": "never", "sandbox": "read-only",
                "config": {"features.shell_tool": True, "features.code_mode_host": True,
                           "features.apps": False, "features.plugins": False,
                           "features.multi_agent": False, "features.multi_agent_v2": False,
                           "web_search": "disabled"},
            })["thread"]["id"]
            server.call("turn/start", {"threadId": thread_id, "input": [{"type": "text",
                "text": "raw: Read verify.txt in the working directory using available tools. Respond only with its exact contents. Do not modify any files."}]})
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                event = events.get(timeout=max(1, deadline - time.monotonic()))
                if event.get("method") == "turn/completed" and event.get("params", {}).get("threadId") == thread_id:
                    assert event["params"]["turn"]["status"] == "completed"
                    break
            else:
                raise RuntimeError("Tool verification timed out")
            history = server.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
            assert any(item.get("text", "").strip() == expected
                       for turn in history["turns"] for item in turn["items"]
                       if item["type"] == "agentMessage"), "Worker could not read the test file with its tools"
            print("Native read-only tool execution verified.")
    finally:
        if thread_id:
            try:
                server.call("thread/archive", {"threadId": thread_id})
            except Exception:
                pass
        server.close()


if __name__ == "__main__":
    main()
