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
    if "app-server" in arguments:
        tail = arguments[arguments.index("app-server") + 1:]
        subcommands = {"daemon", "proxy", "generate-ts", "generate-json-schema"}
        if not any(arg in subcommands for arg in tail):
            # Only a local Unix socket is exposed. Remote desktops arrive through
            # their existing SSH connection over ZeroTier.
            subprocess.run(["systemctl", "--user", "start", "prompt-forge-app-server.service"],
                           check=True, stdout=subprocess.DEVNULL)
            deadline = time.monotonic() + 15
            while not (root / "shared.sock").is_socket():
                if time.monotonic() >= deadline:
                    raise RuntimeError("Shared socket did not become ready")
                time.sleep(0.05)
            arguments = ["app-server", "proxy", "--sock", str(root / "shared.sock")]
    os.execv(str(binary), [str(binary), *arguments])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("Prompt Forge shared backend could not start.\n")
        raise SystemExit(1) from None
