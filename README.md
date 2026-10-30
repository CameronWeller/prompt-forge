# prompt-forge

A Claude Code mod that turns loose prompts into outcome-focused briefs before the agent sees them.

When it matters most (the first prompt of a session, any prompt or agent brief of 50+ words, and
every `/goal`), your text goes to an isolated, tool-less Opus call that extrapolates what you mean.
The agent receives only the forged brief:

```
OUTCOME / WHY / TRACK / DO / CREW / VERIFY / BOUNDS / ASSUMPTIONS / REPORT
```

Everything else runs as typed, with no delay.

## Install

From a shell (any machine with Claude Code):

```bash
claude plugin install prompt-forge --marketplace CameronWeller/prompt-forge
```

Or at the prompt of a Claude Code terminal session:

```
/plugin install prompt-forge --marketplace CameronWeller/prompt-forge
```

Restart Claude Code (or open a new session) to load it.

## Update

```bash
claude plugin marketplace update prompt-forge
claude plugin update prompt-forge@prompt-forge
```

Releases are tagged `prompt-forge--v<version>` (and `v<version>` on GitHub with notes).
If the same plugin was also uploaded to your claude.ai plugin library, remove that copy: a
library copy loads as a session-only plugin and shadows the installed one.

## What it does

- **Extrapolates, not just rewrites.** Vague words become checkable criteria, gaps are filled, and
  everything inferred is listed under `ASSUMPTIONS:` so your words and its inferences stay apart.
  Readings that would change what gets built are marked `ASK FIRST`.
- **Loses nothing.** Every stated requirement survives. A deterministic check re-adds any exact
  token the brief dropped (paths, URLs, quoted strings, identifiers) under `KEEP VERBATIM`.
- **Never widens authority.** Destructive, outward-facing, costly or secret-touching actions stay
  confirm-first. Your project's own rules (CLAUDE.md, AGENTS.md) still win.
- **Goals:** `/goal <text>` becomes a verifiable completion condition, sized to what the goal is worth.
- **Agent briefs:** large prompts for the Agent tool, workflow agents and teammates are forged
  before the agent starts.
- **Visible in the chat:** a forged prompt is held, a one-line notice says so, and the brief is
  sent as the next message, so you see exactly what the agent receives (desktop app included).
  Your original wording stays in the record as a notice the model never reads. Prompts with
  images are rewritten in place instead.
- **Overrides:** start a prompt with `forge:` to force it, or `raw:` to skip it.
- **Skips** slash commands and harness-built prompts (`<system-reminder>`, forks, peer messages).
  A transient API error is retried once; if the forge still fails, or a prompt is over 24,000
  characters, your text goes through as typed and a notice says so.

Each forge is one Opus call (high effort), so a forged prompt takes a few seconds to a minute.

## Principles

- **Altitude, Depth, Range** from Felix Rieseberg,
  [How to be more ambitious](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/):
  outcomes over artifacts, verbs over nouns, expert methods and outside verification.
- **Karpathy guidelines** ([multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), MIT):
  think before coding, simplicity first, surgical changes, every step verified.
- **BMad Method** ([bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD), MIT):
  a right-sized Clarify, Plan or Build-and-verify track, with decisions recorded durably.

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
