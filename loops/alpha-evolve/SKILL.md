---
name: alpha-evolve
description: >
  Use when the user wants to evolve an ML model/program through population-based search rather than a
  single sequential refine loop — a generational evolution where parallel proposers each apply one
  small SEARCH/REPLACE diff to a parent, scored by a cascade-evaluated training run, and children are
  kept in a MAP-Elites archive across islands (with migration + checkpointing) so diverse high
  performers survive. A finite, bounded-parallelism re-creation of AlphaEvolve/OpenEvolve, bent for ML
  autoresearch. Runs to a fixed compute budget or until interrupted. Not for the sequential
  single-thread autoresearch loops (one change → measure → keep/revert), and not for verifying a known
  bug or external claim — this is parallel, diversity-preserving search over a program.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Alpha-Evolve

> Reference (read if you need the algorithm's details): AlphaEvolve — https://arxiv.org/abs/2506.13131 ·
> OpenEvolve (open-source impl) — https://github.com/algorithmicsuperintelligence/openevolve

A **population-based evolutionary** loop over a program. The artifact is the editable model code; a
**child** is one analysis-informed **SEARCH/REPLACE diff** to a parent, and the feedback signal is a
**cascade-evaluated training run** (`<metric>`, smoke→full). Children are placed in a **MAP-Elites
archive across islands** (complexity × diversity axes), so a child survives by being either better or
more novel, not just better. The discipline this enforces: **diversity is preserved, not collapsed** —
diverse high performers co-exist instead of one local optimum winning. You are the controller: sample
a parent + inspirations, spawn parallel Mutators to propose and evaluate children, place them, migrate
between islands, checkpoint. Loops to a fixed compute budget or until interrupted.

## When to use

Use this for parallel, diversity-preserving search over a model/program where many variants explore at
once and the archive keeps the illuminated frontier. Default to broad island coverage; if quality
stalls, bias selection toward exploiting top elites; if coverage stalls, bias toward empty cells. Not
for the sequential autoresearch loops (one change at a time), and not for fixing a known anomaly.

The cast (both in this folder): `roles/Mutator.md` produces + cascade-evaluates one child (the
generation step); `schemas/result.schema.json` is the result a Mutator returns.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available, `<host>` = `claude-code`) infer a likely value for each binding and present it as the
recommended option; on other hosts (`<host>` = `other`) ask each as a quoted plain-text prompt. Then
write `loop.run.yaml` (format: `examples/run.example.yaml`) and confirm the values before creating any
other files. `<host>` also decides execution: Claude Code spawns real `Agent` Mutators in parallel
(capped at `<concurrency>`); other hosts degrade to running a generation's children serially (identical
algorithm).

