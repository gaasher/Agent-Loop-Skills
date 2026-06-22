---
name: power-analysis
description: >
  Use when the user is planning a two-arm comparison (an A/B test, a simple RCT, a behavioral study, or
  a two-model/two-config evaluation) and needs to size it and preregister it before collecting data —
  finding the per-group sample size that hits target statistical power for the smallest effect worth
  detecting, auditing the design against a validity checklist, and locking it in a preregistration.
  Only for a single two-arm comparison with one primary outcome. Not for factorial, repeated-measures,
  clustered/multilevel, time-series, adaptive, or survival designs; not for analyzing data already
  collected; not for choosing the outcome or manipulation from domain knowledge.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Power Analysis Loop

A **power-analysis-and-preregister** loop for a **two-arm comparison**. The artifact is the study's
statistical plan; the feedback signal is two parts — **statistical power** (estimated by Monte-Carlo
simulation of the planned test) and a **count of validity flaws**. Each iteration simulates power,
solves for the sample size that reaches the target, audits the design for flaws, and revises — until
power clears the target **and** the flaw list is empty. The deliverable is a sample-size justification
plus a preregistration that pins the hypothesis, primary outcome, analysis, sample size, and stopping
rule before any data is seen.

## Scope & limitations
This loop does exactly three things, in a loop: **(1)** computes power and required sample size for a
**two-group comparison** by simulation, **(2)** runs a fixed **validity checklist** over the design,
and **(3)** writes a **preregistration**. The vendored power model (`tools/power_sim.py`) covers
**two-sample mean** (continuous outcome) and **two-proportion** (binary outcome) tests only.

It is **not** a general experiment designer. It does **not** handle factorial, repeated-measures,
clustered/multilevel, time-series, adaptive, or survival designs; it does **not** pick your outcome
measure or manipulation from domain knowledge; and it does **not** analyze data you have already
collected. For those, the power numbers here do not apply — use a design-appropriate power method. If
the study is not a simple two-arm comparison, say so and stop rather than reporting a power that does
not match the planned analysis.

## When to use
Use this to size and preregister one two-arm comparison whose primary outcome is a continuous mean or a
binary rate. Default to powering for the **minimal effect of interest** the user states; if they are
unsure of that effect, help them set it from a baseline and a smallest-meaningful difference rather than
an optimistic guess — a design "powered" for an effect bigger than reality is a fiction. If the study is
not a two-arm comparison, stop and point to a design-appropriate method.

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<hypothesis>` | the claim the experiment tests | — | ask the user |
| `<outcome>` | primary outcome type + minimal effect of interest: continuous (`baseline_mean`, `sd`, `min_effect`) **or** binary (`baseline_rate`, `min_lift`) | — | ask; this fixes the effect size power is computed at |
| `<target_power>` | power the design must clear | `0.80` | — |
| `<alpha>` | significance level | `0.05` | — |
| `<power_cmd>` | invocation of the vendored simulator | `python3 <skill_dir>/tools/power_sim.py --design <two-sample-mean\|two-proportion> --effect <e> [--sd <sd> \| --baseline <p0>] --alpha <alpha> --n <n_per_group>` | — |
| `<design_doc>` | output design + preregistration file | `<sandbox_root>/design.md` | — |
| `<sandbox_root>` | where design + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |

`<power_cmd>` prints one JSON object, `{"power", "n_per_group", ...}`. **Run** it to get the power; never
estimate power by hand.

## The loop
Copy this checklist and tick items off:
- [ ] Iteration 0 — draft the design to `<design_doc>`; record nothing as final.
- [ ] **Simulate** power: run `<power_cmd>` at the current `n` and the assumed effect.
- [ ] **Solve N**: if power `< <target_power>`, re-run at larger `n` (step up, then bisect) until it clears.
- [ ] **Audit validity**: list every flaw from the checklist below.
- [ ] **Revise**: fix the highest-priority flaw, set `n` to the power-adequate value, update `<design_doc>` (+ Preregistration section).
- [ ] Append a ledger row; stop when power clears the target **and** no flaws remain, or at `<budget>`.

**Iteration 0 — draft.** Write a first design to `<design_doc>`: the arms/conditions, the unit of
analysis and how units are assigned, the primary outcome and the exact planned test, the assumed effect
size (from `<outcome>`), and a first sample-size guess. Record nothing as final yet.

**Then, until stop (power met + no flaws, or budget):**

1. **Simulate power.** Run `<power_cmd>` at the current per-group `n` and the assumed effect, with the
   `--design` matching the planned test. Record the achieved power.
2. **Solve N.** If `power < <target_power>`, re-run the simulation at larger `n` — step up (e.g. double),
   then bisect — until power clears the target, and adopt that `n`.
3. **Audit validity.** Check the design against the checklist and list every flaw found:
   - **Confounding / no control** — is there a concurrent control group, or is the comparison against a
     historical/other-source baseline that differs in other ways?
   - **Randomization** — are units randomly assigned? If not, selection bias threatens any effect.
   - **Selection / sampling** — is the sample representative of the population the claim is about?
   - **Multiple comparisons** — more than one outcome/subgroup tested without correction?
   - **Optional stopping / peeking** — is there a pre-specified stopping rule, or will analysis run
     repeatedly until significant?
   - **Outcome & analysis pre-specification** — are the primary outcome and its single planned test
     fixed in advance (not chosen after seeing data)?
   - **Measurement** — is the outcome measured reliably and blind to condition where possible?
4. **Revise.** Fix the highest-priority flaw (or a tightly-coupled pair that cannot be fixed
   independently, such as adding a concurrent control and randomizing assignment to it) and set `n` to
   the power-adequate value. Update `<design_doc>`, including a **Preregistration** section: hypothesis,
   primary outcome, the one planned analysis, sample size + how it was derived, randomization scheme, and
   the stopping rule.
5. **Log** one ledger row and continue.

**Stop** when `power ≥ <target_power>` **and** the flaw list is empty, or at `<budget>`. Report the
final design + preregistration, the achieved power and required `n`, and — if stopping on budget — the
flaws still outstanding.

## Ledger
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
Report the **best** iteration: the final design, the achieved power and required `n`, and any flaws
still open if stopping on budget.

## Constraints
- **Power is computed at the minimal effect of interest**, not an optimistic one, because a design
  powered for an effect bigger than reality detects nothing real — and the `--design` in the simulation
  must match the test named in the design. Do not edit `tools/power_sim.py`.
- **A design does not pass on power alone** — an adequately powered but confounded or non-randomized
  design still fails; both gates (power and flaws) must clear.
- **Preregister before data**, so the eventual test is confirmatory rather than chosen after seeing
  results: the analysis, outcome, sample size, and stopping rule are fixed in advance.
- **One primary outcome and one planned test** drive the power and the verdict; secondary analyses are
  labeled exploratory.
- The sandbox is self-contained — no `../` escapes. Do not pause the loop to ask whether to continue.
