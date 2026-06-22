# Idea-judging rubric

How the Judge scores and ranks competing ideas. This file ships the **defaults**; at setup
the loop copies it to `<sandbox_root>/rubric.active.md`, and the Judge self-refines **that
working copy** (never this one).

## Method (why it's built this way)

- **Pairwise decides the rank; pointwise only learns.** The Judge ranks ideas by **de-biased
  pairwise comparison** (compare each pair in *both* orders, keep only verdicts that agree),
  not by an absolute weighted score. LLM judges are markedly more reliable at relative than
  absolute judgments, and pairwise/rubric scoring carries strong position bias that the
  both-orders rule cancels. Anchored **pointwise 0–5 per-axis scores are recorded as the
  learning signal only** (calibration + weight/anchor refinement) — they never set the rank,
  because mixing pointwise and pairwise to decide produces contradictions (an idea scored 8
  can lose to one scored 7). Use chain-of-thought before scoring; fill the schema fields last.
  *(Inspired by: [LLM-as-a-judge survey](https://www.sciencedirect.com/science/article/pii/S2666675825004564);
  ["Am I More Pointwise or Pairwise?" — position bias](https://arxiv.org/abs/2602.02219);
  [G-Eval — anchored criteria + CoT + form-filling](https://arxiv.org/abs/2303.16634).)*
- **Outcome-grounded, not confidence-grounded.** A-priori idea scores predict execution
  outcomes poorly (the "ideation–execution gap"), so the rubric is tuned by **realized metric
  deltas**, not by how good an idea sounded. *(Inspired by:
  [Si/Yang/Hashimoto 2024](https://arxiv.org/pdf/2409.04109) + its ideation–execution-gap
  follow-up.)*
- **Self-refining weights AND anchors** over time. *(Inspired by RubricEval / Prometheus, via
  the survey above.)*
- **Falsifiability gate (pre-scoring):** an idea whose `prediction` is missing or untestable is
  **rejected before it is scored**. This also guarantees the
  calibration loop always has something measurable.
- **Novelty is deliberately NOT an axis.** LLM judges over-rate novelty and it does not
  predict execution success — rewarding it would chase shiny-but-unproven ideas.

The weights below are **priors that bias the holistic pairwise comparison** (which axis should
win a close call), not coefficients of a sum. They self-refine from outcomes.

## The three axes (score each 0–5)

Default weights: **grounding 0.40 · impact 0.35 · feasibility 0.25** (mild analysis-first
prior; the loop tunes these).

### 1. Grounding — *is it aimed at the right problem?*
How tightly the change targets a **specific, current** finding in the latest analysis about
**this** model's bottleneck, and whether it is consistent with history.
- **5** — names the exact analysis file + value/pattern and directly attacks the diagnosed bottleneck.
- **3** — plausibly related to the analysis, but the link is loose or generic.
- **1** — a generic "try X" with no real tie to the diagnostics.
- **0** — contradicts the evidence, or repeats a change already logged `discard`/`crash` in `results.tsv` with no reason it would differ now.

### 2. Expected impact — *how big is the upside?*
Plausible **magnitude** of `<metric>` gain given remaining headroom.
- **5** — addresses a primary bottleneck; large, credible gain.
- **3** — a real but modest improvement.
- **1** — marginal tweak; gain likely within noise.
- **0** — no plausible mechanism for improvement.

### 3. Feasibility & cost — *how cheaply and safely can we get the win?*
Likelihood it runs cleanly within `<editable_files>` + `<budget>` without crashing, plus its
complexity cost (simpler preferred — the standard simplicity criterion).
- **5** — small, self-contained, clearly within budget; low crash risk; simplifies or holds complexity.
- **3** — workable but adds moderate complexity or some risk.
- **1** — large/risky change, tight on budget, easy to break.
- **0** — needs a new dependency / out-of-scope files / cannot fit the budget.

## Scoring & ranking procedure (each round)
Record one verdict per idea (`schemas/verdict.schema.json`):
1. **Gate**: reject any idea failing the falsifiability gate.
2. **Pointwise** (learning signal): reason briefly per axis, then record 0–5 for grounding /
   impact / feasibility in the verdict's `scores`.
3. **Pairwise** (the decision): compare survivors head-to-head in **both orders**, keeping only
   consistent verdicts, weighting axes by the current priors; tally pairwise wins → the verdict's `rank`.
4. **Select** `rank == 1` (verdict `decision`); mark the rest `reject`. Log the Judge's predicted
   outcome for the selected idea to `calibration.tsv`.

## Self-refinement protocol (run at the calibration step, from realized outcomes)
- **Weights**: nudge toward axes whose pointwise scores correlated with realized gains and away
  from those that didn't — bounded and gradual (no swing > ~0.1/iteration; floor 0.1 so no axis
  is zeroed). Renormalize to sum 1.
- **Anchors**: when the calibration log shows an axis was systematically mis-scored (e.g.
  impact=5 picks underperformed), tighten that axis's descriptors in `rubric.active.md` and note
  the change.
- Record every refinement reason in `judge_lessons.md`. The shipped `rubric.md` is never edited.

> **Build-time check (do this when implementing):** re-read the cited sources and confirm this
> method (pairwise+de-bias decides · anchored pointwise learns · weights+anchors self-refine
> from outcomes · novelty excluded) still matches their recommendations; note any deliberate
> deviation here.
