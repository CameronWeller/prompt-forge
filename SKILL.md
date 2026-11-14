---
name: prompt-forge
description: Manual reference for the prompt-forge mod, which forges the first prompt of a session, large prompts and every /goal you send into outcome-focused briefs behind an isolated model call. Built on Felix Rieseberg's "How to be more ambitious", the Karpathy guidelines and the BMad Method.
disable-model-invocation: true
---

# Prompt forge

Applies when it matters most, and only to what you personally send: the **first prompt of a
session**, any **large prompt** (50+ words), and **every goal you set with `/goal`**. Do the forge
first, then act. Everything else runs as typed, with no delay. In a prompt you type: start it with
`forge:` to force a full brief, or `raw:` to skip the forge (the prefix is removed). A typed prompt
that is already simple and clear passes through exactly as typed: one plausible reading, a named
or obvious target, a checkable "done", no vague qualifier, one deliverable or a question, and
nothing destructive, outward-facing, irreversible, costly or secret-touching. Judge by meaning,
never length; when unsure, write the brief.

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
  `Allowed:` is local, reversible work plus exactly the outward actions the input names (push, PR,
  CI or paid runs, deploy, rollback, production data and messages are outward); no conditional
  grants ("if a runbook says"); DO and STOP never do what BOUNDS forbids; no part of a secret shown.
  A named action covers only itself ("push to prod" is not its migrations); irreversible local work
  (schema or data changes on a real database, deleting untracked files) is confirm-first; writing a
  step into the plan is not confirmation; no command whose output could print a secret.
  Project rules (CLAUDE.md, AGENTS.md) win.
- **Keep material whole.** The agent never sees the input, so GIVEN quotes in full what it must work
  from. Text above a `//PROMPT FORGE:` line reaches the agent byte for byte, after the brief.

**Altitude (the purpose)**
- **Start from what is given.** GIVEN states the exact starting state and materials, then the job in
  one sentence.
