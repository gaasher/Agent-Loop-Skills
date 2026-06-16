---
name: highTemperatureMLAutoresearch
description: >
  Use when the user wants an autonomous ML research loop that prioritises broad
  exploration over incremental refinement. Forces wide, diverse swings early, then
  adaptively chooses between merging approaches, taking another big swing, or
  exploiting the best so far — with a hard rule that prevents the loop from
  getting stuck in small-step mode for too long.
metadata:
  version: "0.1.0"
---

# High-Temperature ML Autoresearch Loop

This loop runs hot. It deliberately takes wild, diverse swings — full rewrites,
fundamentally different architectures, completely different training regimes — before
ever settling into refinement. The "temperature" is highest at the start and the loop
enforces variety: if it detects it has been making only small incremental steps for
too long, it forces a pivot back to a big swing or a merge.

Like `standardMLAutoresearch`, every run is followed by a diagnostic analysis phase.
Unlike it, the *type* of change at each iteration is governed by a scheduling rule,
not just the agent's intuition.

You are the researcher. Do not pause to ask for permission once the loop is running.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. You MUST ask every question below and wait for the
user's explicit answer. Do NOT infer, skip, or auto-apply any answer — even if you
think you know it from context. If you skip any question, you are doing it wrong.**

### 1.0 Detect host

Check whether the `AskUserQuestion` tool is available.

- **Yes → Claude Code path**: for each question below, scan the project to infer a
  likely answer, then present it as the recommended option via `AskUserQuestion`.
- **No → plain-text path**: ask each question as a quoted prompt and wait for a
  typed reply.

Record as **`<host>`** = `claude-code` or `other`.

---

### 1a. What metric should the loop optimize?

**Claude Code**: scan editable files and any README for metric names. `AskUserQuestion`:
- Option 1 *(Recommended)*: inferred metric, e.g. `val_acc`
- Option 2–3: other plausible metrics spotted in the code
- Option 4: `Other — I'll specify`

**Other**: Ask:
> "What scalar metric should I optimize, and should I minimize or maximize it?
>  (e.g. `val_loss` minimize, or `val_acc` maximize)"

Record as **`<metric>`** and **`<metric_direction>`** (`minimize` or `maximize`).
The loop infers the grep pattern automatically — tries `^<metric>:` first, falls back
to scanning `tail -n 20 <run_log>`.

---

### 1b. What Python environment and run command?

**Claude Code**: scan for `pyproject.toml`, virtualenv paths, README run instructions.
`AskUserQuestion` with inferred command as recommended option.

**Other**: Ask:
> "What command runs one training experiment end to end?
>  (e.g. `/path/to/venv/bin/python train.py` or `uv run train.py`)"

Record as **`<run_cmd>`** / **`<entrypoint>`** (usually the same).

> **Remote sandboxes**: if training runs on a remote host, note the connection.
> `<run_cmd>` is dispatched there; everything else runs locally.

---

### 1c. Which files are fair game to edit?

**Claude Code**: list candidate source files (model, config, training script). Exclude
data, logs, env files, and the evaluation harness. `AskUserQuestion` (multi-select):
one option per candidate file + `Other — I'll specify`.

**Other**: Ask:
> "Which files may I edit? (e.g. `model.py`, `config.yaml` — not the eval harness)"

Record as **`<editable_files>`**.

**FILE EDIT GUARD**: Before touching any file at any point — setup or loop — confirm
it is in `<editable_files>`. Everything else is read-only. No exceptions.

---

### 1d. Where should the sandbox live?

**Claude Code**: propose a sensible default (e.g. `./sandbox/` next to the editable
files). `AskUserQuestion` with that path as recommended option.

**Other**: Ask:
> "Where should I keep the sandbox? Give me an absolute or relative path."

Record as **`<sandbox_root>`**.

---

### 1e. Iteration strategy — branches or snapshots?

