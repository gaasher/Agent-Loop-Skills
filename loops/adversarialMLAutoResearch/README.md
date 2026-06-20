# adversarialMLAutoResearch

**Competing ideas, judged in a tournament — and a judge that learns to pick winners.**

Each iteration, `<n>` research agents each propose **one** architecture change. A **Judge**
critiques them against a [rubric](rubric.md), the agents refine, and the Judge ranks and picks
the **single** change to run. Everything else works like
[`standardMLAutoresearch`](../standardMLAutoresearch) — analysis-first, one change per run,
keep-or-revert against `<metric>`.

What makes it adversarial — and self-improving:

- **Propose → critique → refine → decide.** `<n>` agents propose; the Judge scores and
  critiques; the agents refine once (default) by choosing to *double down*, *run more analysis*,
  *refine*, or *pivot*; the Judge then selects the top idea. Losing ideas don't get implemented,
  but their suggested **analysis steps** are folded in to sharpen evaluation.
- **The Judge is the orchestrator.** It spawns the proposers (spawn-or-degrade), runs the
  standard experiment, and decides — no merging, exactly one change per iteration.
- **The Judge learns to judge.** It logs a *predicted* outcome for each pick and compares it to
  the *realized* metric delta (`calibration.tsv`), distills lessons (`judge_lessons.md`), and
  **self-refines the rubric's weights and anchor descriptors** from what actually paid off. Its
  own **selection hit-rate** is a metric it tries to improve.

## How the rubric works

Ideas are judged on three orthogonal axes — **grounding** (is it aimed at the diagnosed
problem?), **expected impact** (how big is the upside?), and **feasibility & cost** — plus a
**falsifiability gate** (every proposal must state a checkable signal). The ranking is decided
by **de-biased pairwise comparison** (more reliable than absolute scores); per-axis pointwise
scores are kept only as the learning signal. The method is grounded in the LLM-as-a-judge
literature — see [`rubric.md`](rubric.md) for the criteria, anchors, and citations.

## Files

| File | Role |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The program — setup + the tournament loop. |
| [`roles/Judge.md`](roles/Judge.md) | The Judge/orchestrator behavior. |
| [`roles/ResearchAgent.md`](roles/ResearchAgent.md) | The proposer role (spawned `<n>`× per round). |
| [`rubric.md`](rubric.md) | Scoring criteria + the self-refinement protocol. |
| [`schemas/idea.schema.json`](schemas/idea.schema.json) | What an agent returns (one proposed change). |
| [`schemas/verdict.schema.json`](schemas/verdict.schema.json) | What the Judge records per idea (scores, rank, decision). |
| [`schema.example.yaml`](schema.example.yaml) | Example resolved bindings. |

## Best for

Problems with many plausible directions, where pitting ideas against each other (and a judge
that gets calibrated to *this* project) beats a single agent's first guess. For a single-agent
analysis loop, use [`standardMLAutoresearch`](../standardMLAutoresearch).
