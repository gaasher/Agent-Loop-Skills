---
name: blue-team
description: >
  Use when the user has concrete failing cases in code or a guardrail/classifier/filter/prompt/API they
  own — a red-team failure catalogue OR a CI/CD test-failure report (failing pytest/JUnit tests) — and
  wants the target patched until those failures are closed without breaking what already works. It points
  straight at the failed cases (normalize any source with tools/ingest.py), fixes one root-cause class
  per iteration, and re-checks with tools/verify.py — oracle mode against a red-team oracle, or tests
  mode against the test suite — keeping a patch only if it closes a class while nothing that passed
  before regresses, else reverting; loops until every class is closed (dry) or the budget runs out, then
  opens a pull request with the patch set. The defensive fixer half of a find→fix setup. Not for
  discovering new failures (that is red-team), and not for editing the oracle, tests, or holdout that
  define ground truth.
compatibility: Requires Python 3.9+; git + the gh CLI for the pull-request handoff (degrades to a patch series).
metadata:
  version: "0.1.0"
---

# Blue Team

A **defensive fixer** loop — the inverse of `red-team`. The artifact is the **target, now writable**;
the feedback signal is two-part, like `optimize-loop`: a **gate that must hold** (nothing that passed
before regresses) and a **metric that must drop** (the count of open failure classes, toward zero). You
point it at a set of **concrete failed cases** and fix them one root-cause class at a time. Each
iteration you patch one class, then run `tools/verify.py`, and keep the patch only if it closes the class
with no regression, else revert. You loop until every class is closed (**dry**) or the budget runs out,
then hand the patch set off as a pull request. This is the *fix* half of a find→fix setup (see
[Pairing](#pairing)).

The failed cases come from a real source; `tools/ingest.py` normalizes any of them into one catalogue:
- **`oracle` mode** — a `red-team` `failures.jsonl`: each case is an input where the target's verdict
  disagrees with a ground-truth **oracle**. A case is closed when target and oracle now agree; a
  regression is a benign `<holdout>` input that newly disagrees (most often a new over-block).
- **`tests` mode** — a **CI/CD test-failure report** (`pytest --junitxml` / JUnit XML, or a list of
  failing node ids): each case is a failing test. A case is closed when its test now passes; a
  regression is any *other* test that was passing and now fails.

## When to use
Use to fix a concrete set of failing cases in code or a guardrail/classifier/filter/prompt/API the user
owns — a red-team catalogue, or the failing tests from a CI run — driving the open-class count to zero
without breaking what worked. A `class` is the root-cause group the loop closes as a unit (a red-team
technique, or a CI failure area / test class).

Default: pick the mode that matches the source (`oracle` for red-team, `tests` for CI/CD). Escape hatch:
in `oracle` mode with no separate functional test suite, the `<holdout>` alone is the regression guard;
in `tests` mode the suite's own previously-passing tests are the guard. Not for finding new failures (run
`red-team`), and not for editing the ground truth (the oracle, the tests, or the holdout).

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it, confirm the values in one line, and
skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely
value per binding and recommend it; on other hosts ask each as a quoted prompt. Then write
`loop.run.yaml` and confirm before creating any other files. Two worked configs:
`examples/run.example.yaml` (oracle mode) and `examples/tests.run.yaml` (tests mode).

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<source>` | where the failed cases come from: `oracle` (red-team) or `tests` (CI/CD) | — | red-team `failures.jsonl` → `oracle`; failing pytest/JUnit → `tests` |
| `<target_files>` | the file(s) the loop may edit to fix the target | — | the source/guardrail/classifier behind the failures |
| `<catalogue>` | the failed cases to close, JSONL; build it with `tools/ingest.py` (see below) | `<sandbox_root>/catalogue.jsonl` | red-team's `<failures_log>`, or a JUnit report |
| `<oracle_cmd>` | *(oracle mode)* ground-truth verdict (frozen), same stdin→verdict contract as red-team | — | a reference checker / policy impl |
| `<holdout>` | *(oracle mode)* benign inputs that must keep passing (regression guard) | `<sandbox_root>/holdout.jsonl` | known-good inputs the oracle agrees on |
| `<test_cmd>` | *(tests mode)* runs the suite and writes a JUnit XML; regressions read from it | — | `pytest --junitxml=<junit>` (or any runner that emits JUnit) |
| `<junit>` | *(tests mode)* path to the JUnit XML `<test_cmd>` writes | `<sandbox_root>/junit.xml` | — |
| `<iter_strategy>` | `branches` (one commit per kept fix → feeds the PR) or `snapshots` (folder per iter) | `branches` | dirty / non-git tree → snapshots |
| `<pr_branch>` | branch the fixes land on and the PR opens from | `blue-team/<tag>` | today's date as `<tag>` |
| `<sandbox_root>` | where snapshots + the ledger live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |
| `<patience>` | give up on one class after N failed attempts → mark it a residual | 3 | — |

`<skill_dir>` is this skill's installed folder; substitute the real path when writing `loop.run.yaml`.

**Build the catalogue first** with `tools/ingest.py`, which normalizes any source into `{id, ..., class}`:
```
python3 <skill_dir>/tools/ingest.py --from red-team --in <failures.jsonl> --out <catalogue>   # oracle mode
python3 <skill_dir>/tools/ingest.py --from junit    --in <report.xml>     --out <catalogue>   # tests mode
```

**The signal** each iteration is `tools/verify.py`, in the mode matching `<source>`:
```
# oracle mode — <target_cmd> runs <target_files>, e.g. "python3 ./guardrail.py"
python3 <skill_dir>/tools/verify.py --target "<target_cmd>" --oracle "<oracle_cmd>" \
  --catalogue <catalogue> --holdout <holdout>
# tests mode — <test_cmd> writes the JUnit report verify.py then reads
python3 <skill_dir>/tools/verify.py --test-cmd "<test_cmd>" --junit <junit> --catalogue <catalogue>
```
Either way it prints one JSON object:
`{mode, open_classes, closed_classes, open_count, closed_count, regressions, regression_count, still_failing}`.

## The loop
Copy this checklist and tick items off:

- [ ] Iteration 0 — baseline: run `tools/verify.py` in the `<source>` mode; record the **open classes**
      (should match the catalogue) as the current state and confirm `regression_count` is 0 — if it is
      not, the catalogue or holdout is dirty, so fix that before fixing the target. Log the baseline row.
      Save a pristine copy of `<target_files>` to `<sandbox_root>/iter0/` (snapshots mode) or note the
      branch base (branches mode) — this is the **baseline** the final handoff diffs against, and also
      the snapshot iteration 1 reverts to.
- [ ] In `branches` mode, open the run on a fresh branch: `git checkout -b <pr_branch>`.
- [ ] For iteration N (≥1): snapshot the **current, pre-patch** `<target_files>` to `iter<N>/` (or note
      the git HEAD) *before*
      editing, so a discard can restore exactly this state.
- [ ] Pick **one** open class. Read its `still_failing` examples + the suggested fix from the catalogue,
      and patch `<target_files>` at the **root cause** — one fix should close *all* payloads of that
      class (e.g. normalize case once, not per-keyword). One class per iteration so each delta is
      attributable.
- [ ] Check the signal: run `tools/verify.py`. **Discard** — restore the snapshot / `git reset --hard` —
      if `regression_count > 0` (the gate) or the targeted class is still open. `verify.py`'s regression
      check *is* the gate: in oracle mode a regression is a newly-broken `<holdout>` case (e.g. a fix
      that closes a bypass by over-blocking benign inputs); in tests mode it is any previously-passing
      test the patch broke.
- [ ] **Keep** if there are no regressions and `open_count` strictly dropped. In `branches` mode commit
      it: `git commit -am "close <class>: <one-line fix>"`. Append a ledger row.
- [ ] If a class resists `<patience>` attempts, mark it an **open residual** and move on rather than
      thrashing. Stop when `open_count` = 0 (dry), at `<budget>`, or when every remaining class is a
      residual. `<budget>` counts **attempts** (each keep *or* discard is one iteration), not classes
      closed — a discard still consumes the budget.

On stop, restore the working files to the **best** iteration (most classes closed, zero regressions) and
report: classes closed vs residual, the failures resolved (oracle mode: the bypass/over-block split),
and regressions avoided. Then open the pull request (see [Handoff](#handoff-the-pull-request)).

**Fix toolkit.** In `tests` mode the patches are ordinary bug-fixes, grouped by failure area and applied
one area per iteration. In `oracle` mode (hardening a guardrail/filter), reach for these root-cause
patterns, mirroring red-team's attack toolkit:
- **Normalize before matching** — case-fold, de-leet (homoglyph/leet → letters), strip spacing and
  punctuation, NFKC-normalize unicode. One normalization step closes case / leetspeak / spacing classes.
- **Broaden the policy** — add missing synonyms/expansions to the blocked set (the `missing-synonym`
  class), keyed to the oracle's categories, not ad-hoc strings.
- **Tighten over-broad rules** — scope a match to whole words / the right context so benign inputs stop
  tripping it (the `overblock` class), the most common source of regressions.

Mind the **interaction order** (both modes): make the narrowing/over-broad fix *before* a sweeping one.
A fix that strips separators (closing `spacing`) can re-collapse a benign input into an over-broad
substring and silently reopen an `overblock` class — and likewise a broad code change can reopen a test
a narrower fix had to protect. Fix the narrow/over-broad case first, then generalize.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the description. `regr` = `regression_count`
this iteration (the gate: 0 is clean); `status` ∈ {`keep`,`discard`,`baseline`,`residual`}. Header
`iter	class_targeted	regr	open_classes	status	description`:
```
iter	class_targeted	regr	open_classes	status	description
0	-	0	5	baseline	catalogue: 5 open classes
1	case-bypass	0	4	keep	case-fold the input before matching
2	leetspeak	1	4	discard	de-leet regex also over-blocked a holdout input (regression)
3	leetspeak	0	3	keep	de-leet via translate table, holdout clean
4	missing-synonym	0	2	keep	add passphrase/credentials/api-key to the policy set
5	overblock	0	1	keep	require whole-word "secret key", not bare "secret"
6	spacing	0	0	keep	strip non-alphanumerics before matching — dry
```
Report the **best** iteration (open_classes lowest with `regr` 0), not necessarily the last.

## Constraints
- **Only edit `<target_files>`.** The ground truth — the oracle + `<holdout>` (oracle mode) or the test
  suite (tests mode) — and `tools/verify.py` are frozen; editing what measures the fix manufactures a
  pass (same rule as red-team and optimize-loop). If the oracle or a test is itself wrong, that is a
  finding to report, not something to patch here.
- **Fix the root cause, not the payload.** One fix should close every item of a class; patching a single
  example string while siblings still fail means the class is not closed. This mirrors red-team's class
  accounting, so the two loops agree on what "closed" means.
- **The regression gate is non-negotiable.** A patch that breaks something that passed before — a new
  over-block/bypass (oracle mode) or a previously-passing test (tests mode) — is a regression, not
  progress; revert it regardless of how many classes it closes. Prefer a narrower fix over a sweeping one.
- **One class per iteration**, so each delta is attributable and a bad fix is cheap to revert.
- Keep changes within the project's existing dependency set (stdlib is fine); stay inside the repo and
  `<sandbox_root>`; do not pause the loop to ask whether to continue — run until dry, budget, or residuals.

## Handoff: the pull request
The deliverable is a human-reviewable **pull request** — the communication interface to whoever owns the
target (a human keeps final approval, as with Copilot Autofix). On stop, with the working tree at the
best iteration:
- In `branches` mode each kept fix is already a commit on `<pr_branch>` whose message names the class +
  the one-line fix. Push and open the PR with `gh pr create`, body = the ledger (catalogue → fixes,
  classes closed, residuals listed, regressions avoided) and one reproducible example per closed class.
- **Confirm once before opening the PR** — pushing a branch and creating a PR is outward-facing; never
  auto-push silently.
- **Degrade, don't fail:** if there is no remote or `gh` is unavailable/unauthed, still produce the
  handoff — leave the commits on `<pr_branch>`, write `git format-patch` output and a `PR_BODY.md` into
  `<sandbox_root>`, and tell the user the single command to open the PR themselves. In `snapshots` mode
  (no git), emit a unified `diff` of `<target_files>` against the `iter0/` baseline copy, plus
  `PR_BODY.md`, instead.

## Pairing
This skill is the **fixer** — the back half of a find→fix loop. It assumes a catalogue already exists; by
itself it closes classes but does not search for new ones.

1. **Find** — `red-team` runs against the **frozen** target → `failures.jsonl` (distinct classes).
2. **Fix** *(this loop)* — patch the target to close those classes under the gate, **between** red-team
   runs, never inside one.
3. **Re-verify** — a **fresh** `red-team` run against the patched target confirms each class is closed
   and surfaces any new class the fix introduced (the regression gate already guards the over-block
   direction within this loop).

Keep the two agents independent — the attacker that wrote the catalogue should not grade its own patch.
The `purple-team` loop orchestrates the full find → fix → re-verify cycle until a fresh find stays dry;
this skill deliberately covers only the fix phase.