**Claude Code**: check whether the working directory is a git repo and whether it is
gitignored. `AskUserQuestion`:
- Option 1 *(Recommended)*: whichever is safer, with a one-line reason
- Option 2: the other strategy

**Other**: Ask:
> "Track iterations via:
>  (a) **branches** — one git commit per experiment, good runs advance the branch,
>      bad runs are `git reset`'d; or
>  (b) **snapshots** — all on one branch, each iteration gets a folder in the sandbox."

Record as **`<iter_strategy>`** = `branches` or `snapshots`.

If `branches`: propose a tag from today's date. Branch must not exist.
Create it: `git checkout -b autoresearch/<tag>`.

---

### 1f. Gate on time or epochs?

**Claude Code**: check the config/script for existing time or epoch settings.
`AskUserQuestion` with inferred value as recommended option.

**Other**: Ask:
> "Should each run be gated by wall-clock time (minutes) or a fixed epoch count?"

Record as **`<gate>`** = `time` or `epochs`, and **`<budget>`** = the limit.

If `time`: write `<sandbox_root>/run_with_timeout.sh`:
```bash
#!/usr/bin/env bash
timeout $(( <budget> * 60 )) <entrypoint> "$@"
```
Use the wrapper as the effective run command. If the run has not terminated when it
should have, kill it and treat as a crash.

If `epochs`: patch whichever file in `<editable_files>` controls the epoch count to
cap at `<budget>`. Do not touch files outside `<editable_files>`.

---

### 1g. How many initial forced swings?

**Claude Code**: suggest 3–5 as a sensible default. `AskUserQuestion`:
- Option 1 *(Recommended)*: `3 — enough to cover distinct approaches before converging`
- Option 2: `5 — wider initial exploration`
- Option 3: `Other — I'll specify`

**Other**: Ask:
> "How many iterations should be forced wild swings before the loop enters adaptive
>  mode? (Suggested: 3–5)"

Record as **`<swing_budget>`**.

---

### 1h. Stagnation limit — max consecutive exploit iterations?

**Claude Code**: suggest 3 as a sensible default. `AskUserQuestion`:
- Option 1 *(Recommended)*: `3 — force a swing or merge after 3 straight exploit steps`
- Option 2: `5`
- Option 3: `Other — I'll specify`

**Other**: Ask:
> "After how many consecutive small-step (exploit) iterations should the loop be
>  forced to take a big swing or merge? (Suggested: 3)"

Record as **`<stagnation_limit>`**.

---

### 1i. Initialise sandbox

Create the sandbox layout and write the run schema:

```
<sandbox_root>/
├── schema.yaml           ← resolved bindings (written now)
├── results.tsv           ← append-only log (header only)
├── approaches.md         ← registry of every distinct approach tried
└── iter1/                ← created at loop start
```

**`results.tsv` header** (tab-separated, no commas):
```
iter	<metric>	status	move_type	analysis_summary	description
```

`move_type` ∈ {`swing`, `merge`, `exploit`}.

**`approaches.md`**: create with a header only — the loop populates it as it runs:
```markdown
# Approach Registry

Each entry records a distinct approach tried during this run.
The merge step consults this file to find what to combine.

---
```

**`schema.yaml`**: write all resolved bindings.

---

### 1j. Confirm and go

Print a summary of every resolved binding. **Do not create files or start the loop
until the user confirms.** Once confirmed, build the sandbox and begin immediately.

---

## 2. The experiment loop

**`<run_log>`** refers to the file training output is captured in for a given
iteration. By default this is `<sandbox_root>/iter<N>/<run_log>` (the stdout/stderr
redirect the loop creates). If the harness writes its own log file under a different
name or path, use that file instead — or use both. Wherever `<run_log>` appears
below, substitute whichever file actually contains the training output for that run.

**Everything in `<editable_files>` is fair game**: architecture, optimizer,
hyperparameters, batch size, model size, data pipeline, loss function, initialization
scheme, evaluation strategy — on swing iterations especially, nothing is off limits.
Full rewrites are encouraged.

