"""Isolated processor entry point for the native Codex backend (JSON stdin/stdout)."""
import json
import os
from pathlib import Path
import sys


def main():
    # Configuration is installed alongside the backend, never supplied by a chat.
    root = Path(__file__).resolve().parents[2]
    settings = json.loads((root / "prompt-forge-backend.json").read_text(encoding="utf-8"))
    os.environ["PROMPT_FORGE_REAL_CODEX"] = settings["real_codex"]
    os.environ.pop("CODEX_CLI_PATH", None)
    os.environ.pop("CODEX_APP_RUNTIME_CLI_PATH", None)
    os.environ.pop("CODEX_THREAD_ID", None)
    sys.path.insert(0, str(root / "codex" / "client"))
    from preprocess import main as preprocess_main
    preprocess_main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Neither Python exceptions nor child stderr may disclose a raw draft.
        sys.stdout.write('{"decision":"error"}')
        raise SystemExit(1) from None
