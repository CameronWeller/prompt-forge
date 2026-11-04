"""Stage a tested native backend; activate or restore the desktop backend selection."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

VERSION = "0.166.0-alpha.6"
ROOT = Path.home() / ".local/share/prompt-forge/native" / VERSION


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def environment(value):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                       winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            previous, kind = winreg.QueryValueEx(key, "CODEX_CLI_PATH")
        except FileNotFoundError:
            previous, kind = None, winreg.REG_SZ
        if value is None:
            try:
                winreg.DeleteValue(key, "CODEX_CLI_PATH")
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, "CODEX_CLI_PATH", 0, kind, value)
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 2000, ctypes.byref(result))
    return previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "activate", "restore"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--resources", type=Path)
    parser.add_argument("--real-codex", type=Path)
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("This installer is for the Windows host; other devices connect to it remotely.")
    binary = ROOT / "codex.exe"
    rollback = ROOT / "previous-backend.json"
    if args.action == "stage":
        if not all((args.build, args.resources, args.real_codex)):
            parser.error("stage needs --build, --resources and --real-codex")
        version = subprocess.check_output([str(args.build), "--version"], text=True).strip()
        if version != "codex-cli " + VERSION:
            raise SystemExit("Backend build does not match the installed desktop version")
        ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.build, binary)
        for name in ("codex-code-mode-host.exe", "codex-command-runner.exe",
                     "codex-windows-sandbox-service.exe", "codex-windows-sandbox-setup.exe", "rg.exe"):
            shutil.copy2(args.resources / name, ROOT / name)
        isolated = ROOT / "isolated"
        isolated.mkdir(exist_ok=True)
        shutil.copy2(args.real_codex, isolated / "codex.exe")
        shutil.copytree(Path(__file__).resolve().parents[1], ROOT / "codex", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        write_json(ROOT / "prompt-forge-backend.json", {
            "command": [sys.executable, str(ROOT / "codex/backend/runner.py")],
            "real_codex": str(isolated / "codex.exe"),
            "version": VERSION,
        })
        print(f"Staged native backend: {binary}")
        print("The app backend selection has not changed. Run the smoke verification before activation.")
    elif args.action == "activate":
        if not (ROOT / "smoke-verified.json").is_file():
            raise SystemExit("Native backend smoke verification must pass before activation")
        import hashlib
        proof = json.loads((ROOT / "smoke-verified.json").read_text(encoding="utf-8"))
        if proof["sha256"] != hashlib.file_digest(binary.open("rb"), "sha256").hexdigest():
            raise SystemExit("Backend binary changed since verification")
        previous = environment(str(binary))
        if not rollback.exists():
            write_json(rollback, {"CODEX_CLI_PATH": previous})
        print("Prompt Forge selected for the next complete Codex desktop restart.")
    else:
        previous = json.loads(rollback.read_text(encoding="utf-8"))["CODEX_CLI_PATH"]
        environment(previous)
        print("Previous backend selection restored. Restart Codex desktop to use it.")


if __name__ == "__main__":
    main()
