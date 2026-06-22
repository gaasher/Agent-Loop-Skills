---
name: exploratory-autoresearch
description: >
  Use when the user wants an autonomous ML research loop that explores the space broadly rather than
  hill-climbing one approach. A temperature scheduler replaces the usual hypothesis step: it forces
  several wild, diverse swings (full rewrites, different architectures/regimes) early, then enters an
  adaptive phase that picks swing / merge / exploit per iteration — with a hard stagnation guard that
  bans further small-step exploits once they run too long, forcing a pivot back to a swing or merge.
  Tracks an approaches.md registry and a move_type per iteration; analyses every run before the next
  move. One change per iteration; loops forever until interrupted. Not for the standard analysis-first
  ml-autoresearch (which lets analysis alone choose each change), one-off training runs, or sweeps.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Exploratory Autoresearch Loop

This loop runs hot. Like the standard `ml-autoresearch`, every experiment is followed by a diagnostic
analysis pass. **Unlike** it, the *type* of change at each iteration is set by a **temperature
scheduler**, not the agent's intuition: it forces wide, diverse swings early (full rewrites,
fundamentally different architectures and training regimes), then drops into an adaptive phase that
chooses between **swing** (a fresh wild approach), **merge** (combine two registered approaches), or
**exploit** (a focused tweak of the best). A **stagnation guard** bans exploit once it has run
`<stagnation_limit>` times in a row, forcing a pivot back to swing or merge so the loop never gets
stuck hill-climbing. The feedback signal is `<metric>` read from the run log; an `approaches.md`
registry and a `move_type` per iteration are what make the scheduler work.

You are the researcher. Do not pause to ask for permission once the loop is running.

