# researchProposalLoop

**Evaluate → grade → revise a research proposal until it clears a passing grade.**

You give the loop a **research proposal** (problem · proposed methodology · planned
experiments). Each iteration:

1. **ScholarEval** evaluates it *grounded in the literature* — a faithful reimplementation of
   [ScholarEval (arXiv 2510.16234)](https://arxiv.org/abs/2510.16234): a **Soundness** module
   (per proposed method: literature **Support / Contradictions / Suggestions**) and a
   **Contribution** module (per contribution dimension: **Strengths / Weaknesses /
   Suggestions**), retrieving evidence from Semantic Scholar + arXiv via the vendored
   `lit_search.py`.
2. A **Judge** converts that qualitative feedback into a **graded score (0–100)** against a
   fixed `rubric.md`, and emits a prioritized fix-list. ScholarEval only produces *feedback* —
   the Judge is what turns "is the feedback better?" into a number the loop can compare against
   your threshold.
3. If `grade ≥ <pass_threshold>` (and no hard gate fired), **stop** — passing grade reached.
   Otherwise a **Reviser** rewrites the proposal to address the highest-impact fixes *without
   watering down the research question*, and the round repeats until the threshold, the budget,
   or a plateau.

Every evaluation, grade, and revision is appended to `ledger.tsv`. Roles use
**spawn-or-degrade**: real isolated subagents on Claude Code, inline otherwise.

## Why a Judge on top of ScholarEval?

ScholarEval was built to give *dense, actionable feedback*, not a single score — its only
numbers in the paper are a meta-eval (rubric *coverage* of the evaluator). To "iterate until a
passing grade," you need a stable scalar. The Judge supplies it by grading the proposal **from
ScholarEval's literature-grounded evidence** against a **fixed** rubric — deliberately *not*
self-refining, because a moving bar would make "did the proposal actually improve?"
unanswerable.

## Design decisions

- **Fixed rubric**, not self-refining — a stable passing bar (contrast `adversarialMLAutoResearch`).
- **Grade through evidence, not prose** — confident writing can't inflate the score; an
  **evidence gate** discounts any ScholarEval point not backed by a real retrieved snippet.
- **Hard gates** — a refuted core method or an ungrounded evaluation forces a fail regardless
  of the averaged grade.
- **Intent guard** — the Reviser strengthens the *same* idea; it can't game the grade by
  gutting the ambition or softening every claim.
- **S2 + arXiv stack** — the paper relies on Semantic Scholar; `snippet` (soundness) and `cite`
  (contribution graph) are the two S2-only moves, with arXiv `fulltext` substituting for the
  paper's GROBID full-text parse. Degrades to WebSearch/WebFetch with no key.

## Files

| File | Role |
| --- | --- |
| `SKILL.md` | the loop program (bindings → evaluate → grade → revise → stop) |
| `roles/ScholarEval.md` | the two-module literature-grounded evaluator (+ example output) |
| `roles/Judge.md` | grades the feedback → 0–100 + ranked fixes (+ example verdict) |
| `roles/Reviser.md` | rewrites the proposal to address the top fixes — searches the literature (`<lit>`) for real new citations when a fix needs one (+ example fixes input) |
| `rubric.md` | the **fixed** grading rubric the Judge applies |
| `schemas/scholareval.schema.json` | the ScholarEval evaluation object |
| `schemas/verdict.schema.json` | the Judge's graded verdict |
| `schema.example.yaml` | example resolved bindings |
| `lit_search.py`, `lit/` | vendored Semantic Scholar + arXiv search backend |

## Fidelity note

The paper's pipeline uses Semantic Scholar snippet+paper+recommendation APIs and **GROBID**
full-text parsing. This loop reproduces the **method** (extract → retrieve → summarize →
synthesize, for both modules) using the vendored `lit_search.py` (`snippet`/`search`/`cite`)
plus arXiv `fulltext` for deep reads, and degrades to `WebSearch`/`WebFetch` when keys are
absent. It trades some retrieval depth for being self-contained and installable. The Judge +
fixed-rubric grading layer is **this loop's addition** — the paper itself only scores its
evaluator's rubric coverage, not the proposal.
