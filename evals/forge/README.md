# The forge's own tuning loop

A change to the forge's rules in `hooks/register.tsx` should make briefs better, not just
different. This eval is how you tell. It is the same loop engineering pattern the
[loop-engineering](https://github.com/CameronWeller/loop-engineering) repo uses, pointed at the
forge itself:

1. **A fixed set of prompts** (`prompts/`). Each one is a realistic loose prompt, marked with
   whether the forge should brief it or answer PASS, and whether it is risky. Eight are for
   training, meaning you can look at them while changing the rules. Four are held out, and you
   should never tune against them, so they show whether a change really generalizes.
2. **Forge every prompt twice:** once with the current rules (`--baseline`, default `HEAD`)
   and once with your working tree. Each call is the same isolated, tool-less Opus call the
   plugin makes.
3. **A judge from another model family grades each brief** against `rubric.md`. By default
   that's Codex (`codex exec`), so the forge is never graded by its own family. The rubric
   covers seven things, scored 0 to 2: outcome, checkable, verify, loop, authority, assumptions
   and fidelity. Free deterministic checks run alongside it: was PASS called correctly, are the
   required sections there, and did any exact tokens get dropped.
4. **The decision.** The change may ship only if no prompt gets a new hard failure (a wrong
   PASS call, or the judge finding the brief widened authority), and the held-out score is not
   lower than the baseline. The report gives the standard error, so you can see when a
   difference is just noise.

```bash
node evals/forge/run.mjs                      # working tree vs HEAD, judged by Codex
node evals/forge/run.mjs --baseline v0.5.0    # against a release
node evals/forge/run.mjs --judge claude       # if Codex isn't installed (same family: weaker check)
node evals/forge/run.mjs --only 03,12         # a quick look at a few prompts
node --test evals/forge/run.test.mjs                    # the eval's own unit tests (no model calls)
```

The script exits 0 when the change may ship, and 1 when it may not. Reports go to
`evals/forge/results/`, which git ignores. A full run makes 24 forge calls plus up to 18 judge
calls, which takes about 20 to 40 minutes.

**Where proposals come from.** loop-engineering's weekly tuning loop reads how forged briefs
did in real runs. That covers which assumptions proved wrong, and which review rejections
trace back to a gap in the brief. It proposes rule changes here as PRs. Each of those PRs
includes this eval's report. When a real failure shows a pattern the prompt set doesn't
cover, add a prompt for it. Put new prompts in the training split, and keep the held-out set
as it is.
