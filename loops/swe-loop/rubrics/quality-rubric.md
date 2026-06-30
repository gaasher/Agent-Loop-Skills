# Code-quality rubric for QA

QA scores every accepted change on five axes, each 0-5. This is the *qualitative* half of the gate; the
*objective* half is `tools/quality_check.py` (hard numeric thresholds). A task is kept only when both
halves pass — tests green is necessary but not sufficient.

## The five axes (score each 0-5)

### 1. Simplicity — *is this the simplest change that works?*
- **5** — minimal diff; no speculative abstraction, no unused paths, no incidental complexity.
- **3** — works, but carries some avoidable indirection or a premature generalisation.
- **1** — over-engineered or convoluted; a much simpler solution is obvious.
- **0** — so complex it obscures whether it is even correct.

### 2. Readability — *can the next engineer follow it at a glance?*
- **5** — clear names, obvious control flow, small functions; reads top-to-bottom.
- **3** — mostly clear; one or two awkward names or a function doing slightly too much.
- **1** — cryptic names or tangled flow; needs real effort to follow.
- **0** — unreadable.

### 3. Comment hygiene — *do comments earn their place?*
- **5** — comments only where intent isn't obvious from the code; none redundant; none oversized.
- **3** — a few comments restate the code, or one block runs long.
- **1** — heavy redundant commentary, or long narrating blocks (what the code does, not why).
- **0** — comment noise dominates; `quality_check` flags `max_comment_block` / `long_comment_lines`.

### 4. Organization — *is the repo still well-organised after this?*
- **5** — new code lands in the right module; files/functions sized sensibly; nothing dumped where it doesn't belong.
- **3** — acceptable placement with a minor smell (a util in the wrong file, a file getting large).
- **1** — misplaced code, or a file/function growing past the configured size limits.
- **0** — structural mess; would force a reorg later.

### 5. Style match — *does it look like the surrounding code?*
- **5** — indistinguishable from existing code: same import style, error handling, naming, layout, idiom.
- **3** — broadly consistent with one or two local deviations.
- **1** — visibly foreign style (different conventions than the neighbouring files).
- **0** — ignores the codebase's conventions entirely.

## Quality floor (what `quality_pass` requires)
`quality_pass` is true only when **every axis is ≥ 3** AND `tools/quality_check.py` reports `ok: true`
(no threshold violation). Any axis at 0-2 produces a prioritised `fix` and fails the verdict — a change
can be correct and still be sent back for being unreadable, over-commented, or out of place.

## Hard gates (force `pass = false` regardless of axis scores)
1. **Any required test fails**, or the change does not parse/compile.
2. **A regression** — a test that passed before this task now fails.
3. **The Engineer edited a test file** (out of write scope; tests belong to QA).
4. **A `quality_check.py` threshold violation** (oversized comment block, over-long comment line,
   function/file LOC over limit, nesting over limit).

Record each breach in the verdict's `gate_failures` and turn it into a ranked `fix`.

## Scoring procedure (each iteration)
1. Ensure tests cover the task's `acceptance_criteria`; author missing ones (strengthen-only).
2. Run the full suite; record failures and `regression_green`.
3. Run `quality_check.py` on the changed files; capture violations.
4. Score the five axes from the actual diff, judging style against the neighbouring code.
5. Apply the floor and the hard gates → `quality_pass` and `pass`.
6. If not passing, emit ranked `fixes` (failing tests and regressions before quality).
