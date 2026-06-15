---
name: standardMLAutoresearch
description: >
  Use when the user wants an autonomous ML research loop that does more than
  blindly try changes. After every training run, the agent analyses the results —
  gradients, activations, data, embeddings, logs, or whatever is most informative —
  and uses those findings to motivate the next change. Loops forever until interrupted.
metadata:
  version: "0.1.0"
---

# Standard ML Autoresearch Loop

This loop is **analysis-first**. Unlike a pure iterate-and-score loop, every
experiment is followed by a diagnostic pass: you examine what actually happened
inside the model and use that to decide what to change next. Changes are hypotheses
grounded in evidence, not guesses.

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
to scanning `tail -n 20 run.log`.

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

If `branches`: propose a tag from today's date (e.g. `jun15`). Branch must not exist.
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
Use the wrapper as the effective run command. Hard kill at `2 × <budget>` minutes.

If `epochs`: patch whichever file in `<editable_files>` controls the epoch count to
cap at `<budget>`. Do not touch files outside `<editable_files>`.

---

### 1g. Initialise sandbox

Create the sandbox layout and write the run schema:

```
<sandbox_root>/
├── schema.yaml       ← resolved bindings (written now)
├── results.tsv       ← append-only log (header only, written now)
└── iter1/            ← created at loop start
```

**`results.tsv` header** (tab-separated, no commas):
```
iter	<metric>	status	analysis_summary	description
```

**`schema.yaml`**: write all resolved bindings (metric, run_cmd, editable_files,
sandbox_root, iter_strategy, gate, budget).

---

### 1h. Confirm and go

Print a summary of every resolved binding. **Do not create files or start the loop
until the user confirms.** Once confirmed, build the sandbox and begin immediately.

---

## 2. The experiment loop

**Everything in `<editable_files>` is fair game**: architecture, optimizer,
hyperparameters, batch size, model size, data pipeline, loss function. The only
constraints are that the code runs without crashing and finishes within `<budget>`.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement
that adds ugly complexity is not worth it. Conversely, removing something and getting
equal or better results is a great outcome — that's a simplification win. When
evaluating whether to keep a change, weigh the complexity cost against the improvement
magnitude. A 0.001 improvement that adds 20 lines of hacky code? Probably not worth it.
A 0.001 improvement from *deleting* code? Definitely keep. An improvement of ~0 but
much simpler code? Keep.

**The first run**: always run the script unmodified to establish the baseline.

**FILE EDIT GUARD**: Before editing any file at any step, confirm it is in
`<editable_files>`. No exceptions.

---

### LOOP FOREVER:

**1. Look at the state.**

- *branches*: `git log --oneline -5` — note current branch and commit hash (7 chars).
- *snapshots*: note iteration N, confirm `<sandbox_root>/iter<N>/` does not exist yet.

**2. Form a hypothesis and write an analysis plan.**

For the baseline (iteration 1), skip this — run unmodified.

On iterations 2+:

**2a. Form the hypothesis.** It must be grounded in specific empirical findings from
the previous iteration's analysis — not in theory alone. Cite the actual output:
name the file in `iter<N-1>/results/` and the specific number or pattern that
motivates this change. Theoretical reasoning ("X should work because Y") is not
sufficient without an empirical anchor.

Bad: *"GAP failed, so the model needs classifier capacity — try AdamW."*
Good: *"`results/gradient_norms.txt` showed the FC layer has 10× the gradient norm
of the conv layers, suggesting it dominates and receives poor signal. Hypothesis:
decouple weight decay with AdamW (weight_decay=0.01) to regularise the large FC
independently of the conv layers."*

State explicitly:
- The specific finding (file + number/pattern) that motivates the change.
- What you predict will happen and why that finding supports the prediction.
- Which file(s) in `<editable_files>` you will edit.

**2b. Write an analysis plan.** Before touching any code, write
`<sandbox_root>/iter<N>/analysis/plan.md` specifying exactly what you will examine
*after this run* to evaluate whether the hypothesis held. The plan must be specific
to the hypothesis — not a generic checklist. Ask: "If my hypothesis is correct, what
should I see in the data? If it is wrong, what should I see instead?"

