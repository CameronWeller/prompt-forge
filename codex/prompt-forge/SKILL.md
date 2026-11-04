---
name: prompt-forge
description: Set up or troubleshoot Prompt Forge's separate Codex submission command and its verbatim-material boundary. The command refines a task in an isolated call before starting the working agent.
---

# Prompt Forge for Codex

Strict isolation requires running `scripts/forge.py` outside the working chat.
Invoking this skill after a user submits a raw task cannot remove that task from the
current model's context. Do not claim that a skill, subagent spawned by the working
agent, or an additive native hook provides pre-submission isolation.

The external command supports:

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

The command always forges, including simple requests. `raw:` is rejected in strict
mode. Native `/goal` and later messages typed directly into Codex are not intercepted.
To forge a goal, describe the desired completion condition in the input; the command
does not activate goal mode. Cloud submission uses the installed CLI's cloud service;
it does not install an automatic hook in desktop, browser, or mobile cloud chats.

See [the forge method](references/forge-system.md) when maintaining the isolated
call. Preserve user constraints and distinguish inferred requirements from authority.
