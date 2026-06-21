---
name: anomaly-investigation-loop
description: >
  Use when the user has an anomalous or surprising result — a metric spike or drop, an outlier, an
  unexpected number — and wants the root cause found, not guessed. Each iteration forms candidate
  explanations, tests each against the data, and eliminates the ones the data refutes, narrowing until
  exactly one cause survives and is confirmed by a positive test. The result is an investigation log
  with the confirmed root cause and the evidence that ruled out the alternatives. Bind it to your data
  and the anomaly description at setup.
metadata:
  version: "0.1.0"
---

# Anomaly Investigation Loop

A **form → test → eliminate** loop (root-cause analysis as a search). The artifact is an investigation
log; the feedback signal is the number of **live candidate explanations** — you drive it down toward a
single cause that is **confirmed**, not merely consistent. Each iteration you propose candidate causes,
run analyses that would refute or confirm each, and eliminate the ones the data kills.

The discipline this enforces: a cause is "root" only when it both **survives attempts to refute it**
and makes a **positive prediction that checks out** (e.g. "if this is the cause, removing it restores
normal" — and it does). A story that merely *could* explain the anomaly is a hypothesis, not a finding.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm the values in one line, and skip to §2. Otherwise
resolve each binding, then write `loop.run.yaml` so re-runs are non-interactive.

**Detect host:** if `AskUserQuestion` is available you are in **Claude Code** — infer a likely value
and present it as the recommended option. Otherwise ask each as a quoted plain-text prompt.

- **`<dataset>`** — the data (or logs) to investigate. Read-only ground truth.
- **`<anomaly>`** — what was observed that looks wrong (the metric, where/when, and how big the
  deviation is, if known). If vague, your first job is to make it precise (§2 iteration 0).
- **`<analysis_cmd>`** — interpreter for analysis snippets (default `python3`; stdlib `csv`/`statistics`
  preferred — if the data needs `pandas` and it is missing, degrade to stdlib or offer a consented
  `uv pip install`).
- **`<log>`** — the investigation log file (default `<sandbox_root>/investigation.md`).
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8 iterations).

**The run schema.** These resolved bindings are written to `<sandbox_root>/loop.run.yaml` so re-runs are
non-interactive. See **`schema.example.yaml`** (next to this skill) for the exact shape and field
comments; the user can also fill that template in by hand and point the loop at it to skip the
interactive questions.

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` already existed). Then initialise the ledger (§3) and start.

---

## 2. The loop

**Iteration 0 — characterize.** Quantify the anomaly precisely: write and run a snippet that pins down
*what* deviated, *where/when*, and *how big* the deviation is against the normal baseline (the same
metric on surrounding periods/segments). Then **form an initial slate of candidate explanations** —
mutually distinguishable causes, broad enough to contain the truth (a real change, a composition/mix
shift, a data-quality bug, a measurement change, seasonality, an outlier segment). List them in
`<log>` as the live candidates.

**Then, until stop (one confirmed cause, or budget):**

1. **Pick a candidate to test** — ideally the one whose test most cleanly splits the remaining field.
2. **Test it.** Write `<sandbox_root>/iter<N>/test.py` that computes the thing that would **refute or
   support** it (slice by segment/source/time, recompute the metric, compare distributions), run it
   with `<analysis_cmd>` redirecting output to `iter<N>/out.txt`.
3. **Eliminate or advance.**
   - The data **refutes** it → mark it eliminated in `<log>` with the evidence; drop it from the live set.
   - The data **supports** it → keep it live and, if it is now the leading candidate, run a
     **confirming test**: a positive prediction it uniquely makes (e.g. "remove/seasonally-adjust the
     suspected factor → the anomaly disappears"). Try also to **refute** it — a leading candidate that
     survives a genuine refutation attempt and passes its confirming test is the root cause.
4. **Log** one ledger row (§3) and continue, narrowing the live set.

**Stop** when exactly one candidate is **confirmed** (survived refutation + passed a positive test), or
at `<budget>`. Report the confirmed root cause with the confirming evidence, the alternatives and how
each was ruled out, and — if you stop without a single confirmed cause — the remaining live candidates
and the test that would separate them.

**Observational equivalence.** Two mechanistically different candidates can make *identical* predictions
in the data you have (e.g. a bot flood and a pipeline double-count both look like "sessions spike,
conversions flat" in daily aggregates). When that happens you cannot separate them here — do not pick
one arbitrarily. Report them as a single confirmed cause **at the resolution of the available data**,
and name the additional data that would distinguish them (finer-grained logs, raw event records, an
upstream check). Distinguish, too, the **mechanism** (how the metric moved) from the **root cause** (why
the inputs were wrong) — confirming the mechanism is progress but is not the same as finding the cause.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	candidate_tested	verdict	live_candidates
```
`verdict` ∈ {`characterize`, `refuted`, `supported`, `confirmed`}. Example:
```
iter	candidate_tested	verdict	live_candidates
0	characterize anomaly + slate	characterize	5
1	real drop across all segments	refuted	4
2	one segment's conversions fell	refuted	3
3	one source's sessions inflated	supported	2
4	removing that source restores normal	confirmed	1
```

---

## 4. Hard constraints
- **Confirm, don't just fit.** The root cause must survive an honest refutation attempt and pass a
  positive confirming test; "consistent with the data" is not enough, since several stories usually are.
- **Test against the data, not intuition** — every elimination and the final confirmation is backed by a
  computation you ran, recorded in `<log>`.
- **Keep candidates distinguishable** and prefer the test that splits the field fastest; do not chase one
  pet theory while leaving alternatives untested.
- **Only read `<dataset>`** — never modify it. The sandbox is self-contained (no `../` escapes).
- Do not pause the loop to ask whether to continue; run until a cause is confirmed or the budget is hit.
