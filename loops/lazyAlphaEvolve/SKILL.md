---
name: lazyAlphaEvolve
description: >
  Use when the user wants to evolve an ML model/approach the way AlphaEvolve evolves
  code: a population of program variants, each a small LLM-proposed diff to a parent,
  scored by a training run, kept in a MAP-Elites + islands archive so diverse high
  performers survive. A deliberately simplified ("lazy"), ML-bent re-creation of
  AlphaEvolve / OpenEvolve that runs on an agent harness with bounded parallelism.
  Loops for a fixed compute budget or until interrupted.
metadata:
  version: "0.1.0"
---

# lazyAlphaEvolve

An agent-harness re-creation of **AlphaEvolve** (Novikov et al., 2025, arXiv:2506.13131) and its
open-source implementation **OpenEvolve**, **bent for ML-model autoresearch** and deliberately
**simplified**. The "program" being evolved is the model's editable code; a **child** is one
analysis-informed **SEARCH/REPLACE diff** to a parent, scored by a **training run** (cascade-
evaluated), and placed in a **MAP-Elites archive across islands**. See the README for exactly how
this is similar to / different from AlphaEvolve, and the simplifications.

**You are the controller** (the Distributed Controller Loop, made finite): you sample a parent +
inspirations from the archive, spawn Mutators to produce + evaluate children (bounded parallelism),
place them, migrate between islands, and checkpoint. Mutators are minimal (`roles/Mutator.md`). Do
not pause for permission once running.

The cast and files (all in this folder):
- `roles/Mutator.md` — produces + cascade-evaluates one child (the generation step).
- `schemas/result.schema.json` — the child result a Mutator returns.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question below and wait for the user's explicit answer —
do NOT infer or skip any.** The *evolutionary* config is kept to two core knobs (§1b–1c) plus an
opt-in advanced branch (§1d) — but the **standard task bindings (§1a) are each required** and must
be asked individually; they define the task and cannot be guessed.

### 1.0 Detect host
`AskUserQuestion` available → **`<host>`** = `claude-code` or `other`. Host decides execution: on
Claude Code spawn real `Agent` Mutators in parallel (capped); otherwise **degrade** to running the
generation's children sequentially (identical algorithm, serial).

### 1.0b Probe the box (MANDATORY — measure, never assume)
Measure the hardware before sizing anything; record and report to the user:
- **CPU cores**: `python3 -c "import os; print(os.cpu_count())"` → **`<cores>`**.
- **RAM**: macOS `sysctl -n hw.memsize`; Linux `grep MemTotal /proc/meminfo` → **`<ram_gb>`**.
- **Accelerator**: `nvidia-smi --query-gpu=name,memory.total,count --format=csv` (NVIDIA); else on
  macOS check Apple GPU/MPS; else CPU-only → **`<accelerator>`**, **`<vram>`**, **`<gpu_count>`**.
These drive the concurrency recommendation in §1c.

### 1a. Standard task bindings — ASK EACH, one at a time, and wait (do not infer or bundle)
These define the task and **cannot be skipped**. Ask each explicitly (Claude Code: infer a
recommended option and confirm via `AskUserQuestion`; Other: a quoted prompt):
- **`<metric>`** + **`<metric_direction>`** — the scalar to optimize and whether to min/maximize.
- **`<run_cmd>`** / **`<entrypoint>`** — the command for one training run (the evaluator `h`).
- **`<editable_files>`** — **the program being evolved** (e.g. `model.py`, `config.yaml`); never the
  eval harness or data. **You MUST ask this explicitly — it is the code that gets mutated; do not
  assume or default it.** (Multi-select in Claude Code.)