## When to use
Use for an open-ended ML campaign where you want forced breadth before refinement — the scheduler
guarantees you sample several distinct families before converging, and the stagnation guard prevents
endless small steps. Default to `<swing_budget> = 3` and `<stagnation_limit> = 3`; raise `<swing_budget>`
for wider initial exploration. Not for the standard analysis-first `ml-autoresearch` (use that when you
want the analysis alone to drive each change, with no forced-swing scheduler), not for a single training
run or a fixed sweep, and not for tasks with no measurable scalar metric.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available — record `<host>` = `claude-code`) infer a likely value for each binding from the project and
present it as the recommended option; on other hosts (`<host>` = `other`) ask each as a quoted plain-text
prompt. Then write `loop.run.yaml` (format: `examples/run.example.yaml`) and **confirm every value with
the user before creating any other files.** For `branches` strategy, create
`git checkout -b autoresearch/<run_tag>` (tag from today's date; branch must not exist). For `time`
gating, write `<sandbox_root>/run_with_timeout.sh` (`timeout $(( <budget> * 60 )) <entrypoint> "$@"`) and
use it as the run command, hard-killing at `2 × <budget>` min; for `epochs`, patch the epoch cap in an
`<editable_files>` file.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` / `<metric_direction>` | scalar to optimize + `minimize`/`maximize` | — | scan editable files + README for metric names |
| `<run_cmd>` / `<entrypoint>` | command that runs one experiment end to end | — | `pyproject.toml` / `.venv` / README |
| `<editable_files>` | files fair game to edit (never the eval harness) | — | model / config / train scripts; exclude data, logs, env, harness |
| `<sandbox_root>` | where snapshots + ledgers live | `./sandbox` | next to the editable files |
| `<iter_strategy>` | `snapshots` or `branches` | `snapshots` | is the working dir a clean git repo? |
| `<gate>` / `<budget>` | `time` (min) or `epochs`, and the limit | — | existing time/epoch settings in config |
| `<swing_budget>` | forced wild swings before adaptive mode | 3 (3–5) | wider = more initial breadth |
| `<stagnation_limit>` | max consecutive exploits before a forced pivot | 3 | — |

**FILE EDIT GUARD**: before touching any file at any point — setup or loop — confirm it is in
`<editable_files>`, because everything else is read-only ground truth (the eval harness defines
`<metric>`). No exceptions.

### Initialise the sandbox
Create the layout and write the ledger headers:
```
<sandbox_root>/
├── loop.run.yaml      ← resolved bindings (written now)
├── results.tsv        ← experiment ledger, header only (written now)
├── approaches.md      ← registry of every distinct approach (header only, written now)
└── iter1/             ← created at loop start
```
`results.tsv` header (tab-separated; `move_type` ∈ {`swing`, `merge`, `exploit`}):
```
iter	<metric>	status	move_type	analysis_summary	description
```
`approaches.md` header: `# Approach Registry` plus a one-line note that the merge step consults it to
find complementary approaches to combine.

## The loop (LOOP FOREVER — until interrupted)
Iteration 1 is always the **unmodified baseline** (it does not count as a swing): skip move-selection and
change-planning, but still run the **mandatory analysis** — it is the first empirical anchor iteration 2
builds on. Everything in `<editable_files>` is fair game (architecture, optimizer, hyperparameters, data
pipeline, loss, init, eval); on swings especially, full rewrites are encouraged. The only constraints are
that the code runs and finishes within `<budget>`. **Epoch efficiency is part of the objective** — a
change that reaches the same score in fewer effective steps is a real win. **Simplicity criterion**: all
else equal, simpler is better — a 0.001 gain that adds 20 lines of hacky code is not worth it; a 0.001
gain (or an equal metric) from *deleting* code is a `keep`.

The scheduler keeps two counters in memory across iterations: **`swings_taken`** (total swing iterations,
excludes the baseline) and **`consecutive_exploit`** (exploits since the last swing/merge; resets to 0 on
any swing or merge).

Copy this checklist each iteration and tick items off:
- [ ] **1. Look at the state.** *branches*: `git log --oneline -5`. *snapshots*: confirm `iter<N>/`
      doesn't exist. Read iter N-1's analysis summary and the two counters.
- [ ] **2. Pick `move_type`** (iteration 1: SKIP — baseline). Apply the scheduler below, then record the
      move before touching any file.
- [ ] **3. Form the hypothesis** (iteration 1: SKIP). State the move and why (cite the rule or the
      analysis), what you will do, and which `<editable_files>` it touches. See **The three moves**.
- [ ] **4. Snapshot / commit, then apply the change.** *snapshots*: create
      `iter<N>/{code_snapshot,analysis,results}/`, copy every `<editable_files>` into `code_snapshot/`,
      copy `loop.run.yaml` to `iter<N>/`, then apply. *branches*: apply, then
      `git commit -am "<move_type>: <desc>"`.
- [ ] **5. Run the experiment**, redirecting everything (never `tee`):
      `<entrypoint> > <sandbox_root>/iter<N>/<run_log> 2>&1` (or `run_with_timeout.sh` when time-gated).
      If it overruns, kill it and treat as a crash.
- [ ] **6. Read the metric**: `grep '^<metric>:' <sandbox_root>/iter<N>/<run_log>`. If empty,
      `tail -n 50 <run_log>`, read the trace, attempt one trivial fix (typo/import); if fundamentally
      broken, log `crash` and continue.
- [ ] **7. Analyse the results** — MANDATORY, produces real artifact files. See **Analysing**.
- [ ] **8. Update `approaches.md`** (swing and merge moves only). See **The registry**.
- [ ] **9. Log to `results.tsv`** (untracked — never commit). See **Ledger**.
- [ ] **10. Keep or revert** (the change ran this iteration). Improved per `<metric_direction>` → `keep`,
      update current-best. Equal/worse/crash → `discard`/`crash`; *branches* `git reset --hard HEAD~1`,
      *snapshots* restore `<editable_files>` from `iter<N>/code_snapshot/`. Apply the simplicity criterion
      before logging `discard`. On a crash/OOM, fix with the *minimal* change that preserves the intent
      (OOM → smaller batch + grad-accum to hold effective batch) — never mutate the experiment.
- [ ] **11. Update counters** (below) and go to step 1.

### The scheduler (step 2 — this is the loop's identity)
Follow the rules **exactly, in order** — they are hard constraints, not suggestions:
```
IF   iter == 1                                  → baseline   (run unmodified; no move)
ELIF swings_taken < <swing_budget>              → swing      (forced exploration)
ELIF consecutive_exploit >= <stagnation_limit>  → swing OR merge  (forced pivot — exploit BANNED)
ELSE                                            → agent chooses: swing / merge / exploit
```
On the free `ELSE` branch, let iter N-1's analysis decide:
- **swing** if the current family has a fundamental ceiling — e.g. all top results share a failure mode.
- **merge** if two+ `approaches.md` entries have distinct, non-overlapping strengths (prefer parents that
  changed *different axes* — they combine additively rather than interfere).
- **exploit** if the current best has obvious analysis-suggested headroom not needing a new architecture.

### Counter update (step 11)
```
if move_type in {swing, merge}:  swings_taken += 1 (swing only); consecutive_exploit = 0
elif move_type == exploit:       consecutive_exploit += 1
```

### The three moves (step 3)
- **Swing** — *fundamentally* different from every previous swing (not a tweak; the diff should look
  obviously different from the current best). Most people swing on architecture by reflex — fight that.
  These axes are equally valid and underexplored: **architectural family** (how information flows, depth
  vs width, skip connections, local vs global); **initialization** (magnitude-based, structure-preserving,
  input-statistics-driven, sparse — different early dynamics); **data pipeline** (ordering, sampling,
  determinism, coverage of the view space — not just augmentation flavours); **per-component LR
  decoupling** (early/late layers, norms, biases, heads each have their own optimal step); **evaluation**
  (single pass, multi-view, checkpoint averaging, calibration); **objective** (loss shape, target
  sharpness, auxiliary/consistency signals). A genuine swing explores one of these in a way not yet tried.
- **Merge** — select two+ entries from `approaches.md` and name what is taken from each; the result is a
  new approach that is not a minor variant of either parent. Prefer components from *different axes*.
- **Exploit** — a targeted, focused change to the current best, grounded in a specific analysis finding.
  One or two things at a time; **decouple the axes** (test a new optimizer and a new LR as separate
  iterations so you know which caused the result). Never a different architecture.

### Analysing (step 7 — MANDATORY; produces real artifacts)
This is the spine that feeds the next move. Run whatever analysis most increases your understanding of
*why* this result happened. Every analysis script goes in `iter<N>/analysis/`; every output (plots, CSVs,
text) goes in `iter<N>/results/`, redirecting stdout there. Do not proceed until the results exist —
analysis that wrote no file did not happen. Dimensions to draw from (choose what fits): gradient
norms/flow, activation stats/saturation, embeddings (PCA/CKA/collapse), error & confusion analysis, loss
dynamics & **headroom** (was it still improving at cutoff?), weight/parameter stats, data profiling
(often the highest-yield), compute profiling.

Write a concise **analysis summary** (3–8 bullets): what you examined, the single most important finding,
and what it implies for the next move (whether it favours swing / merge / exploit).

**Ablation discipline** (after any `keep` that touched more than one axis): you don't yet know which part
caused the gain — flag it and consider an ablation exploit next, reverting one component at a time.
Building on an unablated multi-axis change is building on an unknown.

**Forward-looking instrumentation.** After analysing, ask *"what would I wish I had logged?"* — if the
producing script is in `<editable_files>`, add it now (best-epoch checkpoint, per-layer grad norms,
per-class accuracy). Richer logs improve every future analysis; adding instrumentation is a valid
iteration on its own (log it as `move_type=exploit`).

### The registry (step 8 — `approaches.md`, swing and merge only)
Append an entry; the `axes changed` field is what the merge step uses to find complementary parents (two
that changed *different* axes beat two that both changed the architecture):
```markdown
## Approach <N>: <short name>
- **move_type**: swing | merge
- **iter**: <N>
- **<metric>**: <value>  (status: keep | discard | crash)
- **axes changed**: architecture | initialization | data pipeline | optimizer | lr schedule | evaluation | objective | other
- **key ideas**: <what makes this approach distinct>
- **strengths** / **weaknesses** (from analysis): <what worked / what the analysis says is missing>
- **ablated?**: yes (which components isolated, what was found) / no
- **parents** (merge only): Approach X + Approach Y — axes taken from each
```

## Ledger
`<sandbox_root>/results.tsv`, tab-separated, never commas in free text. Status ∈ {`keep`, `discard`,
`crash`}; use `0.000000` for the metric on crashes. For `branches`, the first column is the 7-char commit
instead of the iter number.
```
iter	<metric>	status	move_type	analysis_summary	description
1	0.6320	keep	swing	baseline; grad norms clean, no pathologies	baseline
2	0.5910	discard	swing	ResNet blocks; gradient flow good but overfit on 5 epochs	ResNet-style residual blocks
3	0.6890	keep	swing	MLP-Mixer; feature mixing effective, less overfit	MLP-Mixer token+channel mix
4	0.7120	keep	merge	Mixer channel-mix + ResNet skips; best of both	merge: Mixer + ResNet skips
5	0.7250	keep	exploit	train/val gap small; warmup helped stability	add 2-epoch LR warmup
6	0.7240	discard	exploit	no gain from dropout; val acc unchanged	add dropout 0.1
7	0.6800	discard	swing	forced pivot after stagnation guard; ViT too data-hungry	ViT patch-16 from scratch
```
`approaches.md` registry — one entry per swing/merge, format above. Example:
```markdown
# Approach Registry
The merge step consults this file to find complementary approaches to combine.

## Approach 3: MLP-Mixer
- **move_type**: swing
- **iter**: 3
- **val_acc**: 0.6890  (status: keep)
- **axes changed**: architecture
- **key ideas**: token mixing + channel mixing, no convolutions
- **strengths**: less overfit than ResNet, fast per-epoch
- **weaknesses**: spatial locality not exploited; edges/textures underused
- **ablated?**: no
```
Report the **best** iteration (not necessarily the last) when summarising. Do not commit `results.tsv` or
`approaches.md` — leave them untracked.

## Constraints
- **Only edit files in `<editable_files>`** — confirm before every edit, because everything else is
  read-only ground truth and the eval harness defines `<metric>`.
- **One change per iteration**, so each metric delta is attributable to one move.
- **The scheduler rules are hard constraints, not suggestions.** When
  `consecutive_exploit >= <stagnation_limit>` you MUST choose swing or merge — exploit is unavailable
  regardless of what the analysis suggests; this guard is what prevents endless hill-climbing.
- **Analysis is mandatory every iteration** and must produce real files in `iter<N>/results/`; a move
  with no analysis behind it degrades the loop into blind iteration and starves the next decision.
- A swing must be *fundamentally* different from every prior swing; a merge must name what it takes from
  each parent — otherwise the registry and the breadth guarantee mean nothing.
- Do not install packages or add dependencies the project lacks; helper scripts stay stdlib-only.
- Always redirect training output to `<run_log>`; never use `tee`. The sandbox is self-contained — no
  `../` escapes.

## Stops
This loop runs **forever until the human interrupts it** — do not pause to ask "should I continue?" or
"is this a good stopping point?". The human may be away and expects autonomous work indefinitely. A
working result is the start of the next iteration, not the end. If ideas run dry: re-read the in-scope
files for missed angles, go deeper on the analysis (gradients/activations/embeddings/errors always
surface something), combine previous near-misses from `approaches.md`, or take a more radical swing.
