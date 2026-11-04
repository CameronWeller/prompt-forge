"""Install the native backend for the existing Linux desktop app, per user."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

VERSION = "0.166.0-alpha.6"
ROOT = Path.home() / ".local/share/prompt-forge/native" / VERSION


def desktop_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "activate", "restore"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--resources", type=Path, default=Path("/usr/lib/chatgpt/resources"))
    parser.add_argument("--desktop-file", type=Path, default=Path("/usr/share/applications/chatgpt.desktop"))
    parser.add_argument("--shared", action="store_true")
    args = parser.parse_args()
    binary = ROOT / "codex-bin"
    environment_file = Path.home() / ".config/environment.d/90-prompt-forge.conf"
    desktop_file = Path.home() / ".local/share/applications" / args.desktop_file.name
    rollback_file = ROOT / "previous-desktop.json"
    if args.action == "stage":
        if not args.build:
            parser.error("stage requires --build")
        args.build.chmod(0o755)
        version = subprocess.check_output([str(args.build), "--version"], text=True).strip()
        if version != "codex-cli " + VERSION:
            raise SystemExit("Native backend version mismatch")
        ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.build, binary)
        for name in ("codex-code-mode-host", "rg", "bwrap"):
            source = args.resources / name
            if source.exists():
                shutil.copy2(source, ROOT / name)
        isolated = ROOT / "isolated"
        isolated.mkdir(exist_ok=True)
        shutil.copy2(args.resources / "codex", isolated / "codex")
        shutil.copytree(Path(__file__).resolve().parents[1], ROOT / "codex", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (ROOT / "prompt-forge-backend.json").write_text(json.dumps({
            "command": [sys.executable, str(ROOT / "codex/backend/runner.py")],
            "real_codex": str(isolated / "codex"), "version": VERSION,
        }, indent=2), encoding="utf-8")
        print(f"Staged native backend: {binary}; the desktop selection is unchanged.")
    elif args.action == "activate":
        proof = json.loads((ROOT / "smoke-verified.json").read_text(encoding="utf-8"))
        if proof["sha256"] != hashlib.file_digest(binary.open("rb"), "sha256").hexdigest():
            raise SystemExit("Backend changed since smoke verification")
        if not rollback_file.exists():
            rollback_file.write_text(json.dumps({str(path): path.read_text(encoding="utf-8") if path.exists() else None
                for path in (environment_file, desktop_file)}, indent=2), encoding="utf-8")
        backup = json.loads(rollback_file.read_text(encoding="utf-8"))
        original = backup[str(desktop_file)] or args.desktop_file.read_text(encoding="utf-8")
        selected = ROOT / "codex-desktop" if args.shared else binary
        if not selected.is_file():
            raise SystemExit("Set up and verify the shared host before selecting it")
        lines = []
        for line in original.splitlines():
            if line.startswith("Exec="):
                line = "Exec=env " + desktop_quote("CODEX_CLI_PATH=" + str(selected)) + " " + line[5:]
            elif line == "DBusActivatable=true":
                line = "DBusActivatable=false"
            lines.append(line)
        desktop_file.parent.mkdir(parents=True, exist_ok=True)
        desktop_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        environment_file.parent.mkdir(parents=True, exist_ok=True)
        environment_file.write_text("# Prompt Forge native backend\nCODEX_CLI_PATH=" + desktop_quote(selected) + "\n", encoding="utf-8")
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(desktop_file.parent)], check=True)
        print("Prompt Forge selected for the next complete ChatGPT desktop restart.")
    else:
        for name, contents in json.loads(rollback_file.read_text(encoding="utf-8")).items():
            path = Path(name)
            if contents is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(contents, encoding="utf-8")
        print("Previous desktop selection restored; restart the app to apply it.")


if __name__ == "__main__":
    main()