Example for an AdamW hypothesis:
```markdown
# Analysis plan — iter8

Hypothesis: AdamW weight_decay=0.01 regularises the FC better than SGD.

To evaluate:
1. gradient_norms.py — compare per-layer gradient norms vs iter7. If hypothesis
   holds, FC gradient norm should be lower relative to conv layers.
2. weight_magnitudes.py — compare FC weight L2 norm vs iter7. Expect smaller.
3. loss_curve.py — compare train/val gap vs iter7. Expect val gap to narrow.

If FC grad norm is unchanged → AdamW had no effect on the gradient; try explicit
dropout or L2 on the FC directly.
```

This plan is written now, before the run, so the post-run analysis is driven by a
question — not chosen opportunistically after seeing the result.

**3. Snapshot / commit.**

- *snapshots*: create the following directories:
  ```
  <sandbox_root>/iter<N>/code_snapshot/
  <sandbox_root>/iter<N>/analysis/
  <sandbox_root>/iter<N>/results/
  ```
  Copy every file in `<editable_files>` to `code_snapshot/` (preserve relative paths).
  Copy `<sandbox_root>/schema.yaml` to `<sandbox_root>/iter<N>/schema.yaml`.
  Then apply your changes to the working files.
- *branches*: apply your change, then `git commit -am "<short description>"`.

**4. Run the experiment — redirect everything, never use `tee`.**

```bash
# time-gated
<sandbox_root>/run_with_timeout.sh > <sandbox_root>/iter<N>/run.log 2>&1

# epoch-gated
<entrypoint> > <sandbox_root>/iter<N>/run.log 2>&1
```

If the run has not terminated when it should have, kill it and treat as a crash.

**5. Read the metric.**

```bash
grep '^<metric>:' <sandbox_root>/iter<N>/run.log
```

If empty: `tail -n 50 run.log`, read the stack trace, attempt a trivial fix once
(typo, missing import). If fundamentally broken, log as `crash` and move on.

**6. Analyse the results.**

**This step is mandatory and must produce real artefacts. If `iter<N>/analysis/` is
empty after this step, you have not done the analysis. Do not proceed to step 7.**

Execute the analysis plan you wrote in step 2b. Run each script listed in `plan.md`
and record its output. Then ask: did the results match the predictions in the plan?
If not, why not? That discrepancy is usually the most informative finding of all.

**Every analysis script goes in `<sandbox_root>/iter<N>/analysis/`.**
**Every output (CSVs, text, plots) goes in `<sandbox_root>/iter<N>/results/`.**

```bash
python <sandbox_root>/iter<N>/analysis/<script>.py \
  > <sandbox_root>/iter<N>/results/<script>.txt 2>&1
```

The plan covers the hypothesis-specific analysis. After executing it, also ask:
*"What else does this result suggest that I didn't anticipate?"* If something
unexpected is visible — an unusual loss curve shape, a surprising class error pattern,
a gradient anomaly not in the plan — dig into it with an additional script.

Classes of analysis to draw from (choose what the hypothesis and results call for —
this is not a checklist to execute mechanically):

- **Gradient diagnostics**: per-layer gradient norms, flow across depth, vanishing/
  exploding signals, dead parameter regions.
- **Activation analysis**: layer-wise statistics (mean, variance, fraction of zeros),
  saturation, dead ReLU neurons.
- **Embedding inspection**: PCA / UMAP / t-SNE of learned representations, class
  separability, collapsed or entangled clusters.
- **Error analysis**: confusion matrix, hardest examples per class, failure modes,
  boundary cases.
- **Loss curve and dynamics**: train vs. val gap per epoch, when overfitting begins,
  whether the run was still improving at cutoff.
- **Weight and parameter analysis**: magnitude distributions per layer, sparsity,
  pathological initialisation.
- **Data and input profiling**: class balance, normalisation, augmentation effects,
  batch statistics.
- **Computational profiling**: per-layer cost, where the budget is being spent.
- **Anything else the results suggest.** Do not limit yourself to the above.

