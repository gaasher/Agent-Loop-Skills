---
name: prompt-optimize
description: >
  Use when the user has a prompt that feeds a system they can already score, and wants that prompt
  automatically improved to raise the score against their own evaluation command. Makes one targeted
  quality edit per iteration — clarity, context, specificity, structure, examples, decomposition,
  guardrails — re-runs the user's eval to measure the metric, and keeps the edit only if the metric
  improves, else reverts; loops to a target, plateau, or budget. The metric is whatever the user's
  eval command prints (task accuracy, an LLM-judge score, a pass rate, a tool-call success rate); the
  loop is metric-agnostic and never edits the eval. Not for writing a prompt from scratch, not for
  tuning model weights or hyperparameters, and not for one-off manual prompt edits without a score.
metadata:
  version: "0.1.0"
---

# Prompt Optimize Loop

An **evolutionary optimizer for a prompt** (OpenEvolve / AlphaEvolve-style). The artifact is a prompt
that feeds the user's system; the feedback signal is a **scalar metric printed by the user's own
evaluation command**. Each iteration proposes one quality-focused edit, re-runs the eval, and keeps
the edit only if the metric improves — evolving the prompt toward higher scores. The eval is a
black-box oracle the loop runs but never edits, so the optimization tracks what actually matters
rather than gaming a number.

## When to use

Use this when the user has a prompt and a command that scores the system using it, and wants the
prompt improved to raise that score. Default to diagnosing the prompt's biggest current weakness each
round and applying the one operator that addresses it; if the eval feedback points elsewhere, follow
the feedback. Not for authoring a prompt from nothing, tuning weights/hyperparameters, or making a
single manual edit with no score to compare against.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<prompt_file>` | the prompt to optimize — the artifact the loop evolves | — | scan the working dir for the prompt/template file the eval reads |
| `<eval_cmd>` | **required.** Command that scores the current `<prompt_file>`; prints the metric (see output convention below). Treated as a black box — never edited | — | ask the user; look for `eval`/`score`/`bench` scripts |
| `<objective>` | `maximize` or `minimize`, plus one line on what the metric measures | `maximize` | ask the user |
| `<target>` | optional score at which to stop early | — | ask the user; else leave unbound |
| `<sandbox_root>` | where prompt snapshots + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 10 | — |
| `<patience>` | stop after N consecutive non-improving iterations (plateau) | 3 | — |

**Eval output convention.** `<eval_cmd>` must print, on its **last line**, either a JSON object
`{"score": <number>, "feedback": "<optional notes/errors>", ...any extra metrics...}` or a bare
number. Higher is better unless `<objective>` is `minimize`. The `feedback` field, when present, is
the richest signal — read it like AlphaEvolve's artifacts side-channel to decide the next edit.

**Eval runs in the user's environment.** `<eval_cmd>` may call an inference endpoint or any tooling the
user has installed; the loop just shells out and reads the last line. If instead the prompt is executed
by *you* (interactive development with no separate endpoint), first run the current prompt over the
user's eval inputs to produce outputs, write them where `<eval_cmd>` reads, then run `<eval_cmd>` to
score them.

## The loop

Copy this checklist and tick items off:
- [ ] Iteration 0 — baseline: run `<eval_cmd>` on `<prompt_file>`, record its score as the current best, snapshot the prompt.
- [ ] Diagnose the prompt's single biggest weakness from the latest score, the eval feedback, and the history.
- [ ] Apply one targeted edit (one operator from the toolkit) to `<prompt_file>`.
- [ ] Measure: re-run `<eval_cmd>` and read the new score from its last line.
- [ ] Keep if the metric improves (require a margin if the eval is stochastic), else revert to the best snapshot.
- [ ] Append a ledger row; if stuck, branch from an earlier high-scoring variant; stop on `<target>`, plateau (`<patience>`), or `<budget>`.

**Iteration 0 — baseline.** Run `<eval_cmd>`, record its score as the best, snapshot `<prompt_file>`
to `<sandbox_root>/iter0/`, and start the history (`{iter, edit, score, feedback}` per row).

**Then, until stop (target, plateau, or budget):**

1. **Diagnose.** From the latest score, the `<eval_cmd>` feedback, and recent history, name the
   prompt's single biggest current weakness — the one thing most likely holding the metric back.
2. **Make one targeted edit** — pick the toolkit operator that addresses that weakness:
   - **Clarity** — remove ambiguity, contradictions, and vague wording.
   - **Context** — supply missing domain knowledge, definitions, or background the task needs.
   - **Specificity** — make instructions concrete; pin down the output format; define what "good" is.
   - **Structure** — order the prompt into steps/sections; add a short checklist.
   - **Examples** — add one or two demonstrations of the desired input → output.
   - **Decomposition** — split a complex instruction into explicit ordered sub-steps.
   - **Guardrails** — state edge cases and what to avoid.

   One change per iteration, so its effect on the metric is attributable.
3. **Measure.** Snapshot the edited prompt to `<sandbox_root>/iter<N>/`, run `<eval_cmd>`, and read the
   new score off the last line.
4. **Keep or revert.** **Keep** if the metric improves per `<objective>` (if the eval is stochastic,
   require a small margin so noise alone does not drive a keep); otherwise **revert** `<prompt_file>`
   to the previous best snapshot. Append `{edit, score, feedback}` to the history either way.
5. **Escape local optima.** If the score has not improved for a couple of iterations, stop making tiny
   tweaks — branch from an earlier high-scoring snapshot, or try a bolder restructuring (a different
   decomposition, a fresh set of examples). Diversity beats grinding the same local hill.

When stopping, restore the **best** prompt to `<prompt_file>` and report the score trajectory, which
edits moved the metric (and which did not), and the final prompt.

## Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	score	status	edit
```
`status` ∈ {`baseline`, `keep`, `revert`}. Example (metric = task accuracy, maximize):
```
iter	score	status	edit
0	0.42	baseline	original prompt
1	0.61	keep	specificity: define each output label and the exact output format
2	0.61	revert	examples: add 3 few-shot demos — no metric gain
3	0.78	keep	context: add the domain rules the task assumes but never states
```
Report the **best** iteration, not necessarily the last.

## Constraints
- **The metric is the user's.** Never edit `<eval_cmd>`, its data, or its scoring — that games the
  number instead of improving the prompt, and the eval is the only ground truth the loop has.
- **Optimize the prompt only, and preserve the task's intent.** Improve *how* the task is instructed,
  not *what* is being asked; do not tailor the prompt to exploit eval quirks that would break real use.
- **One edit per iteration**, and compare the *metric* by re-running the full `<eval_cmd>`, not a single
  sample, so each score delta is attributable to that one edit.
- **Report the best variant, not the last.** The sandbox is self-contained — no `../` escapes.
- Do not pause the loop to ask whether to continue; run until target, plateau, or budget.

## Stops
- **Target** — the score reaches `<target>` (if set).
- **Plateau** — no iteration improved the best for `<patience>` consecutive rounds (every non-improving
  iteration counts toward patience; a keep resets it).
- **Budget** — `<budget>` iterations reached.
