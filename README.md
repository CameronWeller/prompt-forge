# prompt-forge

A Claude Code mod that turns loose prompts into outcome-focused briefs before the agent sees them.

When it matters most (the first prompt of a session, any prompt of 50+ words, and every `/goal`
you set), your text goes to an isolated, tool-less Opus call that extrapolates what you mean.
The agent receives only the forged brief:

```
GIVEN / OUTCOME / WHY / TRACK / SCOPE / RESOURCES / DO / CREW / VERIFY / BOUNDS / ASSUMPTIONS / REPORT
```

Everything else runs as typed, with no delay.

A typed prompt that is already simple and clear (one reading, a named target, a checkable
"done", no vague words, one deliverable or a question, nothing destructive or outward-facing) goes
to the agent exactly as typed. The forge judges this by meaning, never length: a short prompt that
carries a lot ("add multi-tenant support", "push to prod") still gets a full brief.

## Install

### Codex (strict external submission)

The Codex port lives in [`codex/`](codex/). It runs an isolated, ephemeral Codex
forge call **before** starting the working agent. The raw request is not submitted
to that agent. This is a separate terminal command, not an automatic desktop or
cloud-composer hook; native Codex hooks cannot replace the submitted user prompt.

Requires Python 3.11+, a current Codex CLI (`0.160.0` tested), and `codex login`.
Install on Windows, macOS, or Linux:

```sh
python codex/install.py
# For a reviewed update: python codex/install.py --update
```

Open a new terminal with `~/.local/bin` on PATH (the Windows installer updates the
user PATH). The installed skill helps explain and maintain the command; invoking
the skill inside an existing chat cannot retroactively hide its raw prompt.

```sh
prompt-forge preview --file task.txt --output forged.txt
prompt-forge local --file task.txt --cwd /path/to/project
prompt-forge cloud --file task.txt --env YOUR_CLOUD_ENVIRONMENT_ID --branch main
```

The cloud command uses `codex cloud exec`. Supply an environment ID accepted by
that CLI service. Desktop Codex Cloud saved-configuration IDs are not assumed to
be interchangeable with CLI environment IDs. For cloud surfaces that do not accept
CLI submission, use preview and submit **only the generated output** in the cloud
composer. This does not install anything into cloud orchestrators or intercept
future messages typed directly in local, web, or mobile chats.

Keep raw material above a marker and the task below it:

```text
Exact source text, logs, or code — spaces and line endings are retained.
//prompt-forge
Explain what this material shows and identify the next check to run.
```

`//PROMPT FORGE:` also works. Everything through the marker line is appended
verbatim after the brief and is excluded from the forge call. Read input from a
UTF-8 file to preserve exact bytes. Do not place the original prompt file in the
working project if you also need it unavailable to the working agent's later
filesystem reads. The forger has no conversation history, uses an empty temporary
workspace, disables shell/apps/plugins/hooks/subagents, and inherits the configured
Codex model. `--forge-model` can override it. The working agent retains its normal
Codex configuration and approvals.

Strict mode always produces a brief: no simple-request PASS, no `raw:` bypass,
and no raw fallback on errors or timeouts. Oversized task instructions are rejected;
large material can go above the marker. `/goal` is not intercepted or activated.
Exact identifiers and paths omitted by the model are added back deterministically.
On Windows, oversized cloud command lines are rejected with a preview alternative.

Validation:

```sh
python -m unittest discover -s codex/tests -v
```

### Claude Code

From a shell (any machine with Claude Code):

```bash
claude plugin install prompt-forge --marketplace CameronWeller/prompt-forge
claude plugin install prompt-forge-view --marketplace CameronWeller/prompt-forge
```

`prompt-forge-view` is a small companion that prints each forged prompt in the chat (the
Claude desktop app draws only command output and messages, not plugin notices). Without it the
forge still works; you just don't see the brief in the desktop app.

Or at the prompt of a Claude Code terminal session:

```
/plugin install prompt-forge --marketplace CameronWeller/prompt-forge
```

Restart Claude Code (or open a new session) to load it.

## Update

```bash
claude plugin marketplace update prompt-forge
claude plugin update prompt-forge@prompt-forge
claude plugin update prompt-forge-view@prompt-forge
```