**Probe the box first (mandatory — measure, never assume `<concurrency>`).** Record and report:
- **CPU cores** → `<cores>`: `python3 -c "import os; print(os.cpu_count())"`.
- **RAM** → `<ram_gb>`: macOS `sysctl -n hw.memsize`; Linux `grep MemTotal /proc/meminfo`.
- **Accelerator** → `<accelerator>`/`<vram>`/`<gpu_count>`: `nvidia-smi --query-gpu=name,memory.total,count --format=csv` (NVIDIA); else macOS Apple GPU/MPS; else CPU-only.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` + `<metric_direction>` | scalar to optimize; min/maximize | — | ask; scan eval output for the reported metric |
| `<run_cmd>` / `<entrypoint>` | command for one training run (the evaluator) | — | `pyproject.toml`/`.venv`/`uv`/README |
| `<editable_files>` | the program being evolved (e.g. `model.py`, `config.yaml`); never the harness or data | — | ask explicitly — this is the code that gets mutated; do not default it (multi-select on Claude Code) |
| `<sandbox_root>` | where `lae/` is created | `./sandbox` | — |
| `<gate>` + `<budget>` | one full run's size: `time`/`epochs` + amount; the FIXED eval budget applied to every program | — | identify the duration key now (e.g. `train.epochs`) so the controller can override it |
| `<total_budget>` | total compute = number of full training runs (or wall-clock minutes); the single cost dial | — | ask |
| `<concurrency>` | parallel evaluations `C` | derived from the probe | CPU-only → `max(1, <cores>//4)`; single GPU/MPS → `1` (ask if more fit `<vram>`); multi-GPU → `<gpu_count>` (pin one child/GPU) |

`num_generations` is **derived**: `ceil(<total_budget> / <concurrency>)`. The cascade is **derived**
from `<budget>` (not asked): smoke = ~1 epoch / a small subset, full = `<budget>`, gate = child's
smoke `<metric>` ≥ parent's smoke. `<budget>`/`<metric>`/eval split are FIXED — never mutation targets
(a child may not "train longer" to look better); changing them means re-running the whole loop.

**Advanced (opt-in).** Ask one yes/no: "Use defaults for the evolutionary settings, or customize?"
Defaults are faithful to AlphaEvolve/OpenEvolve — use them and ask nothing more. Only on "customize"
ask for each (showing the default as recommended): `num_islands` (4), `num_top` (3), `num_diverse` (2),
`num_bins` (10), `migration_interval` (5), `diversity_reference_size` (10), `pop_per_island` (40),
`seed` (42). Axes are fixed: complexity × diversity. See `examples/run.example.yaml` for the shape.

Print the resolved bindings + the probe + derived `num_generations`, and **do not create files or
launch until the user confirms**. Then initialise the sandbox (header rows only; `programs/` is created
as children are evaluated):
```
<sandbox_root>/lae/
├── archive.tsv     ← current elites = program database + checkpoint
├── history.tsv     ← append-only record of every child
├── leaderboard.md  ← rendered UI
└── programs/       ← one self-contained dir per program
```

## The controller (loop)

You maintain `num_islands` MAP-Elites maps in `archive.tsv`, the append-only `history.tsv`, running
per-axis percentile stats, and `leaderboard.md`. **You are the sole writer of all shared logs** —
Mutators only return results, so there are no write races. Copy this checklist and tick items off:

- [ ] Setup done: probe recorded, bindings confirmed, sandbox initialised, `num_generations` derived.
- [ ] GEN 0 — in each island, create the baseline program (a copy of `<editable_files>`) + optionally a few stochastic variants; cascade-evaluate; place in the archive.
- [ ] Per generation: build EXACTLY `<concurrency>` tasks (round-robin island, seeded-rule parent, top `num_top` + `num_diverse` most-diverse inspirations); make each child dir by **copying** the parent program + harness.
- [ ] Run the `C` Mutators (spawn-or-degrade), each with `roles/Mutator.md`, parent code, inspirations, parent artifacts, its child dir, and the smoke/full budgets.
- [ ] For each returned child: append a `history.tsv` row; if `evaluated`, compute its niche → cell and place it in the island map iff `<metric>` is better (`kept=y`); record `smoke_dropped`/`crash` without placing.
- [ ] Re-render `leaderboard.md`; checkpoint (`archive.tsv` is the checkpoint); print a status line.
- [ ] Every `migration_interval` generations: ring-migrate top elites island k → k+1.
- [ ] Stop at `<total_budget>` (reserve a little for synthesis), then synthesize the final report.

**Niche computation (you do this, from a child's sandbox):**
- **`complexity`** = trainable param count (fallback: total LOC of the editable files **+ any files
  the child added**), **log10-scaled**.
- **`diversity`** = average normalized edit distance of the program's concatenated code (editable +
  added files) to a random sample of `diversity_reference_size` programs from its island (vs the
  baseline if the island is near-empty). Higher = more novel.
- Normalize each axis with **running ~5th/95th percentiles** (not raw min/max, so one outlier can't
  collapse the range): `scaled = clamp01((v − p5)/(p95 − p5))`; `bin = min(num_bins−1, int(scaled ×
  num_bins))`; `cell = (complexity_bin, diversity_bin)`. **Re-bin** existing elites when a percentile
  shifts enough to move an edge (keep the higher `<metric>` on collisions; the archive is small).

**The Mutator's prompt (the sampler):** parent code + inspirations + the parent's rendered artifacts
(`<metric>`, per-class accuracy, loss curve, stderr) + the instruction to return one SEARCH/REPLACE
diff. Single harness model — no LLM ensemble. The Mutator applies its diff in the child dir,
cascade-evaluates at the FIXED `<budget>` (the controller injects/caps the duration key on the run
command), and returns a result validated against `schemas/result.schema.json`:
```json
{"child_id": "g3-i1-a2", "parent_id": "g1-i1-a0", "approach_summary": "add BatchNorm after conv2",
 "sandbox_path": "<sandbox_root>/lae/programs/g3-i1-a2", "status": "evaluated",
 "smoke_metric": 0.61, "metric": 0.71}
```
`status` ∈ {`evaluated`, `smoke_dropped`, `crash`}; `metric` is null unless `evaluated`. Mutators
compute nothing about the archive — the controller derives every niche from the sandbox.

**Program sandboxes.** A parallel population doesn't map onto branches, so every program is a
self-contained, fully-runnable dir `<sandbox_root>/lae/programs/<child_id>/`; the archive references it
by id. Build each child dir by **copying real files** (the parent's `<editable_files>`, then apply the
diff, **plus the harness/entrypoint code it imports**) and evaluate from inside it
(`cd <child_dir> && <entrypoint>`). **Symlink only large read-only data**, never the entrypoint or any
imported `.py`: Python resolves a symlinked script's `__file__` to the link target, so `sys.path[0]`
becomes the original dir and the child's `model.py`/`dataset.py` are silently shadowed by the baselines
— every architecture/data mutation becomes a no-op (tell-tale: identical loss curves across different
"architectures"). **Isolation sanity gate:** the harness logs the param count / a code fingerprint;
flag any child whose code changed but whose metric/loss curve is identical to its parent's (shadowed),
and fix the sandbox before placing it. The repo working tree is never mutated.

**Final synthesis.** Report the global-best program + its `lae/programs/<id>/` path, the illuminated
complexity×diversity map (coverage + who won each region), per-island bests, and 2–3 notably diverse
runners-up.

## Ledger

All three logs live under `<sandbox_root>/lae/`, tab-separated, never commas in free text. The
controller is the sole writer; resume from `archive.tsv` + `history.tsv` if interrupted.

**`archive.tsv`** — current elites + checkpoint. Header
`island	cell	metric	child_id	parent_id	sandbox_path	complexity	diversity`:
```
island	cell	metric	child_id	parent_id	sandbox_path	complexity	diversity
0	(2,7)	0.7100	g4-i0-a1	g2-i0-a3	lae/programs/g4-i0-a1	2.1M	0.71
```
**`history.tsv`** — every child, append-only. Header
`gen	island	parent_id	child_id	smoke_metric	full_metric	status	kept	cell`:
```
gen	island	parent_id	child_id	smoke_metric	full_metric	status	kept	cell
4	0	g2-i0-a3	g4-i0-a1	0.61	0.71	evaluated	y	(2,7)
4	1	g2-i1-a0	g4-i1-a2	0.40	-	smoke_dropped	n	-
```
**`leaderboard.md`** — re-rendered each generation: global best + per-island coverage + the archive
ranked by `<metric>`. Report the **best** program at stop (not the last), the archive coverage, and a
few diverse runners-up. Leave `lae/` untracked.

## Constraints

- A child works **only inside its own `lae/programs/<child_id>/` dir** — it may edit the copied
  `<editable_files>` and create new files there, but never modify any file outside it (the repo, the
  read-only harness, the data, other programs' dirs are ground truth or shared state).
- **The controller is the sole writer** of `archive.tsv`/`history.tsv`/`leaderboard.md`, so parallel
  Mutators never race on the logs.
- **`<concurrency>` comes from the probe + the user's confirmation** — never assume the box; pin one
  child per GPU on multi-GPU; if a run OOMs/thrashes, lower `C` and say so (don't rewrite a child's
  config to fit), because the box's limit is real and rewriting the child corrupts the comparison.
- **`<budget>` (epochs/time), `<metric>`, and the eval/test split are FIXED and out-of-bounds for
  mutation.** The controller injects `<budget>` on every run, overriding any duration the child set —
  so "train longer" / change-the-metric / change-the-test-set can never win. Evolve the
  model/optimizer/data pipeline, not the compute or the scoring; comparability across programs depends
  on it.
- **Never symlink the entrypoint or any imported `.py`** into a child dir (it shadows the child's code
  via `sys.path[0]`); copy harness code, symlink only data, and run the isolation sanity gate before
  placing a child — a shadowed result is a phantom.
- Do not install new packages or modify the evaluation harness — `<metric>` is ground truth.
- **Do not pause to ask "should I continue?"** Run until `<total_budget>` (reserving a little for
  synthesis) or interrupt; if coverage stalls bias toward empty cells, if quality stalls exploit top
  elites. A child that overruns its gate is killed and recorded as `crash`.
