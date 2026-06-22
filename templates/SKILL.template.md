---
name: my-loop                     # == folder name; lowercase letters/numbers/hyphens; no claude/anthropic
description: >
  Use when the user wants to <trigger>. <One sentence: what the loop does + its feedback signal.>
  Each iteration <one change> → <measure signal> → keep/revert; loops to a plateau or budget.
  Not for <the confusable adjacent case>.
compatibility: Requires Python 3.9+   # optional — only if there is a real env requirement
metadata:
  version: "0.1.0"
---
# My Loop

One-to-two sentence overview: what the artifact is, what the feedback signal is, and the loop shape.
Assume the agent is smart — only state what it doesn't already know.

## When to use
Mirror the description's triggers. State one default approach and an escape hatch.

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it and skip to the loop. Otherwise:
on Claude Code infer a likely value per binding and recommend it via `AskUserQuestion`; on other hosts
ask each as a quoted prompt. Write `loop.run.yaml` and confirm before creating other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<artifact>` | the file(s) to improve | — | scan for the primary source file |
| `<run_cmd>` | run the artifact in the user's env | — | `pyproject.toml`/`.venv`/README |
| `<sandbox_root>` | where snapshots + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |
| `<patience>` | stop after N no-improvement iters | 3 | — |

Format: `examples/run.example.yaml`.

## Loop (until plateau or `<budget>`)
Copy this checklist and tick items off:
- [ ] Iteration 0 — baseline: run the signal, record it as the current best.
- [ ] Apply one focused change to `<artifact>`.
- [ ] Measure the signal (run the tool / `<run_cmd>`).
- [ ] Keep if it improves the best, else revert (snapshot restore).
- [ ] Append a ledger row; stop on plateau (`<patience>`) or `<budget>`.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text:
```
iter	signal	status	description
0	23	baseline	unmodified artifact
1	19	keep	<the change>
```
Report the **best** iteration, not necessarily the last.

## Constraints
- Only edit files in `<artifact>` — everything else is read-only ground truth.
- One change per iteration, so each signal delta is attributable.
- Do not add dependencies the project lacks; helper scripts stay stdlib-only.
- Do not pause the loop to ask whether to continue; run until plateau or budget.
