---
name: prompt-forge
description: Set up or troubleshoot Prompt Forge's isolated Codex preprocessing, native desktop backend, external submission command, and verbatim-material boundary.
---

# Prompt Forge for Codex

Strict isolation requires running Forge before submission to the working agent.
Invoking this skill after a user submits a raw task cannot remove that task from the
current model's context. Do not claim that a skill, subagent spawned by the working
agent, or an additive native hook provides pre-submission isolation.

The optional native backend runs Forge from shared app-server submission handlers.
Its versioned installation is under `~/.local/share/prompt-forge/native/` and the
desktop selects it through `CODEX_CLI_PATH`. Consult the repository's
`codex/backend/README.md` for staging, verification, shared-host setup and rollback.
Do not infer that this backend is installed merely because this skill is available.
It covers typed task submissions, steering, queue edits and human goals. It uses
the original first-message/50-word eligibility rules and semantic simplicity gate;
`forge:` forces processing and `raw:` explicitly bypasses it. The material marker
alone does not force processing. Eligible failures block the turn. Shared desktop
chats require both clients to use the same host runtime, such as SSH over ZeroTier;
this does not intercept ordinary cloud ChatGPT chats or enable mobile pairing.

The separate external command supports:

```text
python scripts/forge.py preview --file task.txt --output forged.txt
python scripts/forge.py local --file task.txt --cwd /path/to/project
python scripts/forge.py cloud --file task.txt --env ENVIRONMENT_ID --branch BRANCH
```

It uses the existing Codex CLI login and configured model for an ephemeral,
read-only forge in an empty temporary directory. Shell, apps, plugins, hooks,
browser, memories and subagents are disabled. No conversation history or project
instructions are supplied. The working agent starts only after a complete brief
is returned. Errors and oversized requests stop submission; there is no raw fallback.

Use a line `//prompt-forge` or `//PROMPT FORGE:` to separate raw material above
from the task below. Everything through the marker line, including original line
endings and spacing, is appended unchanged after the forged brief. It is not sent
to the forger. Keep the input file outside the working project's accessible files
if the raw task must also remain unavailable to later filesystem reads.

The external command always forges, including simple requests. `raw:` is rejected
in its strict mode. The command alone does not intercept native `/goal` or later
messages typed directly into Codex; the optional native backend is needed for that.
To forge a goal, describe the desired completion condition in the input; the command
does not activate goal mode. Cloud submission uses the installed CLI's cloud service;
it does not install an automatic hook in desktop, browser, or mobile cloud chats.

See [the forge method](references/forge-system.md) when maintaining the isolated
call. Preserve user constraints and distinguish inferred requirements from authority.