- **`<sandbox_root>`** — where `lae/` is created.
- **`<gate>`** (`time`/`epochs`) + **`<budget>`** — the size of one full run. This is the **fixed
  eval budget applied to EVERY program** so scores are comparable, and the controller **enforces it
  on each run** (injects/caps the program's own epoch/time setting). It is **not** a mutation target:
  a child may not "train longer" to look better. Changing the budget is a *global* decision the user
  makes by re-running the whole loop — never a per-program change. Identify the key that controls
  duration now (e.g. `train.epochs`) so the controller can override it.

No `iter_strategy` — this loop is sandbox-only (see §3).

### 1b. CORE knob 1 — total budget
**`<total_budget>`** = how much compute to spend = total **full** training runs (or wall-clock
minutes). The single cost dial. `num_generations` is derived: `ceil(total_budget / C)`.

### 1c. CORE knob 2 — concurrency
**`<concurrency>`** `C` — parallel evaluations. Recommend from the §1.0b probe and ask to confirm:
CPU-only → `max(1, <cores>//4)`; single GPU/MPS → default `1`, ask if more fit in `<vram>`;
multi-GPU → `<gpu_count>` (pin one child per GPU via `CUDA_VISIBLE_DEVICES`). Surface the risk once
if they exceed what the box can sustain, then honor their choice.

### 1d. Advanced config — opt-in branch
Ask one yes/no: **"Use defaults for the evolutionary settings, or customize them?"**
- **Defaults (recommended)** → use the faithful defaults below; ask nothing more.
- **Customize** → only then ask for each (show the default as the recommended option):
  `num_islands` (4), `num_top` (3), `num_diverse` (2), `num_bins` (10), `migration_interval` (5),
  `diversity_reference_size` (10), `pop_per_island` (40), `seed` (42).
The cascade is **derived**, not asked: smoke = ~1 epoch / small subset of `<budget>`, full =
`<budget>`, gate = child's smoke `<metric>` ≥ parent's smoke. Axes are fixed (complexity × diversity).

### 1e. Initialise sandbox
```
<sandbox_root>/lae/
├── archive.tsv       ← current elites = program database + checkpoint (header only now)
├── history.tsv       ← append-only record of every child (header only now)
├── leaderboard.md    ← rendered UI (written now)
└── programs/         ← one self-contained dir per program (created as evaluated)
```
**`archive.tsv` header** (tab-separated): `island	cell	metric	child_id	parent_id	sandbox_path	complexity	diversity`
**`history.tsv` header**: `gen	island	parent_id	child_id	smoke_metric	full_metric	status	kept	cell`
Write all resolved bindings (standard + the two core knobs + the advanced set) to
`<sandbox_root>/lae/schema.yaml`.

### 1f. Confirm and go
Print the resolved bindings + the probe + derived `num_generations`. **Do not create files or
launch until the user confirms.**

---

## 2. The controller (finite generational algorithm)

You maintain `num_islands` MAP-Elites maps in `archive.tsv`, the append-only `history.tsv`, running
per-axis percentile stats, and `leaderboard.md`. **You are the sole writer of all shared logs**
(Mutators only return results — no write races).

**Niche computation (you do this, from a child's sandbox):**
- **`complexity`** = trainable param count (fallback: total LOC of the program's code — the editable
  files **plus any files it added**), **log10-scaled**.
- **`diversity`** = the **average normalized edit distance** of the program's concatenated code (its
  editable files + any added files) to a random sample of `diversity_reference_size` programs from
  its island (vs the baseline if the island is near-empty). Higher = more novel.
  (AlphaEvolve/OpenEvolve's diversity metric.)
- Normalize each axis with **running ~5th/95th percentiles** (not raw min/max, so one outlier can't
  collapse the range): `scaled = clamp01((v − p5)/(p95 − p5))`; `bin = min(num_bins−1, int(scaled ×
  num_bins))`; `cell = (complexity_bin, diversity_bin)`. **Re-bin** existing elites when a percentile
  shifts enough to move edges (keep the higher `<metric>` on collisions; archive is small).

### Algorithm
```
seed RNG with `seed`.
GEN 0: in each island, create the baseline program (a copy of <editable_files>) + optionally a few
       stochastic variants; cascade-evaluate; place in the archive.
for generation in 1..num_generations:                 # finite (= ceil(total_budget / C))
  build EXACTLY C tasks (one per free slot):
    island       = round-robin over islands
    parent       = sample a parent elite from that island (seeded rule)
    inspirations = top `num_top` by metric + `num_diverse` most-diverse elites of that island
    child_id, child_dir = new program dir; COPY the parent's program + harness code into it
                          (real copies, NOT symlinks; symlink only the data dir) — see §3
  run the C Mutators in parallel (spawn-or-degrade), each with roles/Mutator.md, its parent code,
      inspirations, the parent's artifacts, its child_dir, and the smoke/full budgets:
      -> Mutator proposes a SEARCH/REPLACE diff, applies it in child_dir, cascade-evaluates
         AT THE FIXED <budget> (the controller injects/caps the epoch-or-time key on the run command,
         overriding any duration the child set), returns
         {child_id, parent_id, approach_summary, sandbox_path, status, smoke_metric, metric}
  for each returned child:
      append a `history.tsv` row (status, smoke/full metric, cell, kept?)
      if status == evaluated: compute niche -> cell; place in island map iff <metric> better (kept=y)
      (smoke_dropped / crash: recorded in history, not placed)
  re-render leaderboard.md; checkpoint (archive.tsv is already the checkpoint); print a status line
  if generation % migration_interval == 0: ring-migrate top elites island k -> k+1
  stop if total_budget spent (reserve a little for synthesis)
FINAL: synthesize.
```

**Prompt the Mutator gets** (the prompt sampler): parent code + inspirations + the parent's rendered
artifacts (`<metric>`, per-class accuracy, loss curve, stderr) + the instruction to return one
SEARCH/REPLACE diff. (Single harness model — no LLM ensemble.)

**Final synthesis.** Report the global-best program + its `lae/programs/<id>/` path, the illuminated
complexity×diversity map (coverage + who won each region), per-island bests, and 2–3 notably diverse
runners-up.

---

**NEVER STOP** (until `total_budget` or interrupt): don't pause to ask "should I continue?". If
coverage stalls, bias parent/child selection toward empty cells; if quality stalls, exploit top
elites. Resume from `archive.tsv` + `history.tsv` if interrupted.

---

## 3. Program sandboxes (sandbox-only — no branches)
A parallel population doesn't map onto git branches, so every program is a **self-contained,
fully-runnable dir** `<sandbox_root>/lae/programs/<child_id>/`; the archive references it by id.
- **Build the child dir by COPYING real files** (not symlinks): the parent's `<editable_files>`
  (then apply the diff) **and the harness/entrypoint code it imports** (e.g. `train.py` and any
  non-editable local modules). **Symlink ONLY large read-only data** (data isn't imported, so a
  symlink is safe for it) — or point the config's data path at the shared absolute location.
- Evaluate **from inside the child dir**: `cd <child_dir> && <entrypoint>`.
- **CRITICAL — never symlink the entrypoint or any imported `.py`.** Python resolves a symlinked
  script's `__file__` to the link *target*, so `sys.path[0]` becomes the original directory and the
  child's `model.py`/`dataset.py` are **silently shadowed by the baselines** — the child trains the
  unmodified baseline and every architecture/data mutation becomes a no-op (tell-tale: *identical
  loss curves across different "architectures"*). Copy the harness so the child dir is `sys.path[0]`.
  (Equivalent safe alternative: `cd <child_dir> && python -m <entrypoint_module>`, which forces
  `sys.path[0] = cwd`.)
- **Isolation sanity gate (do this):** confirm each child actually ran *its own* code before placing
  it — the harness should log the model's **param count / a code fingerprint**, and the controller
  flags any child whose code changed but whose loss curve / metric is identical to its parent's
  (that means the harness shadowed it). Do not place a shadowed result; fix the sandbox first.
- The **repo working tree is never mutated**, so parallel children are isolated and safe. Lineage is
  tracked by `parent_id` in `archive.tsv`/`history.tsv`.

---

## 4. Log formats
**`archive.tsv`** (elites + checkpoint):
```
island	cell	metric	child_id	parent_id	sandbox_path	complexity	diversity
0	(2,7)	0.7100	g4-i0-a1	g2-i0-a3	lae/programs/g4-i0-a1	2.1M	0.71
```
**`history.tsv`** (every child, append-only):
```
gen	island	parent_id	child_id	smoke_metric	full_metric	status	kept	cell
4	0	g2-i0-a3	g4-i0-a1	0.61	0.71	evaluated	y	(2,7)
4	1	g2-i1-a0	g4-i1-a2	0.40	-	smoke_dropped	n	-
```
**`leaderboard.md`** — re-rendered each generation: global best + per-island coverage + the archive
ranked by `metric`. Do not commit `lae/` to git; leave it untracked.

---

## 5. Hard constraints (never violate)
- A child works **only inside its own `lae/programs/<child_id>/` dir**: it may edit the copied
  `<editable_files>` **and create new files there** (e.g. a new module its approach needs). It must
  **never modify any existing file outside that dir** — the repo working tree, the read-only
  harness, the data, and other programs' dirs are all out-of-bounds. (New files = fine;
  out-of-bounds edits = forbidden.)
- **The controller is the sole writer** of `archive.tsv`, `history.tsv`, `leaderboard.md`.
- Concurrency `C` comes from the §1.0b probe + the user's confirmation — never assume the box; pin
  one child per GPU on multi-GPU; if a run OOMs/thrashes, lower `C` and say so (don't rewrite a
  child's config to fit).
- Do not install new packages or modify the evaluation harness — `<metric>` is ground truth.
- Stop at `<total_budget>`; reserve budget for the final synthesis. A child that overruns its gate
  is killed and recorded as `crash`.
- Mutators compute nothing about the archive; the controller derives every niche and writes every log.
- **The eval budget (epochs/time), the metric, and the eval/test split are FIXED and out-of-bounds
  for mutation.** The controller injects `<budget>` (and the smoke budget) on every run, overriding
  any duration the child set — so "train longer" / change-the-metric / change-the-test-set can never
  win. Evolve the model/optimizer/data pipeline, not the compute or the scoring.
- **Never symlink the entrypoint or any imported `.py` into a child dir** (it shadows the child's
  code with the baseline via `sys.path[0]`). Copy harness code; symlink only data. Verify each child
  ran its own code (the isolation sanity gate, §3) before placing it.
- Keep setup to the two core knobs unless the user opts into the advanced branch (§1d).