**Epoch efficiency is the objective, not just final score.** At every step, ask:
*"Am I getting the most signal per budget unit?"* A change that gets the same final
score in fewer effective steps is a real win — it means the remaining budget compounds
on a stronger foundation. Improvements that accelerate convergence are just as
valuable as improvements that raise the ceiling.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement
that adds ugly complexity is not worth it. Conversely, removing something and getting
equal or better results is a great outcome — that's a simplification win. When
evaluating whether to keep a change, weigh the complexity cost against the improvement
magnitude. A 0.001 improvement that adds 20 lines of hacky code? Probably not worth it.
A 0.001 improvement from *deleting* code? Definitely keep. An improvement of ~0 but
much simpler code? Keep.

**The first run**: always run the script unmodified to establish the baseline.
The baseline does not count as a swing.

**FILE EDIT GUARD**: Before editing any file at any step, confirm it is in
`<editable_files>`. No exceptions.

**Tracking state**: The loop maintains two counters in memory across iterations:
- **`swings_taken`**: total swing iterations completed (starts at 0).
- **`consecutive_exploit`**: consecutive exploit iterations since the last swing or
  merge (resets to 0 whenever a swing or merge is chosen).

---

### LOOP FOREVER:

**1. Look at the state.**

- *branches*: `git log --oneline -5` — note current branch and commit hash (7 chars).
- *snapshots*: note iteration N, confirm `<sandbox_root>/iter<N>/` does not exist yet.
- Read `consecutive_exploit` and `swings_taken` from your running state.

**2. Decide the move type for this iteration.**

This is the scheduling step. Follow the rules exactly, in order:

```
IF   iter == 1 (baseline)         → move_type = swing  (run unmodified)
ELIF swings_taken < <swing_budget> → move_type = swing  (forced exploration)
ELIF consecutive_exploit >= <stagnation_limit> → move_type = swing OR merge (forced pivot)
ELSE                               → agent chooses: swing / merge / exploit
```

When the agent has a free choice (the `ELSE` branch), use the analysis from the
previous iteration to decide:
- Choose **swing** if the analysis suggests the current family of approaches has a
  fundamental ceiling — e.g. all top results share the same failure mode.
- Choose **merge** if two or more approaches in `approaches.md` each have distinct
  strengths that do not overlap; combining them is likely to outperform either alone.
- Choose **exploit** if the current best approach has obvious headroom — clear
  improvements suggested by the analysis that do not require a different architecture.

Record the chosen `move_type` before touching any file.

**3. Form a hypothesis.**

State explicitly:
- The chosen `move_type` and why (cite the scheduling rule or the analysis finding).
- What you will do (describe the approach — for swings, describe the full new
  approach; for merges, name the approaches being combined and what is taken from each;
  for exploit, name the targeted change and the analysis finding that motivated it).
- Which file(s) in `<editable_files>` you will edit.

For the baseline (iteration 1), skip — run unmodified.

**What counts as a swing:**
A swing means the approach is *fundamentally* different from all previous swings —
not a tweak, not adding one layer to the same backbone. The changed code should look
obviously different from the current best when diffed.

Most people swing along the architecture axis by default. Fight that reflex. The
following axes are equally valid swing targets and are frequently underexplored:

- **Architectural family**: the overall structural pattern of the network — how
  information flows, how depth and width are arranged, whether connections skip layers,
  whether computation is local or global.
- **Initialization strategy**: how weights start matters as much as how they update.
  Different init philosophies (magnitude-based, structure-preserving, input-statistics-
  driven, sparse) lead to qualitatively different early training dynamics and can
  compress the effective learning budget significantly.
- **Data pipeline redesign**: not just swapping augmentation flavours, but rethinking
  *how* data is presented to the model over time — the ordering, the sampling strategy,
  the degree of randomness vs. determinism, and whether the full space of possible
  views is covered systematically or left to chance across the budget.