Write a concise **analysis summary** (3–8 bullet points):
- For each script in the plan: what you found and whether it matched the prediction.
- The single most important finding (expected or unexpected).
- The specific empirical evidence (file + number/pattern) that will anchor the next
  hypothesis. This is what step 2 of the next iteration must cite.

If the analysis reveals a useful quantity not currently being logged, add
instrumentation by editing the appropriate file in `<editable_files>`. This is a
valid iteration on its own if the diagnostic will materially improve future decisions.

**6b. Empirical justification gate.**

Before logging or forming the next hypothesis, answer this question in one sentence:

> *"The next change will be X because the analysis showed Y (from `results/<file>`,
> value/pattern Z)."*

If you cannot complete that sentence with a specific file reference and a concrete
value or pattern — not a theoretical argument — go back to step 6 and run more
analysis until you can. Proceeding without an empirical anchor is the failure mode
this loop is designed to prevent.

**7. Log to `results.tsv`. Do NOT commit this file — leave it untracked.**

Append one tab-separated row:

- *snapshots*: `<N>  <metric_value>  <status>  <one-line analysis summary>  <change description>`
- *branches*: `<commit>  <metric_value>  <status>  <one-line analysis summary>  <change description>`

`<status>` ∈ {`keep`, `discard`, `crash`}. Use `0.000000` for the metric on crashes.

**8. Keep or revert.**

- **If `<metric>` improved** (direction per `<metric_direction>`):
  - Status → `keep`. Update current-best.
  - *branches*: stay on this commit. *Snapshots*: leave working files as-is.

- **If equal or worse** (or crash):
  - Status → `discard` (or `crash`).
  - *branches*: `git reset --hard HEAD~1`.
  - *snapshots*: restore every file in `<editable_files>` from
    `<sandbox_root>/iter<N>/code_snapshot/`.

  Apply the simplicity criterion before logging `discard`: if the metric is equal but
  the code is meaningfully simpler, that is a `keep`, not a `discard`.

  If you feel stuck — the same idea keeps failing, or you are cycling through similar
  changes without progress — you can rewind further (branches: several commits; snapshots:
  restore from an earlier iteration's snapshot). Do this very, very sparingly. It is
  almost always better to let the analysis surface a new angle than to erase history.

**9. Use the analysis to form the next hypothesis → go to step 1.**

The analysis from step 6 is the primary input to the next iteration's hypothesis in
step 2. If the analysis was inconclusive, choose a new analysis angle rather than
changing the architecture blindly.

---

**NEVER STOP**: Once the loop has begun, do NOT pause to ask "should I continue?" or
"is this a good stopping point?". The human may be asleep, or away from their computer,
and expects you to continue working **indefinitely** until manually stopped. You are
autonomous. If you run out of ideas, think harder — re-read the in-scope files for
angles you missed, read any papers referenced in the code, try combining previous
near-misses from `results.tsv`, try more radical architectural changes. And in this
loop specifically: if architectural ideas are dry, go deeper on the analysis — a
thorough examination of gradients, activations, embeddings, or error patterns will
always surface something worth trying. The loop runs until the human interrupts you,
period.

---

## 3. results.tsv format

Tab-separated. Never use commas — they break in descriptions.

```
iter	<metric>	status	analysis_summary	description
1	0.6320	keep	baseline; grad norms even across layers, no obvious issues	baseline
2	0.6890	keep	activations in layer 2 near-saturated; added BN before ReLU	add BatchNorm after conv2
3	0.6750	discard	BN helped saturation but LR now too high; training unstable	increase LR to 0.05
4	0.7120	keep	loss curve still improving at epoch 5; extend budget next time	add lr warmup 3 epochs
```

---

## 4. Hard constraints (never violate)

- **Only edit files in `<editable_files>`.** Confirm before every edit.
- Do not install new packages or add dependencies not already present.
- Do not modify the evaluation harness — `<metric>` is the ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect training output to `run.log`. Never use `tee`.
- The sandbox must be fully self-contained — no `../` escapes.
- Do not commit `results.tsv` to git. Leave it untracked.
