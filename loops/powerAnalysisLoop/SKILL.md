---
name: power-analysis-loop
description: >
  Use when the user is planning a two-arm comparison (an A/B test, a simple RCT, a behavioral study, or
  a two-model/two-config evaluation) and needs to run a proper power analysis before collecting data:
  find the per-group sample size that gives adequate statistical power to detect the smallest effect
  worth detecting, check the design against a validity checklist, and lock it in a preregistration.
  Each iteration simulates the planned test to estimate power, solves for the required sample size,
  audits the design for validity flaws, and revises — until power clears the target and no flaws remain.
  Bind it to your hypothesis, the minimal effect of interest, and a power command at setup.
metadata:
  version: "0.1.0"
---

# Power Analysis Loop

A **power-analysis-and-preregister** loop for a **two-arm comparison**. The artifact is the study's
statistical plan; the feedback signal is two parts: **statistical power** (estimated by Monte-Carlo
simulation of the planned test) and a **count of validity flaws**. Each iteration you simulate power,
solve for the sample size that reaches the target, audit the design for flaws, and revise — until power
clears the target **and** the flaw list is empty. The deliverable is a sample-size justification plus a
preregistration that pins the hypothesis, primary outcome, analysis, sample size, and stopping rule
before any data is seen.

## Scope & limitations (read this — be honest about what it does)
This loop does exactly three things, in a loop: **(1)** computes power and required sample size for a
**two-group comparison** by simulation, **(2)** runs a fixed **validity checklist** over the design, and
**(3)** writes a **preregistration**. The vendored power model covers **two-sample mean** (continuous
outcome) and **two-proportion** (binary outcome) tests only.

It is **not** a general experiment designer. It does **not** handle factorial, repeated-measures,
clustered/multilevel, time-series, adaptive, or survival designs; it does **not** pick your outcome
measure or manipulation from domain knowledge; and it does **not** analyze data you have already
collected. For those, the power numbers here do not apply — use a design-appropriate power method. If
the user's study is not a simple two-arm comparison, say so and stop rather than reporting a power that
does not match the planned analysis.

The power signal comes from `tools/power_sim.py` (vendored, stdlib): given an assumed effect size and a
per-group sample size, it simulates the experiment many times and returns the fraction that reach
significance. **Power is computed under the effect size the user cares about — the minimal effect worth
detecting — not an inflated guess; a design "powered" for an effect bigger than reality is a fiction.**

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm the values in one line, and skip to §2. Otherwise
resolve each binding, then write `loop.run.yaml` so re-runs are non-interactive.

**Detect host:** if `AskUserQuestion` is available you are in **Claude Code** — infer a likely value
and present it as the recommended option. Otherwise ask each as a quoted plain-text prompt.

- **`<hypothesis>`** — the claim the experiment tests (e.g. "the new tutorial raises quiz scores").
- **`<outcome>`** — the primary outcome's type and the **minimal effect of interest**: for a continuous
  outcome, the baseline mean, the SD, and the smallest meaningful difference; for a proportion, the
  baseline rate and the smallest meaningful lift. This fixes the effect size power is computed at.
- **`<target_power>`** (default 0.80), **`<alpha>`** (default 0.05).
- **`<power_cmd>`** — default
  `python3 <skill_dir>/tools/power_sim.py --design <two-sample-mean|two-proportion> --effect <e> [--sd <sd> | --baseline <p0>] --alpha <alpha> --n <n_per_group>`.
  It prints `{power, n_per_group, ...}`.
- **`<design_doc>`** — the output design + preregistration file (default `<sandbox_root>/design.md`).
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8 iterations).

**The run schema.** These resolved bindings are written to `<sandbox_root>/loop.run.yaml` so re-runs are
non-interactive. See **`schema.example.yaml`** (next to this skill) for the exact shape and field
comments; the user can also fill that template in by hand and point the loop at it to skip the
interactive questions.

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` already existed). Then initialise the ledger (§3) and start.

---

## 2. The loop

**Iteration 0 — draft.** Write a first design to `<design_doc>`: the arms/conditions, the unit of
analysis and how units are assigned, the primary outcome and the exact planned test, the assumed effect
size (from `<outcome>`), and a first sample-size guess. Record nothing as final yet.

**Then, until stop (power met + no flaws, or budget):**

1. **Power.** Run `<power_cmd>` at the current per-group `n` and the assumed effect. If `power <
   <target_power>`, **solve for n**: re-run the simulation at larger `n` (step up, e.g. double then
   bisect) until power clears the target, and adopt that `n`. Record the achieved power.
2. **Flaw audit.** Check the design against the validity checklist and list every flaw found:
   - **Confounding / no control** — is there a concurrent control group, or is the comparison against a
     historical/other-source baseline that differs in other ways?
   - **Randomization** — are units randomly assigned? If not, selection bias threatens any effect.
   - **Selection / sampling** — is the sample representative of the population the claim is about?
   - **Multiple comparisons** — more than one outcome/subgroup tested without correction?
   - **Optional stopping / peeking** — is there a pre-specified stopping rule, or will analysis run
     repeatedly until significant?
   - **Outcome & analysis pre-specification** — is the primary outcome and its single planned test
     fixed in advance (not chosen after seeing data)?
   - **Measurement** — is the outcome measured reliably and blind to condition where possible?
3. **Revise.** Fix the highest-priority flaw (or a tightly-coupled pair that cannot be fixed
   independently, such as adding a concurrent control and randomizing assignment to it) and set `n` to
   the power-adequate value. Update
   `<design_doc>`, including a **Preregistration** section: hypothesis, primary outcome, the one planned
   analysis, sample size + how it was derived, randomization scheme, and the stopping rule.
4. **Log** one ledger row (§3) and continue.

**Stop** when `power ≥ <target_power>` **and** the flaw list is empty, or at `<budget>`. Report the
final design + preregistration, the achieved power and required `n`, and — if stopping on budget — the
flaws still outstanding.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	n_per_group	power	open_flaws	change
```
Example:
```
iter	n_per_group	power	open_flaws	change
0	50	0.50	2	draft: volunteers vs last-year cohort, n=50
1	100	0.80	1	solved n for 80% power at d=0.4
2	100	0.80	0	randomized concurrent control; pre-specified single primary outcome + stopping rule
```

---

## 4. Hard constraints
- **Power is computed at the minimal effect of interest**, not an optimistic one — and the planned test
  in the simulation must match the test named in the design. Do not edit `tools/power_sim.py`.
- **A design does not pass on power alone** — an adequately powered but confounded or non-randomized
  design still fails; both gates must clear.
- **Preregister before data.** The design's analysis, outcome, sample size, and stopping rule are fixed
  in advance, so the eventual test is confirmatory rather than chosen after seeing results.
- **One primary outcome and one planned test** drive the power and the verdict; secondary analyses are
  labeled exploratory.
- The sandbox is self-contained — no `../` escapes. Do not pause the loop to ask whether to continue.