- **Per-component learning rate decoupling**: treat each distinct part of the model
  (early layers, late layers, normalisation parameters, biases, heads) as having its
  own optimal update magnitude. Scaling all of them together with a single LR is a
  strong assumption that is often wrong.
- **Evaluation strategy**: how predictions are aggregated at test time is a free
  variable — single forward pass, multiple views, checkpoint averaging, output
  calibration. The model you trained and the model you evaluate can differ more than
  you think.
- **Training objective restructuring**: what the model is directly optimised against
  — the loss surface shape, target sharpness, auxiliary signals, consistency
  constraints, or self-referential objectives.

A genuine swing explores one of these axes in a way not yet attempted.

**What counts as a merge:**
Select two or more entries from `approaches.md`. Explicitly name what is taken from
each. The result is a new approach that could not be described as a minor variant of
either parent. When choosing what to take from each, prefer components that operated
on *different axes* — they are more likely to combine additively rather than
interfere.

**What counts as an exploit:**
A targeted, focused change to the current best approach based directly on an analysis
finding. One or two things at a time — **decouple the axes**. If you want to test a
different optimizer *and* a different LR, run them as separate iterations; combined
changes obscure which one caused the result. Should NOT be a different architecture.

**4. Snapshot / commit.**

- *snapshots*: create:
  ```
  <sandbox_root>/iter<N>/code_snapshot/
  <sandbox_root>/iter<N>/analysis/
  <sandbox_root>/iter<N>/results/
  ```
  Copy every file in `<editable_files>` → `code_snapshot/` (preserve relative paths).
  Copy `<sandbox_root>/schema.yaml` → `<sandbox_root>/iter<N>/schema.yaml`.
  Then apply your changes to the working files.
- *branches*: apply your change, then `git commit -am "<move_type>: <short description>"`.

**5. Run the experiment — redirect everything, never use `tee`.**

```bash
# time-gated
<sandbox_root>/run_with_timeout.sh > <sandbox_root>/iter<N>/<run_log> 2>&1

# epoch-gated
<entrypoint> > <sandbox_root>/iter<N>/<run_log> 2>&1
```

If the run has not terminated when it should have, kill it and treat as a crash.

**6. Read the metric.**

```bash
grep '^<metric>:' <sandbox_root>/iter<N>/<run_log>
```

If empty: `tail -n 50 <run_log>`, read the stack trace, attempt a trivial fix once
(typo, missing import). If fundamentally broken, log as `crash` and move on.

**7. Analyse the results.**

This is the same analysis phase as in `standardMLAutoresearch`. Run whatever analysis
will most increase your understanding of *why* this result happened.

**Every analysis script goes in `<sandbox_root>/iter<N>/analysis/`.**
**Every output (plots, CSVs, text) goes in `<sandbox_root>/iter<N>/results/`.**

```bash
python <sandbox_root>/iter<N>/analysis/<script>.py \
  > <sandbox_root>/iter<N>/results/<script>.txt 2>&1
```

Classes of analysis to draw from (not an exhaustive list — choose what fits):

- **Gradient diagnostics**: per-layer norms, flow, vanishing/exploding signals.
- **Activation analysis**: saturation, dead neurons, layer-wise statistics.
- **Embedding inspection**: PCA / UMAP / t-SNE, class separability, collapse.
- **Error analysis**: confusion matrix, hardest examples, failure modes.
- **Loss curve and dynamics**: train/val gap, convergence, whether the run was
  still improving at cutoff.
- **Weight and parameter analysis**: distributions, sparsity, pathological init.
- **Data and input profiling**: class balance, normalisation, batch statistics.
- **Computational profiling**: per-layer cost, where the budget is being spent.
- **Anything else** the results suggest — don't limit yourself to this list.

Write a concise **analysis summary** (3–8 bullet points):
- What you examined and why.
- The most important finding.
- What it implies for the next move (and whether it favours swing / merge / exploit).

