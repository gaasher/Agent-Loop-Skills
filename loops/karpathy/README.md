# karpathy

**The default loop: single-agent iterate-and-score, fully inline.**

A faithful adaptation of the [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch)
program-as-skill. One agent runs the whole loop with no subagents — everything lives
in `SKILL.md`.

Each iteration the agent proposes a change to the editable files, runs training,
reads the metric, then keeps or reverts the change and logs the outcome to the
sandbox. It loops forever until you interrupt it — designed to run while you sleep.

## What makes it different from the original

The original Karpathy loop is hardwired to a specific repo, a fixed metric (`val_bpb`),
a single GPU, a 5-minute time budget, and a branch-per-run git strategy. This version
asks you to supply those decisions at setup time, so it works with any project:

1. **Metric** — you name the scalar to minimize.
2. **Environment** — you specify the run command / Python env (local or remote).
3. **Editable files** — you say which files the loop may touch.
4. **Training entrypoint** — the exact shell command that launches one run.
5. **Sandbox location** — local or on a remote host; the loop keeps all artifacts there.
6. **Iteration strategy** — branch-per-run (Karpathy original) or same-branch
   snapshots (one folder per iteration under `sandbox/`).
7. **Gate** — time budget (minutes) or epoch budget; the loop injects a timeout wrapper
   or patches the epoch count as needed.

## Sandbox layout (snapshots mode)

```
<sandbox_root>/
├── results.tsv          # append-only run log
├── iter1/
│   ├── code_snapshot/   # copies of editable files before this iteration
│   └── run.log
├── iter2/
│   └── ...
```

## Files

| File | Role |
| --- | --- |
| `SKILL.md` | The full loop program — setup, experiment loop, logging, constraints. |
| `schema.example.yaml` | Copy to `schema.yaml` and fill in, or let the loop ask interactively. |
