---
name: data-analysis
description: >
  Use when the user wants an iterative, self-checking exploratory analysis of a dataset — surfacing
  findings that are each verified by re-running the computation, not asserted. Proposes one specific
  hypothesis at a time, writes and runs analysis code to test it, and records the finding only if the
  numbers support it at a meaningful effect size; loops until no new verified finding appears or the
  budget is hit. The result is a findings report where every claim is backed by a reproducible number.
  Not for diagnosing a single known anomaly or pipeline failure, and not for verifying an external
  claim against sources (that is a claim-verification task) — this is open-ended discovery over a
  bound dataset.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Data Analysis Loop

A **hypothesis → verify** reflection loop over a dataset. The artifact is a findings report; the
feedback signal is **verification** — a finding only counts if re-running the computation confirms it
at a meaningful effect size. The discipline this enforces: **no insight without a number behind it.**
A plausible claim the data does not support is discarded, not softened; every line in the report can
be reproduced from the dataset.

## When to use

Use this for open-ended, self-checking exploration of a bound dataset where each finding must survive
an independent re-computation. Default to broad exploration across the columns; if the user gives a
focus question, let it steer the hypotheses. Not for diagnosing one known anomaly or for checking an
external claim against the literature.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<dataset>` | data file to analyze (CSV/TSV/Parquet/…); read-only ground truth | — | scan the working dir for a data file |
| `<question>` | optional analysis focus; omit to explore broadly | — | ask the user; else leave unbound |
| `<report>` | output findings file | `<sandbox_root>/findings.md` | — |
| `<analysis_cmd>` | interpreter that runs analysis snippets in the user's env | `python3` | `pyproject.toml`/`.venv`/`uv` in the working dir |
| `<sandbox_root>` | where snippets + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |
| `<patience>` | stop after N consecutive iters with no new verified finding | 2 | — |

Analysis snippets run in the **user's environment** via `<analysis_cmd>`, so they may use whatever the
user has installed. Keep helper code **stdlib-first** (`csv`, `statistics`): if a snippet needs
`pandas`/`numpy`, probe with `try/except ImportError` and degrade to a stdlib path, or offer a
consented `uv pip install "pandas==<ver>"` — never assume the package is installed.

## The loop

Copy this checklist and tick items off:
- [ ] Iteration 0 — profile `<dataset>` (shape, types, ranges, missingness); record nothing as a finding.
- [ ] Propose one specific, checkable hypothesis (steered by `<question>`; not already settled).
- [ ] Compute it: write `<sandbox_root>/iter<N>/analysis.py`, run with `<analysis_cmd>`, redirect to `out.txt`.
- [ ] Verify: re-derive the key number a second way; judge against a stated effect-size bar.
- [ ] Supported → append finding to `<report>` (`verified`); else log `refuted`, do not add it.
- [ ] Append a ledger row; stop on plateau (`<patience>`) or `<budget>`.

**Iteration 0 — profile.** Write and run a snippet that reports the shape of `<dataset>`: columns,
inferred types, row count, and a quick summary (ranges, category counts, missingness). This grounds
the hypotheses; record nothing as a finding yet.

**Then, until stop (dry or budget):**

1. **Propose one hypothesis.** A single, specific, checkable claim — e.g. "enterprise orders average
   higher value than consumer", "mobile has a higher return rate than other channels", "order value
   rises with signup tenure". Let `<question>` steer it; do not repeat a hypothesis already settled.
2. **Compute it.** Write `<sandbox_root>/iter<N>/analysis.py` that loads `<dataset>` and computes the
   relevant statistic **plus an effect size** (a group-mean difference, a rate gap, a correlation —
   not just a yes/no). Run it with `<analysis_cmd>`, redirecting output to
   `<sandbox_root>/iter<N>/out.txt` (never flood your context).
3. **Verify — the gate.** Re-derive the key number a second, independent way (a different grouping, a
   recount, or a sanity cross-check) and confirm the two agree. Then judge honestly: does the result
   **support the hypothesis at a meaningful effect size**, or is it negligible / within noise? Decide
   "meaningful" against a bar you state up front and apply consistently — a minimum effect size scaled
   to the group sizes and noise (e.g. roughly |Cohen's d| ≳ 0.2, risk ratio ≳ 1.5, or |r| ≳ 0.1,
   tightened when groups are small) — so the keep/refute threshold does not drift between iterations.
   - **Supported** → append a finding to `<report>`: the claim, the exact numbers, the effect size,
     and the method (so it is reproducible). Mark it `verified`.
   - **Not supported / negligible** → record it as `refuted` in the ledger and do **not** add it to
     the report. A null result is a real outcome, not a failure to hide.
4. **Log** one ledger row and continue.

## Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	hypothesis	effect	status
```
`status` ∈ {`profile`, `verified`, `refuted`}. Example:
```
iter	hypothesis	effect	status
0	dataset profile	-	profile
1	enterprise orders average higher value than consumer	185 vs 109 (+70%)	verified
2	returns differ by region	North 0.16 vs South 0.14 (negligible)	refuted
3	mobile has a higher return rate than web/store	0.30 vs 0.10	verified
```
Report the **best** outcome: the `<report>` path, the count of verified findings, and the hypotheses
refuted (so the user sees what was checked and ruled out, not just what survived).

## Constraints
- **No claim without a computed number.** Every finding in `<report>` carries the figures and the
  method that produced it; if you cannot compute it, you cannot claim it.
- **Verify before recording.** The independent re-derivation in step 3 is the gate — a finding that
  does not reproduce, or whose effect is within noise, does not enter the report.
- **Report effect sizes, not just direction**, and do not inflate a correlation into a causal claim —
  say "associated with", and note confounders when the data cannot separate them.
- **One hypothesis per iteration**, so each finding is attributable, and skip hypotheses already settled.
- **Only read `<dataset>`** — never modify it, because it is the ground truth every finding is checked
  against. The sandbox is self-contained (no `../` escapes).
- Do not pause the loop to ask whether to continue; run until it goes dry or hits the budget.

## Stops
- **Dry** — `<patience>` consecutive iterations add no new verified finding.
- **Budget** — `<budget>` iterations reached.
