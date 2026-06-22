---
name: claim-verify
description: >
  Use when the user has a results draft or a set of data-backed claims and wants each one
  adversarially verified against the underlying dataset before publishing — a pre-publication
  red-team of the findings. Extracts the discrete checkable claims from the draft, reproduces each
  claim's number against the data, stress-tests it against the threats most likely to kill it
  (outliers, confounds, Simpson's reversals, tiny subgroups, alternative specifications), and marks
  it verified, fragile, or refuted; fragile and refuted claims are revised — hedged, scoped, or
  retracted — until every claim is verified or appropriately qualified. The result is a draft where
  every surviving claim has been reproduced and survived a stress test. Not for open-ended discovery
  of new findings over a dataset (that is a data-analysis task), and not for diagnosing a single known
  anomaly or pipeline failure — this is a gate over an existing draft.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Claim Verify Loop

A **claim-by-claim adversarial verification** loop over a results draft. The artifact is the draft;
the feedback signal is the count of **unverified claims** — claims not yet checked, or checked but not
yet survived a stress test. You drive it to zero: each claim ends **verified** (reproduces and
survives the obvious threats) or **appropriately qualified** (hedged, scoped, or retracted with the
reason).

The discipline: a number that merely reproduces is not trustworthy — most wrong findings reproduce
fine. A claim is verified only when it also **survives the threat most likely to kill it**: an
outlier, a confound, a subgroup too small to mean anything, a sign that flips under stratification.
This loop is a *gate on an existing draft*, not a generator of new findings.

## When to use

Use this when you have a draft (or a list of claims) drawn from a dataset and want each claim
red-teamed before it goes out. Default to verifying every discrete claim in the draft; if the user
flags a few high-stakes claims, prioritize those but still sweep the rest. Not for open-ended
discovery of new findings (that is the `data-analysis` loop) and not for diagnosing one known anomaly.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<draft>` | results/claims document to verify (markdown/text) | — | scan the working dir for a results/report file |
| `<dataset>` | data the claims were drawn from; read-only ground truth | — | scan the working dir for the data file |
| `<analysis_cmd>` | interpreter that runs check snippets in the user's env | `python3` | `pyproject.toml`/`.venv`/`uv` in the working dir |
| `<report>` | the verified/revised draft this loop produces | `<sandbox_root>/verified.md` | — |
| `<sandbox_root>` | where check snippets + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 10 | — |

Check snippets run in the **user's environment** via `<analysis_cmd>`, so they may use whatever the
user has installed. Keep helper code **stdlib-first** (`csv`, `statistics`): if a snippet needs
`pandas`/`numpy`, probe with `try/except ImportError` and degrade to a stdlib path, or offer a
consented `uv pip install "pandas==<ver>"` — never assume the package is installed.

## The loop

Copy this checklist and tick items off:
- [ ] Iteration 0 — extract the discrete checkable claims from `<draft>`; record nothing as verified.
- [ ] Pick one unverified claim.
- [ ] Reproduce its exact number from `<dataset>`; if it does not reproduce → `refuted`.
- [ ] Stress-test against the threat(s) most likely to kill it; classify `verified` / `fragile`.
- [ ] Revise `<report>`: keep verified, hedge/scope/retract fragile, correct refuted.
- [ ] Append a ledger row; the claim leaves the unverified set. Stop when none remain or at `<budget>`.

**Iteration 0 — extract claims.** Read `<draft>` and list its discrete, checkable claims, each with
the number/effect it asserts and its **claim type** (a group difference, a correlation, a
causal/policy claim, a subgroup result, a rate). These are the live unverified set. If the draft is
prose, splitting it into discrete claims is the first job.

**Then, until stop (all claims resolved, or budget):**

1. **Pick one unverified claim.**
2. **Reproduce — the first gate.** Write `<sandbox_root>/iter<N>/check.py` to recompute the exact
   statistic the claim states from `<dataset>`. Run it with `<analysis_cmd>`, redirecting output to
   `<sandbox_root>/iter<N>/out.txt` (never flood your context). If the number does not reproduce →
   **refuted** (the number is wrong); skip to step 4.
3. **Stress-test — the second gate.** Hit the claim with the one or two threats most likely to kill it
   for its claim type:
   - **Outlier sensitivity** — recompute dropping extreme points / using a robust statistic. Does the
     effect survive, or was it driven by a handful of rows?
   - **Confound & Simpson's reversal** — stratify by the obvious confounder; does the effect hold
     within strata, or flip? A causal/policy claim that reverses within subgroups is **not** supported.
   - **Subgroup size & multiplicity** — how large is the subgroup? Is the result one of many
     comparisons? A striking rate on n=5 is noise.
   - **Alternative specification** — a defensible different cut (different bins, controlling for a
     covariate). Does the sign/size stay?

   Classify: **verified** (reproduces and survives) or **fragile** (reproduces but collapses or flips
   under a reasonable stress). A claim whose **number reproduces but whose implied interpretation is
   not supported** — a descriptive gap dressed up as causal ("treatment works"), a tiny-n rate sold as
   "superior", a one-point correlation called an "early-warning signal" — is **fragile**, not
   verified: the statistic is fine, the conclusion drawn from it is not.
4. **Revise the draft.** Update `<report>`:
   - **verified** → keep the claim, noting the robustness check it passed.
   - **fragile** → **hedge, scope, or down-weight** it to what the data supports (e.g. "descriptively
     higher, but the within-stratum comparison reverses — not evidence the treatment causes
     recovery"), or retract it. Never leave a fragile claim standing as first written.
   - **refuted** → correct it with the right number, or remove it.
   Record the verdict and the evidence.
5. **Log** one ledger row and continue; the claim leaves the unverified set.

## Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	claim	verdict	threat	resolution
```
`verdict` ∈ {`extract`, `verified`, `fragile`, `refuted`}. Example:
```
iter	claim	verdict	threat	resolution
0	claims extracted	extract	-	7 claims listed
1	treatment recovery rate > control (70.6 vs 55.0)	verified	reproduced; holds	kept
2	treatment causes higher recovery (+16pp)	fragile	Simpson: control >= treatment within both age groups	rescoped to descriptive; causal claim retracted
3	biomarker correlates with recovery_days (r=0.16)	fragile	one outlier drives it (r=0.16 -> 0.02 without it)	retracted
5	pilot site 100% recovery (superior)	fragile	n=5 subgroup	hedged: too small to conclude
```
Report the **outcome**: the `<report>` path, the per-claim verdicts, and a summary — how many claims
were verified, hedged, or retracted, and the single most important fragility found.

## Constraints
- **Reproduce *and* stress-test — both.** A claim that only reproduces is not verified; it must
  survive the threat most likely to kill it. Skipping the stress test is the failure mode this loop
  exists to prevent.
- **Every verdict is backed by a re-run** recorded in `<report>`; no claim is waved through or
  condemned on intuition.
- **A fragile claim is changed, never left standing** — hedge it to what the data supports or retract
  it, because leaving it as first written is exactly what shipped the unverified draft.
- **Distinguish description from causation** — "treatment arm recovered more" can be true while
  "treatment causes recovery" is refuted by a confound; say exactly what the data supports.
- **Only read `<dataset>`** — never modify it, because it is the ground truth every claim is checked
  against. The sandbox is self-contained (no `../` escapes).
- One claim per iteration, so each verdict is attributable.
- Do not pause the loop to ask whether to continue; run until all claims are resolved or `<budget>`.

## Stops
- **Resolved** — no unverified or unresolved-fragile claims remain.
- **Budget** — `<budget>` iterations reached.
