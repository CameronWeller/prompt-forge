---
name: prompt-forge
description: Manual reference for the prompt-forge mod, which forges the first prompt of a session, large prompts, large agent briefs and every /goal into outcome-focused briefs behind an isolated model call. Built on Felix Rieseberg's "How to be more ambitious", the Karpathy guidelines and the BMad Method.
disable-model-invocation: true
---

# Prompt forge

Applies when it matters most, not to every prompt: the **first prompt of a session**, any
**large prompt** (50+ words), and any **large agent brief**, and **every goal you set with `/goal`**. Do the forge first, then
act. Everything else runs as typed, with no delay. In a prompt you type: start it with
`forge:` to force the forge on a short one, or `raw:` to skip it (the prefix is removed).

Sources: felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models supplies the
structure (Altitude, Depth, Range). The Karpathy guidelines (github.com/multica-ai/andrej-karpathy-skills,
MIT) and the BMad Method (github.com/bmad-code-org/BMAD-METHOD, MIT) are folded into it.

## Method (Rieseberg's Altitude, Depth and Range, with Karpathy and BMad folded in)

**Ground rules (always)**
- **Mark what is yours.** ASSUMPTIONS lists each inference, each reading with a different effect
  (never picked silently; say which you chose), and `ASK FIRST` on any reading that changes what
  gets built. Say so when a better or simpler approach exists. Never invent paths, tools or facts.
- **Never widen authority.** Nothing destructive, outward-facing, irreversible, costly or
  secret-touching that the input did not authorize; approval-gated actions stay confirm-first.
  Project rules (CLAUDE.md, AGENTS.md) win.

**Altitude (the purpose)**
- **Verbs, not nouns, first.** Rewrite each deliverable as the job it does ("a deck" -> "get busy
  people to believe a cause-and-effect story and decide under uncertainty in 30 minutes"), then
  extrapolate from the verbs.
- **The goal beyond the goal.** An outcome to achieve and keep, not an artifact ("keep the apps
  crash-free", not "fix this crash"); the inferred purpose goes in WHY, marked "(inferred)".
  Creative work: hold the intent, don't inflate it.
- **Vague words become checkable criteria.** Solutions beyond the literal ask are welcome and
  listed in ASSUMPTIONS.
- **Right-sized track:** Clarify a vague notion, Plan a big clear idea, or Build-and-verify a small
  clear change; record decisions where they outlive the chat (spec, PRD, ADR, `_bmad/`, PR).

**Depth (work like a field-leading expert)**
- What would a field-leading professional do that the prompt does not ask for?
- Start from the rawest material (in existing code, what is actually there) and use the field's
  real tools, not a markdown table of opinions.
- DO is numbered steps, each `-> verify: <check>` ("fix the bug" -> "write a failing test, make it pass").
- Challenge the stated assumptions against raw data where cheap.
- VERIFY names a judge other than the model and a specific hard goal ("200 ms", not "faster").

**Range (draw on several fields)**
- CREW draws widely: product, architecture, UX, design, development, testing, security, data and
  statistics, operations, accessibility, legal and compliance, finance, the domain expert, the end
  user, analyst, journalist, editor, motion and audio design, or any other field that helps, plus
  an adversary (red team, skeptic, short seller, forensic accountant or checker). Each does what
  that role does, never role-play.

**Report**
- What was done, what was skipped and why, which assumptions held, and what should adjust the
  plan or spec.

## What the mod does (isolated from the primary agent)

The raw prompt goes to a tool-less Opus call that has no history and no tools. The primary
agent (or worker agent) receives **only the forged brief**, never the raw text and never this
skill (it is hidden from the model; `/prompt-forge` is for you).

- **User prompts:** forged on the first prompt of every session (also after `/clear`, so every
  new chat) and on any prompt of 50+ words. Your prompt is held and the brief is sent as the next message, so the chat (desktop app included) shows exactly what the agent receives; your original wording stays in the record as a notice the model never reads. Prompts with images are rewritten in place instead. Agent briefs get a notice with the forged brief. Prompts the harness wraps in `<system-reminder>` and similar tags (session briefs, forks, peer messages) are never forged. A status line shows "forging…"
  while it runs (up to a minute or two). Skipped: slash commands, first prompts under four words, prompts over 24k
  characters. `forge:` forces a short prompt, `raw:` skips the forge (prefix removed).
- **Goals (`/goal <text>`):** always forged, whatever the size, into one verifiable completion
  condition of whatever length the goal is worth (the evaluator checks it against the conversation): an
  outcome to reach and keep, vague words turned into thresholds, the proving evidence named
  (command and exit code, test result, measured number). `Goal set:` shows the
  condition. `/goal clear` and the like pass through; `raw:` sets your wording as typed.
- **Large agent briefs** (Agent tool, workflow `agent()`, teammates): rewritten the same way
  before the agent starts. Skipped: small briefs, forks, resumes, and briefs that already
  contain a line starting `OUTCOME:`.
- **Extrapolates, not just rewrites:** the forger acts as a guard against loose language. It infers
  the intended outcome, turns vague words into checkable criteria, fills gaps and adds implied
  requirements, and lists everything it inferred under `ASSUMPTIONS:` so stated and inferred stay
  apart. It never widens authority: destructive, outward-facing, costly or secret-touching
  actions stay confirm-first. It briefs the task; it does not answer it.
- **Exact tokens kept:** a deterministic check looks for backticked spans, quoted strings, URLs, paths, file names and identifiers with
  digits from the original; any the brief dropped are appended under `KEEP VERBATIM`. Prose
  prohibitions rely on the forger's BOUNDS rule, not on the check.
- A transient API error is retried once. If the forge still fails, returns malformed text, or the
  prompt is over 24,000 characters, the raw prompt goes through and a notice says so.

```
OUTCOME: <state of the world to achieve, as a verb phrase>
WHY: <the goal beyond the goal; what the result unblocks>
TRACK: <Clarify | Plan | Build-and-verify, why, and where decisions are recorded>
DO: <verbs a top practitioner would do, with rawest inputs and real tools/paths>
CREW: <disciplines/adversary to apply, as actions>
VERIFY: <outside check: command, test, data, independent reviewer; exit codes expected>
BOUNDS: <scope limits, forbidden actions, risk tier, files not to touch>
ASSUMPTIONS: <what was inferred rather than stated; report where one proved wrong>
REPORT: <what to return, how short; what was skipped and why>
```

Never hand an agent your conclusion to confirm; hand it the raw material and the question.
