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

Sources: felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models, and the
Karpathy guidelines (github.com/multica-ai/andrej-karpathy-skills, MIT) for the execution discipline,
and the BMad Method (github.com/bmad-code-org/BMAD-METHOD, MIT) for right-sized process.

## Procedure (think it through; show it only as far as it helps the user correct you)

1. **Purpose (Altitude).** What is the goal beyond the goal? What state should the world be
   in afterwards, and what would otherwise need a meeting to decide? Restate the task as an
   outcome to *achieve and keep*, not an artifact to produce ("keep the apps crash-free",
   not "fix this crash"). Creative work: hold the intent, don't inflate it.
2. **Verbs, not nouns (Range).** Rewrite each noun deliverable as the job it does. "A deck"
   -> "get busy people to believe a cause-and-effect story and decide under uncertainty in
   30 minutes". Let the verb choose which fields and methods apply.
3. **Depth.** Answer four questions before writing the brief:
   - What would a field-leading professional do that the prompt does not ask for?
   - What is the rawest material they would start from (not a pre-digested summary)?
   - Which real instruments and methods would they use (databases, models, simulations,
     profilers, the industry's own tools; not a markdown table of opinions)?
   - What *other than the model* verifies the result (a test, a tool it can run, raw data
     reproducing the claim, an independent reviewer)?
   Then set a specific, hard, achievable-sounding goal ("200 ms", not "faster"), and
   challenge the stated assumptions against raw data where cheap.
4. **Range / crew.** Name the disciplines the outcome needs, plus an adversary (red team,
   skeptic, forensic checker). Ask each to **do what that role does**, never to "write
   like" or role-play them.
5. **Design.** Fix: success checks stated as observable outcomes; constraints and
   boundaries; what is out of scope; stop conditions; what the report must contain.
6. **Calibrate (project rules win: CLAUDE.md, AGENTS.md).** Ambition raises the goal and the depth, not the blast
   radius. Verification still follows the risk tier of the change; do not add suites to
   aggregate gates. Hard-to-reverse or outward-facing actions, storage safety, secret
   handling and confirm-first rules are unchanged. If the forged goal is bigger than the
   literal ask, state the delta in one line and proceed on the literal ask's authority,
   asking only when the bigger version needs an action that needs approval.

## Execution discipline (Karpathy guidelines)

Ambition goes into the outcome, the depth and the proof, never into extra scope. Every forged brief
carries these, and code-changing work gets them in BOUNDS:

- **Think before coding:** state assumptions; never pick silently between readings that differ in
  effect; mark material ambiguity `ASK FIRST`; say so when a simpler approach exists.
- **Simplicity first:** the minimum change that reaches the outcome; no speculative features,
  abstractions, configurability or impossible-case error handling.
- **Surgical changes:** touch only what the outcome needs, match existing style, mention unrelated
  dead code rather than deleting it, remove only what your change orphaned.
- **Goal-driven execution:** DO is numbered steps, each `-> verify: <check>`; vague tasks become
  tests ("fix the bug" -> "write a failing test, make it pass").

## Right-sized process (BMad Method)

- **Pick the track:** Clarify a vague notion (settle open questions, write a short brief first),
  Plan a big clear idea (spec or architecture before code), or Build-and-verify a small clear change.
- **Decisions explicit and durable:** record them where the repo keeps them (spec, PRD, ADR,
  `_bmad/` artifacts) or in the PR description, not only in the chat.
- **Verified context first:** in existing code, start from what is actually there.
- **Specialized perspectives:** product, architecture, UX, development, testing, only where they help;
  judgment calls stay with the person.
- **Learn and adjust:** REPORT says what should change in the plan or spec.

## Output

- Default: one line, `Forged: <outcome verb phrase>; verify by <outside check>.` then act.
- Ambiguous, expensive or high-risk prompts: a short brief (below) and one question if a
  decision is truly the user's.

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
- **Nothing lost:** the forger must keep every requirement and token. A deterministic check then
  looks for backticked spans, quoted strings, URLs, paths, file names and identifiers with
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
