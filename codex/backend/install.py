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


def environment(value, name="CODEX_CLI_PATH"):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                       winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            previous, kind = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            previous, kind = None, winreg.REG_SZ
        if value is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, kind, value)
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
        raise SystemExit("Use install_linux.py for a Linux host.")
    binary = ROOT / "codex.exe"
    rollback = ROOT / "previous-backend.json"
    if args.action == "stage":
        if not all((args.build, args.resources, args.real_codex)):
            parser.error("stage needs --build, --resources and --real-codex")
        version = subprocess.check_output([str(args.build), "--version"], text=True).strip()
        if version != "codex-cli " + VERSION:
            raise SystemExit("Backend build does not match the installed desktop version")
        bundled_version = subprocess.check_output([str(args.resources / "codex.exe"), "--version"], text=True).strip()
        if bundled_version != version:
            raise SystemExit("The desktop has a different backend version; rebuild and verify compatibility first")
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
        bin_dir = Path.home() / ".local/bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        launcher = bin_dir / "codex-forge.exe"
        marker = bin_dir / "codex-forge-launcher.json"
        import hashlib
        if launcher.exists():
            if not marker.exists() or json.loads(marker.read_text())["sha256"] != hashlib.file_digest(launcher.open("rb"), "sha256").hexdigest():
                raise SystemExit("An unrelated codex-forge.exe already exists")
            # Remove only our identified legacy launcher. Windows Application
            # Control may reject that locally compiled helper. The verified
            # native backend can serve as the entry point directly.
            launcher.unlink()
            marker.unlink()
        entry = ROOT / "codex-forge.exe"
        if entry.exists():
            entry.unlink()
        os.link(binary, entry)
        print(f"Staged native backend: {binary}")
        print("The app backend selection has not changed. Run the smoke verification before activation.")
    elif args.action == "activate":
        if not (ROOT / "smoke-verified.json").is_file():
            raise SystemExit("Native backend smoke verification must pass before activation")
        import hashlib
        proof = json.loads((ROOT / "smoke-verified.json").read_text(encoding="utf-8"))
        if proof["sha256"] != hashlib.file_digest(binary.open("rb"), "sha256").hexdigest():
            raise SystemExit("Backend binary changed since verification")
        previous = environment("codex-forge")
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            user_path, _ = winreg.QueryValueEx(key, "Path")
        if str(ROOT).lower() not in [p.lower().rstrip("\\") for p in user_path.split(";")]:
            environment(str(ROOT) + ";" + user_path, "Path")
        if not rollback.exists():
            write_json(rollback, {"CODEX_CLI_PATH": previous})
        print("Prompt Forge selected for the next complete Codex desktop restart.")
    else:
        previous = json.loads(rollback.read_text(encoding="utf-8"))["CODEX_CLI_PATH"]
        environment(previous)
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            user_path, _ = winreg.QueryValueEx(key, "Path")
        environment(";".join(p for p in user_path.split(";") if p.lower().rstrip("\\") != str(ROOT).lower()), "Path")
        print("Previous backend selection restored. Restart Codex desktop to use it.")


if __name__ == "__main__":
    main()