- **Verbs, not nouns, first.** Rewrite each deliverable as the job it does ("a deck" -> "get busy
  people to believe a cause-and-effect story and decide under uncertainty in 30 minutes"), then
  extrapolate from the verbs.
- **The goal beyond the goal.** An outcome to achieve and keep, not an artifact ("keep the apps
  crash-free", not "fix this crash"); the inferred purpose goes in WHY, marked "(inferred)".
  Creative work: hold the intent, don't inflate it.
- **Vague words become checkable criteria.** Solutions beyond the literal ask are welcome and
  listed in ASSUMPTIONS.
- **Say what counts.** SCOPE gives examples in and out of scope, names the tempting shortcuts that
  satisfy the words and miss the purpose, and marks limits that tooling enforces or could.
- **Right-sized track:** Clarify a vague notion, Plan a big clear idea, or Build-and-verify a small
  clear change; record decisions where they outlive the chat (spec, PRD, ADR, `_bmad/`, PR).

**Depth (work like a field-leading expert)**
- What would a field-leading professional do that the prompt does not ask for?
- RESOURCES inventories the tools, data, schemas and hard limits the input gives. Costly runs get a
  finite budget, marked "(inferred)", to plan before spending.
- Start from the rawest material (in existing code, what is actually there) and use the field's
  real tools, not a markdown table of opinions.
- DO is numbered steps, each `-> verify: <check>` ("fix the bug" -> "write a failing test, make it pass").
- Challenge the stated assumptions against raw data where cheap.
- **Diagnose first:** categorize failures, read raw failing examples, go after the largest category
  you can explain.
- **Show cause:** correlation is not enough. Name the confound and show that changing the suspected
  cause changes the behaviour as predicted, at several strengths where that applies.
- **Long work:** state each step's hypothesis, print compact summaries, keep notes that survive a
  restart, keep copies of the best result, and warn about output that could get a session refused.
- VERIFY names a judge other than the model and a specific hard goal ("200 ms", not "faster").
- **A loop, not a script:** each DO step is try, check, and on failure the exact error feeds the next
  try; never repeat an attempt unchanged.
- **Measurable outcomes:** fix the protocol first; compare against an unchanged baseline on the same
  items; confirm on held-out items; state the standard error and the smallest effect that counts; use
  cheap dense signals beside costly ones. Name the proxy that could mislead, and judge by the outcome.
- BOUNDS is written as `Not allowed:` and `Allowed:` lists.
- Leave out whatever does not apply rather than padding it.

**Range (draw on several fields)**
- CREW draws widely: product, architecture, UX, design, development, testing, security, data and
  statistics, operations, accessibility, legal and compliance, finance, the domain expert, the end
  user, analyst, journalist, editor, motion and audio design, or any other field that helps, plus
  an adversary (red team, skeptic, short seller, forensic accountant or checker). Each does what
  that role does, never role-play.

**Loop (how the work stops)**
- STOP sets `Done when:` (the VERIFY checks that mean success), `Attempts:` (a cap per approach,
  default 3, and a total of 2 approaches before handing back), `Budget:` (time, runs or money where costly, "(inferred)" unless given) and
  `Hand back when:` (the same failure twice, an ASK FIRST reading met mid-work, a BOUNDS limit in the
  way, the budget spent). A stop is a result; REPORT says which condition ended the run.

**Report**
- How the work runs and ends: when it is finished, what gets handed over, and any exact reply format.
- With several steps, a few plain sentences before each: what the last result showed, what it
  concludes, what comes next and why, and what would confirm or refute the hypothesis.
- At the end: what was done, what was skipped and why, which assumptions held, and what should adjust the
  plan or spec.

## What the mod does (isolated from the primary agent)

The raw prompt goes to a tool-less Opus call that has no history and no tools. The primary
agent receives **only the forged brief**, never the raw text and never this
skill (it is hidden from the model; `/prompt-forge` is for you).

- **User prompts:** forged on the first prompt of every session (also after `/clear`, so every
  new chat) and on any prompt of 50+ words. Your prompt is held; the chat shows "Forging your prompt…", then the full forged prompt (printed by the companion plugin `prompt-forge-view`, since the desktop app draws command output but not plugin notices), then the brief is sent as the next message; your original wording stays in the record as a notice the model never reads. Prompts with images are rewritten in place instead. Only prompts the engine stamps as yours are forged (typed at the prompt, the desktop app included; Remote Control; Slack): `claude -p` runs, the app's own events, schedules, task notices, other sessions and plugins pass untouched with no model call. A `<system-reminder>` the app attaches to your message reaches the agent intact and is not counted as your words. A status line shows "forging…"
  while it runs (up to a minute or two). Skipped: slash commands, first prompts under four words, prompts over 24k
  characters, bash-mode lines. A simple, clear request (the forge answers PASS) shows "Not forged: a simple, clear
  request" and is sent exactly as typed. `forge:` forces a full brief, `raw:` skips the forge (prefix removed).
- **Goals (`/goal <text>`):** always forged, whatever the size, into one verifiable completion
  condition of whatever length the goal is worth (the evaluator checks it against the conversation): an
  outcome to reach and keep, vague words turned into thresholds, the proving evidence named
  (command and exit code, test result, measured number). `Goal set:` shows the
  condition. `/goal clear` and the like pass through; `raw:` sets your wording as typed.
- **Agent briefs are never forged:** a model wrote them, and they hold data the agent needs.
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
GIVEN: <exact starting state and materials, then the job in one sentence>
OUTCOME: <state of the world to achieve, as a verb phrase>
WHY: <the goal beyond the goal; what the result unblocks>
TRACK: <Clarify | Plan | Build-and-verify, why, and where decisions are recorded>
SCOPE: <what counts, what does not, tempting shortcuts, limits tooling enforces>
RESOURCES: <tools, data, schemas, hard limits, a finite budget where runs are costly>
DO: <verbs a top practitioner would do, with rawest inputs and real tools/paths; try, check, retry with the exact error>
CREW: <disciplines/adversary to apply, as actions>
VERIFY: <outside check: command, test, data, independent reviewer; exit codes expected>
STOP: <Done when / Attempts / Budget / Hand back when: the loop the agent runs and how it ends>
BOUNDS: <Not allowed and Allowed lists: limits, risk tier, files not to touch>
ASSUMPTIONS: <what was inferred rather than stated; report where one proved wrong>
REPORT: <what to return, how short; what was skipped and why>
```

Never hand an agent your conclusion to confirm; hand it the raw material and the question.
