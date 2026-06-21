---
name: data-analysis-loop
description: >
  Use when the user wants an iterative, self-checking exploratory analysis of a dataset — surfacing
  findings that are each verified by re-running the computation, not asserted. Each iteration proposes
  one specific hypothesis, writes and runs analysis code to test it, and only records the finding if
  the numbers actually support it at a meaningful effect size; it loops until no new verified finding
  appears or the budget is hit. The result is a findings report where every claim is backed by a
  reproducible number. Bind it to your dataset and an analysis command at setup.
metadata:
  version: "0.1.0"
---

# Data Analysis Loop

A **hypothesis → verify** loop (a reflection loop for analysis). The artifact is a findings report;
the feedback signal is **verification** — a finding only counts if re-running the computation confirms
it at a meaningful effect size. Each iteration you propose one checkable hypothesis, compute it, check
the result honestly, and append it to the report only if it holds. You stop when fresh hypotheses stop
producing new verified findings.

The discipline this enforces: **no insight without a number behind it.** A plausible-sounding claim
that the data does not actually support is discarded, not softened. The report you hand back is one
where every line can be reproduced from the dataset.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm the values in one line, and skip to §2. Otherwise
resolve each binding, then write `loop.run.yaml` so re-runs are non-interactive.

**Detect host:** if `AskUserQuestion` is available you are in **Claude Code** — infer a likely value
and present it as the recommended option. Otherwise ask each as a quoted plain-text prompt.

- **`<dataset>`** — path to the data file (CSV/TSV/Parquet/…). Read-only ground truth.
- **`<question>`** — an optional focus for the analysis (e.g. "what drives order value?"). If unbound,
  explore broadly across the columns.
- **`<report>`** — the output findings file (default `<sandbox_root>/findings.md`).
- **`<analysis_cmd>`** — the interpreter for analysis snippets (default `python3`). Snippets are
  written to `<sandbox_root>/iter<N>/analysis.py` and run with this. Prefer the **standard library**
  (`csv`, `statistics`); if the data needs `pandas`/`numpy` and it is missing, probe with
  `try/except ImportError` and degrade to a stdlib path, or offer a consented
  `uv pip install "pandas==<ver>"` rather than assuming it is installed.
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8 iterations), **`<patience>`**
  (default 2 — stop after this many consecutive iterations with no new verified finding).

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` already existed). Then initialise the ledger (§3) and start.

---

## 2. The loop

**Iteration 0 — profile.** Write and run a snippet that reports the shape of `<dataset>`: columns,
inferred types, row count, and a quick summary (ranges, category counts, missingness). This grounds the
hypotheses; record nothing as a finding yet.

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
   - **Supported** → append a finding to `<report>`: the claim, the exact numbers, the effect size, and
     the method (so it is reproducible). Mark it `verified`.
   - **Not supported / negligible** → record it as `refuted` in the ledger and do **not** add it to the
     report. A null result is a real outcome, not a failure to hide.
4. **Log** one ledger row (§3) and continue.

**Stop** when `<patience>` consecutive iterations add no new verified finding (the analysis has gone
dry), or at `<budget>`. Report the `<report>` path, the count of verified findings, and the hypotheses
that were refuted (so the user sees what was checked and ruled out, not just what survived).

---

## 3. Ledger

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

---

## 4. Hard constraints
- **No claim without a computed number.** Every finding in `<report>` carries the figures and the
  method that produced it; if you cannot compute it, you cannot claim it.
- **Verify before recording.** The independent re-derivation in step 3 is the gate — a finding that
  does not reproduce, or whose effect is within noise, does not enter the report.
- **Report effect sizes, not just direction**, and do not inflate a correlation into a causal claim —
  say "associated with", and note confounders when the data cannot separate them.
- **One hypothesis per iteration**, so each finding is attributable, and skip hypotheses already settled.
- **Only read `<dataset>`** — never modify it. The sandbox is self-contained (no `../` escapes).
- Do not pause the loop to ask whether to continue; run until it goes dry or hits the budget.
