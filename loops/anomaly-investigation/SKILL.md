---
name: anomaly-investigation
description: >
  Use when the user has a known, already-observed anomaly in their data — a metric spike or drop, an
  outlier, an unexpected number — and wants its root cause diagnosed, not guessed. Forms a slate of
  candidate causes, tests each against the data, and eliminates the ones the data refutes, narrowing
  the live candidates until exactly one survives refutation and passes a positive confirming test. The
  result is an investigation log with the confirmed root cause and the evidence that ruled out the
  alternatives. Not for open-ended discovery over a dataset with no specific anomaly in hand (that is
  data-analysis), and not for checking an external claim against sources (that is claim-verify) — this
  is reactive diagnosis of one anomaly you already know about.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Anomaly Investigation Loop

A **form → test → eliminate → confirm** loop — root-cause analysis as a search. The artifact is an
investigation log; the feedback signal is the count of **live candidate explanations**, driven down
toward a single cause that is **confirmed**, not merely consistent. Each iteration you test one
candidate against the data and drop the ones the data refutes, narrowing the field until one survives.

The discipline this enforces: a cause is "root" only when it both **survives an honest attempt to
refute it** and makes a **positive prediction that checks out** (e.g. "if this is the cause, removing
it restores normal" — and it does). A story that merely *could* explain the anomaly is a hypothesis,
not a finding.

## When to use

Use this when an anomaly is already in hand — you know roughly what looks wrong and want the cause
diagnosed by elimination against the data. Default to a broad initial slate of mutually distinguishable
causes, then test the one that splits the field fastest; if the anomaly is vague, your first job is to
make it precise (iteration 0). Not for open-ended exploration of a dataset with no anomaly to chase
(use data-analysis), and not for verifying an external claim against the literature (use claim-verify).

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<dataset>` | data (or logs) to investigate; read-only ground truth | — | scan the working dir for a data/log file |
| `<anomaly>` | what looks wrong: the metric, where/when, and how big the deviation is | — | ask the user; make precise in iter 0 |
| `<analysis_cmd>` | interpreter that runs analysis snippets in the user's env | `python3` | `pyproject.toml`/`.venv`/`uv` in the working dir |
| `<log>` | output investigation log | `<sandbox_root>/investigation.md` | — |
| `<sandbox_root>` | where snippets + ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |

Analysis snippets run in the **user's environment** via `<analysis_cmd>`, so they may use whatever the
user has installed. Keep helper code **stdlib-first** (`csv`, `statistics`): if a snippet needs
`pandas`/`numpy`, probe with `try/except ImportError` and degrade to a stdlib path, or offer a
consented `uv pip install "pandas==<ver>"` — never assume the package is installed.

## The loop

Copy this checklist and tick items off:
- [ ] Iteration 0 — characterize the anomaly precisely; form an initial slate of candidate causes in `<log>`.
- [ ] Pick a candidate to test (the one whose test most cleanly splits the remaining field).
- [ ] Test it: write `<sandbox_root>/iter<N>/test.py`, run with `<analysis_cmd>`, redirect to `out.txt`.
- [ ] Eliminate (data refutes it → drop from the live set) or advance (data supports it → keep it live).
- [ ] Confirm the survivor: when one candidate leads, run a positive test only it predicts, after a refutation attempt.
- [ ] Append a ledger row; stop when one cause is confirmed or at `<budget>`.

**Iteration 0 — characterize.** Quantify the anomaly precisely: write and run a snippet that pins down
*what* deviated, *where/when*, and *how big* the deviation is against the normal baseline (the same
metric on surrounding periods/segments). Then **form an initial slate of candidate causes** — mutually
distinguishable explanations, broad enough to contain the truth (a real change, a composition/mix
shift, a data-quality bug, a measurement change, seasonality, an outlier segment). List them in
`<log>` as the live candidates. Record nothing as confirmed yet.

**Then, until stop (one confirmed cause, or budget):**

1. **Pick a candidate to test.** Ideally the one whose test most cleanly splits the remaining field, so
   each iteration removes as many live candidates as possible.
2. **Test it.** Write `<sandbox_root>/iter<N>/test.py` that computes the thing that would **refute or
   support** it (slice by segment/source/time, recompute the metric, compare distributions). Run it
   with `<analysis_cmd>`, redirecting output to `<sandbox_root>/iter<N>/out.txt` (never flood your
   context).
3. **Eliminate or advance.**
   - Data **refutes** it → mark it eliminated in `<log>` with the evidence; drop it from the live set.
   - Data **supports** it → keep it live, and if it is now the leading candidate run a **confirming
     test**: a positive prediction it uniquely makes (e.g. "remove / seasonally-adjust the suspected
     factor → the anomaly disappears"). Also try to **refute** it — a leading candidate that survives a
     genuine refutation attempt and passes its confirming test is the root cause.
4. **Log** one ledger row and continue, narrowing the live set.

**Observational equivalence.** Two mechanistically different candidates can make *identical*
predictions in the data you have (e.g. a bot flood and a pipeline double-count both look like "sessions
spike, conversions flat" in daily aggregates). When that happens you cannot separate them here — do not
pick one arbitrarily. Report them as a single confirmed cause **at the resolution of the available
data**, and name the additional data that would distinguish them (finer-grained logs, raw event
records, an upstream check). Distinguish, too, the **mechanism** (how the metric moved) from the **root
cause** (why the inputs were wrong) — confirming the mechanism is progress, but is not the cause.

## Ledger

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
Report the confirmed root cause with its confirming evidence, the alternatives and how each was ruled
out, and — if you stop without a single confirmed cause — the remaining live candidates and the test
that would separate them.

## Constraints
- **Confirm, don't just fit.** The root cause must survive an honest refutation attempt *and* pass a
  positive confirming test; "consistent with the data" is not enough, since several stories usually are.
- **Test against the data, not intuition** — every elimination and the final confirmation is backed by
  a computation you ran, recorded in `<log>`.
- **Keep candidates distinguishable** and prefer the test that splits the field fastest, so the live
  count falls; do not chase one pet theory while leaving alternatives untested.
- **Only read `<dataset>`** — never modify it, because it is the ground truth every test is checked
  against. The sandbox is self-contained (no `../` escapes).
- Do not pause the loop to ask whether to continue; run until a cause is confirmed or the budget is hit.

## Stops
- **Confirmed** — exactly one candidate survived refutation and passed a positive confirming test.
- **Budget** — `<budget>` iterations reached without a single confirmed cause; report the live set.
