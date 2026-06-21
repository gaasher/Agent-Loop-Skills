# lazyAlphaEvolve

**Evolve an ML model the way AlphaEvolve evolves code — a simplified, agent-harness re-creation.**

## What this is

A loop that evolves a *population* of model variants. The "program" is your model's editable code
(`model.py`/`config.yaml`); a **child** is one LLM-proposed **SEARCH/REPLACE diff** to a parent,
scored by a **training run**, and stored in a **MAP-Elites archive across islands** so diverse
high-performers survive instead of collapsing to one peak. It is a deliberately **simplified
("lazy")**, **ML-bent** re-creation of [AlphaEvolve](https://arxiv.org/abs/2506.13131) and its
open-source implementation [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve),
running on an agent harness with **bounded parallelism**.

## How it works

A finite controller loop (you = the controller):

1. **Sample** a parent program + a few "inspiration" programs from an island's archive.
2. **Mutate**: a Mutator proposes one analysis-grounded SEARCH/REPLACE diff to the parent (using the
   parent's artifacts — `<metric>`, per-class accuracy, loss curve), in its own sandbox.
3. **Evaluate (cascade)**: a cheap smoke run gates which children earn a full training run.
4. **Place**: compute the child's niche (complexity × diversity) and keep it as that cell's elite if
   it scores best.
5. **Migrate** top elites between islands periodically; **checkpoint** the archive each generation.

Each generation evaluates exactly `C` children in parallel (`C` from a mandatory hardware probe), for
`num_generations = total_budget / C` — so the whole run is finite and countable. You set just **two
values** (`total_budget`, `concurrency`); everything else has faithful defaults behind an optional
"advanced" branch.

## Similar to AlphaEvolve / OpenEvolve

- **MAP-Elites + island populations** with periodic **ring migration**.
- **parent + inspirations** sampled from the archive (improve-and-inspire), fed into the prompt.
- **SEARCH/REPLACE diffs** as the mutation operator (full rewrite for tiny files).
- **Evaluation cascade**: small-scale smoke filter → full evaluation; scalar metric maximized.
- **Artifacts feedback**: a program's run output (errors, per-class results) informs the next diff.
- **Diversity** = average edit-distance to a reference sample; **adaptive normalization** of axes;
  **seeded + checkpointed** (the archive/history are the resumable checkpoint).
- AlphaEvolve's own Figure 3 evolves a supervised-learning pipeline — the ML bent matches a paper example.

## Different — the ML bent

- The **program** is an ML model's editable code; the **evaluator `h`** is a **training run** that
  reports `<metric>` plus ML artifacts (per-class accuracy, loss curve), not a generic code benchmark.
- **complexity axis = trainable param count (log-scaled)**, not source-character length — a one-line
  config edit can 10× the model, so params are the meaningful "size."

## Simplifications (why it's "lazy")

1. **Single LLM** (the harness model), not AlphaEvolve's Gemini Flash + Pro ensemble.
2. **Bounded, generational, small population** (ML training is expensive) vs OpenEvolve's large async
   pool (pop ~500, 100s–1000s of iterations).
3. **2-stage cascade** (smoke → full), not an arbitrary N-stage cascade.
4. **Metric-only fitness** (+ artifacts); no separate LLM-graded scores.
5. The controller is a **Markdown spec executed by the agent** — determinism is best-effort (seed +
   explicit selection rules), and diffs are applied by the agent editing files, not a compiled engine.

## Files

| File | Role |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The controller — setup + the finite generational algorithm. |
| [`roles/Mutator.md`](roles/Mutator.md) | Produces + cascade-evaluates one child (the generation step). |
| [`schemas/result.schema.json`](schemas/result.schema.json) | The child result a Mutator returns. |
| [`schema.example.yaml`](schema.example.yaml) | Example bindings + the 2 core knobs (+ advanced defaults). |

## Citations

- A. Novikov et al., **"AlphaEvolve: A coding agent for scientific and algorithmic discovery,"** 2025,
  [arXiv:2506.13131](https://arxiv.org/abs/2506.13131).
- **OpenEvolve** — open-source AlphaEvolve implementation,
  [github.com/algorithmicsuperintelligence/openevolve](https://github.com/algorithmicsuperintelligence/openevolve).

For a single-agent analysis loop, see [`standardMLAutoresearch`](../standardMLAutoresearch).