**Ablation discipline (applies after any `keep`).** If this iteration was kept,
ask: *"Which part of the change caused the gain?"* If the change touched more than
one axis (e.g. new architecture + new init + new LR), you don't actually know yet
what worked. When this is true, flag it in the summary and consider an ablation
exploit next: revert one component at a time to isolate the source of the improvement.
Building on a multi-axis change without ablating is building on an unknown — a future
swing or merge that duplicates the non-contributing parts wastes budget.

**Cross-setting check (optional but high-value after a strong `keep`).** If the
improvement is large, consider verifying it holds under a perturbation: a different
budget length, a different seed, or a slightly different data fraction. An improvement
that is robust across settings is worth building on; one that is fragile to the
evaluation conditions is likely noise.

**Extend the training log if it would help future analysis.**

If the training script (or any script that produces the training log or metrics file)
is in `<editable_files>`, you are allowed — and actively encouraged — to add new
metrics and diagnostics to it. Every future iteration benefits from richer logs, and
post-hoc analysis scripts can only work with what was recorded at training time. Do
not wait for a specific finding to trigger this; after any run, ask: *"What would I
wish I had logged right now?"*

Note: some harnesses write metrics to a separate file (e.g. a JSON or CSV) rather
than to the main training log. If that file's producer is in `<editable_files>`, it
is equally fair game to extend.

Useful things to consider adding (depending on what the current analysis is missing):

- **Per-epoch diagnostics**: gradient norms per layer, weight update magnitudes,
  activation statistics (mean, variance, fraction of zeros per layer).
- **Per-class breakdown**: per-class accuracy or loss at each eval, not just the
  aggregate — tells you whether a metric improvement is broad or driven by one class.
- **Training dynamics signals**: train/val gap per epoch, learning rate at each step
  if a scheduler is running, loss variance across batches.
- **Model state snapshots**: save a checkpoint at the best val epoch so analysis
  scripts can reload the model and probe it (embeddings, activations, gradients on
  held-out examples) without re-running training.
- **Anything else** that a post-hoc analysis script would need but currently has to
  approximate or skip.

Adding instrumentation is a valid iteration on its own — if richer logs will
materially improve the quality of the next three analyses, spending one iteration on
it is a good trade. Log it in `results.tsv` as `move_type=exploit` with description
`add <metric> logging`.

**8. Update `approaches.md` (swing and merge iterations only).**

If `move_type` is `swing` or `merge`, append an entry to
`<sandbox_root>/approaches.md`:

```markdown
## Approach <N>: <short name>

- **move_type**: swing | merge
- **iter**: <N>
- **<metric>**: <value>  (status: keep | discard | crash)
- **axes changed**: architecture | initialization | data pipeline | optimizer |
                    learning rate schedule | evaluation | objective | other
- **key ideas**: <bullet list of what makes this approach distinct>
- **strengths** (from analysis): <what worked>
- **weaknesses** (from analysis): <what didn't, or what the analysis suggests is missing>
- **ablated?**: yes / no — if yes, which components were isolated and what was found
- **parents** (merge only): Approach X + Approach Y — axes taken from each
```

The `axes changed` field is what the merge step uses to find complementary approaches:
two approaches that changed different axes are better merge candidates than two that
both changed the architecture.

This registry is the primary input to future merge decisions.

**9. Log to `results.tsv`. Do NOT commit this file — leave it untracked.**

Append one tab-separated row:

- *snapshots*: `<N>  <metric_value>  <status>  <move_type>  <one-line analysis summary>  <description>`
- *branches*: `<commit>  <metric_value>  <status>  <move_type>  <one-line analysis summary>  <description>`

`<status>` ∈ {`keep`, `discard`, `crash`}. Use `0.000000` for the metric on crashes.

**10. Keep or revert.**

- **If `<metric>` improved** (per `<metric_direction>`):
  - Status → `keep`. Update current-best.
  - *branches*: stay on this commit. *Snapshots*: leave working files as-is.

