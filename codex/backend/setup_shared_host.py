"""Provision the private shared Linux runtime after native smoke verification."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path.home() / ".local/share/prompt-forge/native/0.166.0-alpha.6"


def main():
    binary = ROOT / "codex-bin"
    proof = json.loads((ROOT / "smoke-verified.json").read_text(encoding="utf-8"))
    if proof["sha256"] != hashlib.file_digest(binary.open("rb"), "sha256").hexdigest():
        raise SystemExit("Verify this backend before creating the shared runtime")
    # The Unix transport rejects a directory whose entries other users can replace.
    # A user's default umask may otherwise make this installation group-writable.
    ROOT.chmod(0o700)
    unit = Path.home() / ".config/systemd/user/prompt-forge-app-server.service"
    if unit.exists() and "Description=Prompt Forge shared Codex backend" not in unit.read_text():
        raise SystemExit("An unrelated shared service already exists")
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("\n".join([
        "[Unit]", "Description=Prompt Forge shared Codex backend", "After=network-online.target",
        "[Service]", "Type=simple", "UMask=0077", "Restart=on-failure", "RestartSec=3",
        # Do not silently enable a relay path that would bypass the user's private
        # network requirement. Phone access can be configured separately.
        "Environment=CODEX_INTERNAL_APP_SERVER_REMOTE_CONTROL_DISABLED=1",
        'Environment="CODEX_INTERNAL_ORIGINATOR_OVERRIDE=Codex Desktop"',
        'ExecStart="' + str(binary) + '" -c features.code_mode_host=true app-server --listen unix://' + str(ROOT / "shared.sock"),
        "[Install]", "WantedBy=default.target", "",
    ]), encoding="utf-8")
    bridge = ROOT / "codex-desktop"
    bridge.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " "
                      + shlex.quote(str(ROOT / "codex/backend/shared_bridge.py")) + ' "$@"\n', encoding="utf-8")
    bridge.chmod(0o755)
    # This is already on the user's SSH login PATH. Do not alter their Nix-managed
    # shell profiles or replace the ordinary codex command.
    command = Path.home() / ".npm-global/bin/codex-forge"
    command.parent.mkdir(parents=True, exist_ok=True)
    if command.exists() or command.is_symlink():
        if not command.is_symlink() or command.resolve() != bridge:
            raise SystemExit("An unrelated codex-forge command already exists")
    else:
        command.symlink_to(bridge)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", unit.name], check=True)
    print("Shared backend ready on a private Unix socket; SSH clients use codex-forge.")


if __name__ == "__main__":
    main()
