---
name: analysis-verify-loop
description: >
  Use when the user has a results draft or a set of claims drawn from data and wants each one
  adversarially verified before it goes out — a pre-publication red-team of the findings. Each
  iteration takes one claim, reproduces its number, then stress-tests it against the obvious threats
  (outliers, confounds and Simpson's reversals, tiny subgroups, alternative specifications), and marks
  it verified, fragile, or refuted; fragile and refuted claims are revised — hedged, scoped, or
  retracted — until every claim is verified or appropriately qualified. Bind it to your draft and the
  dataset at setup.
metadata:
  version: "0.1.0"
---

# Analysis Verify Loop

A **claim-by-claim adversarial verification** loop. The artifact is a results draft; the feedback
signal is the number of **unverified claims** — claims that either have not been checked or have not yet
survived a stress test. You drive it to zero: every claim ends up **verified** (reproduces and survives
the obvious threats) or **appropriately qualified** (hedged, scoped, or retracted with the reason).

The discipline: a number that merely reproduces is not yet trustworthy — most wrong findings reproduce
fine. A claim is verified only when it also **survives the threat most likely to kill it**: an outlier,
a confound, a subgroup too small to mean anything, a flipped sign under stratification. This loop is a
*gate on an existing draft*, not a generator of new findings.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm in one line, and skip to §2. Otherwise resolve each
binding, then write `loop.run.yaml`. **Detect host:** `AskUserQuestion` available → Claude Code (infer
+ recommend); else ask as quoted plain-text prompts.

- **`<draft>`** — the results/claims document to verify (markdown/text). Each claim should be a
  checkable statement; if the draft is prose, your first job is to split it into discrete claims.
- **`<dataset>`** — the data the claims were drawn from. Read-only ground truth.
- **`<analysis_cmd>`** — interpreter for checks (default `python3`; stdlib `csv`/`statistics` preferred;
  degrade gracefully if `pandas` is missing).
- **`<report>`** — the verified/revised draft (default `<sandbox_root>/verified.md`).
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 10 iterations).

**The run schema.** These resolved bindings are written to `<sandbox_root>/loop.run.yaml` so re-runs are
non-interactive. See **`schema.example.yaml`** (next to this skill) for the exact shape and field
comments; the user can also fill that template in by hand and point the loop at it to skip the
interactive questions.

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` existed). Then extract the claims (§2 iteration 0) and initialise the ledger (§3).

---

## 2. The loop

**Iteration 0 — extract claims.** Read `<draft>` and list its discrete, checkable claims, each with the
number/effect it asserts and its **claim type** (a group difference, a correlation, a causal/policy
claim, a subgroup result, a rate). These are the live unverified set.

**Then, until stop (all claims resolved, or budget):**

1. **Pick one unverified claim.**
2. **Reproduce.** Write `<sandbox_root>/iter<N>/check.py` to recompute the exact statistic the claim
   states from `<dataset>`. Run it (redirect output to `iter<N>/out.txt`). If it does not reproduce →
   **refuted** (the number is wrong); go to step 4.
3. **Stress-test against the threat that fits the claim type** (do the one or two most likely to kill it):
   - **Outlier sensitivity** — recompute dropping extreme points / using a robust statistic. Does the
     effect survive, or was it driven by a handful of rows?
   - **Confound & Simpson's reversal** — stratify by the obvious confounder; does the effect hold within
     strata, or flip? A causal/policy claim that reverses within subgroups is **not** supported.
   - **Subgroup size & multiplicity** — how large is the subgroup? Is the result one of many comparisons?
     A striking rate on n=5 is noise.
   - **Alternative specification** — a defensible different cut (different bins, controlling for a
     covariate). Does the sign/size stay?
   Classify: **verified** (reproduces and survives) or **fragile** (reproduces but collapses/flips under
   a reasonable stress). A claim whose **number reproduces but whose implied interpretation is not
   supported** — a descriptive gap dressed up as causal ("treatment works"), a tiny-n rate sold as
   "superior", a one-point correlation called an "early-warning signal" — is **fragile**, not verified:
   the statistic is fine, the conclusion drawn from it is not. Rescope it to what the data supports.
4. **Revise the draft.** Update `<report>`:
   - **verified** → keep the claim, noting the robustness check it passed.
   - **fragile** → **hedge, scope, or down-weight** it to what the data supports (e.g. "descriptively
     higher, but the within-stratum comparison reverses — not evidence the treatment causes recovery"),
     or retract it. Never leave a fragile claim standing as first written.
   - **refuted** → correct or remove it, with the corrected number.
   Record the verdict and the evidence.
5. **Log** one ledger row (§3); the claim leaves the unverified set. Continue.

**Stop** when no unverified or unresolved-fragile claims remain, or at `<budget>`. Report `<report>`
(the cleaned draft), the per-claim verdicts, and a summary: how many claims were verified, hedged, or
retracted, and the single most important fragility found.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	claim	verdict	threat	resolution
```
`verdict` ∈ {`extract`, `verified`, `fragile`, `refuted`}. Example:
```
iter	claim	verdict	threat	resolution
1	treatment recovery rate > control (70.6 vs 55.0)	verified	reproduced; holds	kept
2	treatment causes higher recovery (+16pp)	fragile	Simpson: control >= treatment within both age groups	rescoped to descriptive; causal claim retracted
3	biomarker correlates with recovery_days (r=0.16)	fragile	one outlier drives it (r=0.16 -> 0.02 without it)	retracted
5	pilot site 100% recovery (superior)	fragile	n=5 subgroup	hedged: too small to conclude
```

---

## 4. Hard constraints
- **Reproduce *and* stress-test — both.** A claim that only reproduces is not verified; it must survive
  the threat most likely to kill it. Skipping the stress test is the failure mode this loop exists to prevent.
- **Every verdict is backed by a re-run** recorded in `<report>`; no claim is waved through or condemned
  on intuition.
- **A fragile claim is changed, never left standing** — hedge it to what the data supports or retract it.
- **Distinguish description from causation** — "treatment arm recovered more" can be true while
  "treatment causes recovery" is refuted by a confound; say exactly what the data supports.
- **Only read `<dataset>`** — never modify it. The sandbox is self-contained (no `../` escapes).
- Do not pause the loop to ask whether to continue; run until all claims are resolved or the budget is hit.