Releases are tagged `prompt-forge--v<version>` (and `v<version>` on GitHub with notes).
If the same plugin was also uploaded to your claude.ai plugin library, remove that copy: a
library copy loads as a session-only plugin and shadows the installed one.

## What it does

- **Extrapolates, not just rewrites.** Vague words become checkable criteria, gaps are filled, and
  everything inferred is listed under `ASSUMPTIONS:` so your words and its inferences stay apart.
  Readings that would change what gets built are marked `ASK FIRST`.
- **Keeps exact tokens.** A deterministic check re-adds any exact token the brief dropped (paths, URLs, quoted strings, identifiers) under `KEEP VERBATIM`.
- **Never widens authority.** Destructive, outward-facing, costly or secret-touching actions stay
  confirm-first. Your project's own rules (CLAUDE.md, AGENTS.md) still win.
- **Goals:** `/goal <text>` becomes a verifiable completion condition, sized to what the goal is worth.
- **Visible in the chat:** a forged prompt is held, "Forging your prompt…" shows while it runs,
  then "Forged prompt the agent receives:" with the full brief, then the brief is sent as the
  next message, so you see exactly what the agent receives (desktop app included, with
  `prompt-forge-view`). Failures show "Not forged (reason)".
  Your original wording stays in the record as a notice the model never reads. Prompts with
  images are rewritten in place instead.
- **Your material stays whole:** everything above a line starting `//PROMPT FORGE:` reaches the agent
  byte for byte, after the brief. Without that line, the forge is told to quote material in full.
- **Simple requests pass:** the chat shows "Not forged: a simple, clear request" and the agent
  receives your exact words. When unsure, the forge writes the brief.
- **Overrides:** start a prompt with `forge:` to force a full brief (even for a simple one), or
  `raw:` to skip the forge.
- **Only what you send:** the forge reads the engine's stamp on each prompt and fires only for
  what you personally submit: typed at the prompt (desktop app included), Remote Control, or Slack.
  `claude -p` runs, the desktop app's own events, schedules and `/loop`, background-task
  notices, other sessions, subagents and other plugins go through untouched, with no model call.
  Agent briefs are never forged: a model wrote them, and they hold data the agent needs. A reminder
  the app attaches to your message reaches the agent intact and does not count as your words.
  Each decision is logged, without the prompt's text, to the debug log (`claude --debug`).
- **Skips** slash commands and bash-mode lines.
  A transient API error is retried once; if the forge still fails, or a prompt is over 24,000
  characters, your text goes through as typed and a notice says so.

Each forge is one Opus call (high effort), so a forged prompt takes a few seconds to a minute.

## Principles

Built on Felix Rieseberg's
[How to be more ambitious](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/):
**Altitude** (outcomes over artifacts, verbs over nouns), **Depth** (expert methods, rawest material,
outside verification) and **Range** (a wide crew plus an adversary). Folded into that structure:

- **Karpathy guidelines** ([multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), MIT):
  never pick silently between readings, ask first when it matters, every step verified.
- **BMad Method** ([bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD), MIT):
  a right-sized Clarify, Plan or Build-and-verify track, decisions recorded durably, learn and adjust.

- **A research-grade exemplar prompt:** the starting state and materials up front, what counts and the
  tempting shortcuts that do not, an inventory of resources and a finite budget, diagnosing failures
  before fixing them, showing cause rather than correlation, a fixed measurement protocol against a
  baseline on held-out items, naming the proxy that can mislead, explicit Allowed and Not allowed
  lists, working habits that survive a restart, and a short explanation before each step.

The brief does not cap the size of the work: solutions beyond the literal ask are welcome, and are
labelled under `ASSUMPTIONS` so your words and the forge's additions stay apart.

See [SKILL.md](SKILL.md) for the full method.

## Develop and release

```bash
claude plugin validate .
claude plugin test .
# bump "version" in .claude-plugin/plugin.json and .claude-plugin/marketplace.json, commit, then:
claude plugin tag --push
gh release create v<version> --title "prompt-forge v<version>" --notes "..."
```

## License

MIT
