# highTemperatureMLAutoresearch

**A mono-agent ML research loop that forces wide exploration before converging.**

Runs hot — prioritising diverse, full-rewrite swings over incremental refinement.
The "temperature" is highest at the start and the scheduling rules enforce variety:
if the loop has been making only small exploit steps for too long, it is forced to
pivot back to a big swing or a merge.

## How the scheduling works

The loop moves through three phases:

**Phase 0 — Baseline (iteration 1 only)**
Run the code unmodified to establish a score to beat. This does not count as a swing.

**Phase 1 — Forced exploration**
For the first `<swing_budget>` iterations (after the baseline), every step must be a
full swing. No tweaks, no refinements — each attempt must be a fundamentally different
approach.

**Phase 2 — Adaptive**
Once `<swing_budget>` swings are done, the agent chooses freely each iteration:
- **swing** — try something completely different again
- **merge** — combine strengths from two previous approaches in `approaches.md`
- **exploit** — make a targeted, analysis-driven improvement to the current best

One hard guardrail applies: if the agent has chosen exploit `<stagnation_limit>` times
in a row without a swing or merge in between, exploit is taken off the table and it
must swing or merge. This prevents the loop from quietly hill-climbing forever.

The two thresholds (`<swing_budget>` and `<stagnation_limit>`) are set by the user at
setup time.

## What's the same as standardMLAutoresearch

- Same mandatory analysis phase after every run (scripts in `iter<N>/analysis/`,
  outputs in `iter<N>/results/`).
- Same setup questions (metric, env, editable files, sandbox, gate/budget).
- Same simplicity criterion and NEVER STOP rules.
- Same sandbox layout per iteration.

## What's new

- Two extra setup questions: `<swing_budget>` and `<stagnation_limit>`.
- `approaches.md` — a persistent registry of every distinct approach tried, with
  strengths/weaknesses from the analysis. The merge step reads this directly.
- `move_type` column in `results.tsv`.
- Hard scheduling constraint in the loop body (not a suggestion).

## Per-iteration sandbox layout

```
<sandbox_root>/
├── schema.yaml
├── results.tsv           # includes move_type column
├── approaches.md         # registry; updated on swing and merge iterations
└── iter<N>/
    ├── schema.yaml
    ├── code_snapshot/
    ├── run.log
    ├── analysis/
    └── results/
```

## Files

| File | Role |
| --- | --- |
| `SKILL.md` | The full loop program. |
| `schema.example.yaml` | Copy to `schema.yaml` and fill in, or answer interactively. |