- **If equal or worse** (or crash):
  - Status → `discard` (or `crash`).
  - *branches*: `git reset --hard HEAD~1`.
  - *snapshots*: restore every file in `<editable_files>` from
    `<sandbox_root>/iter<N>/code_snapshot/`.

  Apply the simplicity criterion before logging `discard`: if the metric is equal
  but the code is meaningfully simpler, that is a `keep`.

  If you feel stuck — the same ideas keep failing with no signal — you can rewind
  further. Do this very, very sparingly. It is almost always better to let the analysis
  surface a new direction.

**11. Update counters and go to step 1.**

```
if move_type == swing or move_type == merge:
    swings_taken += 1         (only increment on actual swing, not baseline)
    consecutive_exploit = 0
elif move_type == exploit:
    consecutive_exploit += 1
```

Proceed to step 1 for iteration N+1.

---

**NEVER STOP**: Once the loop has begun, do NOT pause to ask "should I continue?" or
"is this a good stopping point?". The human may be asleep and expects you to continue
**indefinitely** until manually stopped. You are autonomous. If you run out of ideas,
think harder — re-read the in-scope files for angles you missed, read any papers
referenced in the code, try combining previous near-misses from `approaches.md`, try
more radical changes. If architectural ideas are dry, go deeper on the analysis. The
loop runs until the human interrupts you, period.

---

## 3. results.tsv format

Tab-separated. Never use commas.

```
iter	<metric>	status	move_type	analysis_summary	description
1	0.6320	keep	swing	baseline; grad norms clean, no pathologies	baseline
2	0.5910	discard	swing	ResNet blocks; gradient flow good but overfit badly on 5 epochs	ResNet-style residual blocks
3	0.6890	keep	swing	MLP-Mixer; feature mixing effective, less overfit than ResNet	MLP-Mixer token+channel mix
4	0.7120	keep	merge	merged Mixer channel-mix with ResNet skip conns; best of both	merge: Mixer + ResNet skips
5	0.7250	keep	exploit	train/val gap small; LR warmup helped stability	add 2-epoch LR warmup
6	0.7240	discard	exploit	no gain from dropout; val acc unchanged	add dropout 0.1
7	0.7260	keep	exploit	augmentation reduced overfit slightly	enable random crop augment
8	0.6800	discard	swing	forced pivot after 3 exploits; ViT too data-hungry for this subset	ViT patch-16 from scratch
```

---

## 4. approaches.md format

```markdown
# Approach Registry

---

## Approach 2: ResNet blocks

- **move_type**: swing
- **iter**: 2
- **val_acc**: 0.5910  (status: discard)
- **key ideas**: residual connections, 3-block depth, BN before ReLU
- **strengths**: stable gradients, good depth scaling
- **weaknesses**: overfit heavily on 5-epoch budget; needs more data or regularisation

## Approach 3: MLP-Mixer

- **move_type**: swing
- **iter**: 3
- **val_acc**: 0.6890  (status: keep)
- **key ideas**: token mixing + channel mixing, no convolutions
- **strengths**: less overfit than ResNet, fast per-epoch
- **weaknesses**: spatial locality not exploited; edges and textures underused
```

---

## 5. Hard constraints (never violate)

- **Only edit files in `<editable_files>`.** Confirm before every edit.
- Do not install new packages or add dependencies not already present.
- Do not modify the evaluation harness — `<metric>` is the ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect training output to `<run_log>` (default: `<sandbox_root>/iter<N>/<run_log>`). Never use `tee`.
- The sandbox must be fully self-contained — no `../` escapes.
- Do not commit `results.tsv` or `approaches.md` to git. Leave them untracked.
- The scheduling rules in step 2 are hard constraints, not suggestions. If
  `consecutive_exploit >= <stagnation_limit>`, you MUST choose swing or merge —
  exploit is not available regardless of what the analysis suggests.
