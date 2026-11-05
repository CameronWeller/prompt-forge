"""Connect native desktop stdio clients to the same private Linux app-server."""
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    root = Path(__file__).resolve().parents[2]
    binary = root / "codex-bin"
    arguments = sys.argv[1:]
    # Desktop reads organization policy with a one-shot JSON command before
    # opening its main connection. Preserve the native policy response.
    if "--print-startup-config" in arguments:
        os.execv(str(binary), [str(binary), *arguments])
    if "app-server" in arguments:
        tail = arguments[arguments.index("app-server") + 1:]
        desktop_proxy = tail == ["proxy"]
        subcommands = {"daemon", "proxy", "generate-ts", "generate-json-schema"}
        if desktop_proxy or not any(arg in subcommands for arg in tail):
            # Only a local Unix socket is exposed. Remote desktops arrive through
            # their existing SSH connection over ZeroTier.
            subprocess.run(["systemctl", "--user", "start", "prompt-forge-app-server.service"],
                           check=True, stdout=subprocess.DEVNULL)
            deadline = time.monotonic() + 15
            while not (root / "shared.sock").is_socket():
                if time.monotonic() >= deadline:
                    raise RuntimeError("Shared socket did not become ready")
                time.sleep(0.05)
            # Desktop SSH already speaks WebSocket over its raw proxy. Without
            # an explicit socket, upstream connects it to the stock daemon.
            if desktop_proxy:
                os.execv(str(binary), [str(binary), *arguments, "--sock", str(root / "shared.sock")])
            # Local JSONL clients need the WebSocket adapter instead.
            from socket_bridge import run
            run(root / "shared.sock")
            return
    os.execv(str(binary), [str(binary), *arguments])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("Prompt Forge shared backend could not start.\n")
        raise SystemExit(1) from None
