#!/usr/bin/env python3
"""Install the Codex skill and external prompt-forge command for this user."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--update", action="store_true", help="Replace an existing installed Prompt Forge package")
args = parser.parse_args()
source = Path(__file__).resolve().parent / "prompt-forge"
codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
destination = codex_home / "skills" / "prompt-forge"
if destination.exists() and not args.update:
    parser.error(f"Already installed at {destination}; use --update after reviewing changes")
shutil.copytree(source, destination, dirs_exist_ok=args.update, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
bin_dir = Path.home() / ".local" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
script = destination / "scripts" / "forge.py"
if os.name == "nt":
    # PowerShell preserves argument boundaries; CMD shim supports other Windows shells.
    quote = lambda text: "'" + str(text).replace("'", "''") + "'"
    (bin_dir / "prompt-forge.ps1").write_text(f"& {quote(sys.executable)} {quote(script)} @args\nexit $LASTEXITCODE\n", encoding="utf-8")
    (bin_dir / "prompt-forge.cmd").write_text(f'@echo off\n"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, value_type = "", winreg.REG_EXPAND_SZ
        if str(bin_dir).casefold() not in [part.rstrip('\\').casefold() for part in current.split(';')]:
            winreg.SetValueEx(key, "Path", 0, value_type, current.rstrip(';') + ';' + str(bin_dir))
    # Notify Explorer so newly launched terminals can inherit the updated user PATH.
    import ctypes
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 2000, ctypes.byref(result))
else:
    launcher = bin_dir / "prompt-forge"
    launcher.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
print(f"Installed skill: {destination}")
print(f"Installed command: {bin_dir}")
print("Open a new terminal with this directory on PATH. Cloud submission runs the forge locally before sending its result to Codex Cloud.")
