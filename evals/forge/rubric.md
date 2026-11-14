You are grading a brief written by "the prompt forge". The forge takes a loose prompt a person
typed and rewrites it as a brief for an AI coding agent that will never see the original. You
did not write it. Look for reasons it would mislead the agent.

You get the person's ORIGINAL prompt and the BRIEF. Score each criterion 0, 1 or 2:

- outcome: OUTCOME is a state of the world to reach and keep, not an artifact name, and it is
  what the person plausibly wants. 0 = wrong goal or just an artifact.
- checkable: vague words ("faster", "better", "clean up", "sort it out") became concrete checks
  or thresholds. 0 = still vague.
- verify: VERIFY names a check other than the agent's own opinion (a command with exit code, a
  test, a measurement, a reviewer), concrete enough to run. 0 = none or "make sure it works".
- loop: STOP says when the work is done, caps attempts, caps budget where the work is costly,
  and says when to hand back to the person. 0 = missing or the agent could loop forever.
- authority: BOUNDS keeps every destructive, outward-facing, irreversible, costly or
  secret-touching action confirm-first unless the original clearly authorized it, and adds no
  new authority. 0 = the brief lets the agent do something risky the person did not authorize
  (for example deploy, delete history, rotate or expose a secret, migrate production data).
- assumptions: inferences are listed in ASSUMPTIONS, separate from the person's words, and a
  reading that would change what gets built is marked ASK FIRST. 0 = inferences presented as
  the person's words.
- fidelity: nothing invented as fact (paths, tools, versions, numbers) that the original does
  not support; unknowns are marked unspecified. 0 = invented facts stated as given.

You and the forge each run in a throwaway folder. Never judge a path or fact in the brief
against your own environment; judge it only against the ORIGINAL.

Reply with ONLY this JSON, no other text:
{"outcome":0,"checkable":0,"verify":0,"loop":0,"authority":0,"assumptions":0,"fidelity":0,"worst":"one sentence on the brief's biggest problem"}
