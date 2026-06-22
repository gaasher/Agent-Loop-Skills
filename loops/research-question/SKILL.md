---
name: research-question
description: >
  Use when the user has a vague topic or area of interest and wants it sharpened into a few strong,
  novel, feasible research questions. Drafts candidate questions, scores each against a fixed rubric
  (Specific, Answerable, Novel, Feasible, Significant) with a light literature/web novelty check, and
  revises the weakest axis until enough questions clear the bar. Not for grading a full written
  proposal (use the research-proposal loop), and not for turning a question into testable predictions
  (use the hypothesis-generation loop).
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Research Question Loop

A **sharpen → score → revise** loop for the *framing* stage of research. The artifact is a small set
of research questions; the feedback signal is how many **clear the bar** — each scored 0-5 on five
fixed axes (Specific, Answerable, Novel, Feasible, Significant). You start from a vague topic, draft
candidates, score each against the rubric (with a light novelty check against the literature), and
rewrite the weakest axis of the promising ones until enough are strong.

A good research question is the hard part of research: too broad and it cannot be answered; too narrow
and it does not matter; already settled and there is no point. The goal is **a few excellent
questions**, not many mediocre ones — this loop drives toward the narrow band that is answerable,
novel, and worth answering.

## Scope & limitations
This loop produces and refines **questions**, grounded by a *light* novelty check (a few searches),
not a full survey — for an exhaustive map use the literature-survey loop, and to turn a question into
testable predictions use the hypothesis-generation loop. The novelty check needs web or literature
access; without it (`novelty_check: none`), novelty is the loop's best judgment and must be labeled
unverified.

## When to use
Use when the user has a topic, area, or rough curiosity and wants it turned into concrete questions
worth pursuing. Default: run the full draft→score→revise loop below. Escape hatch: if the user only
wants candidates rated (no rewriting), score the set once and report the rubric breakdown. Not for
grading a finished proposal, and not for generating hypotheses or experimental designs.

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<topic>` | the area of interest (field, population, scope, what the user already cares about) | — | ask the user |
| `<n_questions>` | how many strong questions to deliver | 3 | — |
| `<pass_threshold>` | rubric score (0-100) a question must clear to count as strong | 75 | a solid question without demanding perfection |
| `<novelty_check>` | how to check whether a question is already answered: `lit` \| `web` \| `none` | `lit` if the sibling skill is installed, else `web` | probe for the literature-search skill (below) |
| `<report>` | output question set | `<sandbox_root>/questions.md` | — |
| `<sandbox_root>` | where the ledger and report live | `./sandbox` | — |
| `<budget>` | max iterations | 8 | — |

**Novelty toolchain (only for `novelty_check: lit`).** Paper search goes through the sibling
**`literature-search` skill** (`<lit> = <lit_skill_dir>/tools/lit_search.py`, with
`<lit_py> = python3` and `<lit_skill_dir>` its installed location, e.g.
`~/.claude/skills/literature-search/`); the relevant moves are `<lit> search "<q>"` (is a direct
answer already published?) and `<lit> snippet "<q>"` (pinpoint the answering passage). Confirm `<lit>
--help` works at setup; if the skill is absent, tell the user and either install it (copy the repo's
`loops/literature-search` folder into `~/.claude/skills/`) or degrade to `web` (host
WebSearch/WebFetch) or `none`. Record the resolved choice in `<novelty_check>` so re-runs are
non-interactive.

## The loop

The **rubric** (a fresh Grader scores each question 0-5 per axis — see grading below):

| Axis | 5 | 3 | 1 |
|---|---|---|---|
| **Specific** | one clear construct/relationship, well-scoped | direction clear, scope loose | broad/ambiguous topic, not a question |
| **Answerable** | a concrete study/analysis could resolve it; the answer-shape is clear | resolvable in principle, approach unclear | not empirically/analytically decidable |
| **Novel** | open per the novelty check; closest work cited | partly addressed; a real twist remains | already answered (check found a direct answer) |
| **Feasible** | data/methods/access plausibly exist | feasible with effort | needs unavailable data or impossible measurement |
| **Significant** | answering it changes understanding or practice | a useful increment | marginal even if answered |

**Grading — spawn a fresh Grader per iteration (spawn-or-degrade).** Each iteration, spawn a freshly
instantiated **Grader** subagent — separate from whoever drafted or revised the questions, so the
score is independent and not self-graded — and give it each candidate plus its novelty evidence. It
returns the five raw 0-5 per-axis points (no weights). On Claude Code spawn it as a real `Agent`;
otherwise adopt the Grader role inline in a clean pass. The orchestrator sums to a **raw score out of
25**, then converts to the 0-100 score used everywhere:

`total = 100 × raw / 25`   (e.g. raw 20/25 → `total` 80).

A question is **strong** when `total ≥ <pass_threshold>` **and** no axis scored 1 (a single fatal axis
sinks it regardless of `total`).

Copy this checklist and tick items off:
- [ ] Iteration 0 — restate `<topic>` and what is interesting about it; draft 3-5 candidate questions spanning different angles (mechanism, comparison, condition/boundary, application). Record nothing as strong yet.
- [ ] Gather novelty evidence per candidate via `<novelty_check>` (`<lit> search`/`snippet`, or WebSearch, or skip).
- [ ] Score — spawn a **fresh Grader** with each candidate + its evidence; it returns raw 0-5 per axis; convert `raw/25 → total/100`.
- [ ] Diagnose each promising question's **lowest axis** — the one thing keeping it from strong.
- [ ] Revise that one axis (one focused move per question); drop a fatally-flawed question revision cannot save; add a fresh candidate if short.
- [ ] Append a ledger row; stop when `<n_questions>` clear the bar, or at `<budget>`.

**Iteration 0 — frame & draft.** Restate `<topic>` and what is interesting about it; draft 3-5
candidate questions spanning different angles. Record nothing as strong yet.

**Then, until stop (`<n_questions>` strong, or `<budget>`):**

1. **Gather novelty evidence.** Run the `<novelty_check>` for each candidate's core: `<lit>
   search`/`snippet` (or WebSearch). If a direct answer exists, note the closest answered work; if only
   related work exists, note the open part. Each `<lit>` call prints JSON; on failure it prints
   `{"error","fallback"}` and exits non-zero — then fall back to WebSearch/WebFetch.
2. **Score.** Spawn a **fresh Grader** (spawn-or-degrade) and hand it each candidate plus its evidence;
   it returns the raw per-axis points. Convert `raw/25 → total/100`.
3. **Diagnose & revise.** Find each promising question's **lowest axis** and make one focused move on
   it: narrow an over-broad question to a specific population/condition; operationalize an unanswerable
   one into a measurable comparison; pivot an already-answered one toward the part the check showed is
   still open; raise significance by tying it to a decision or a contested claim. Drop questions with a
   fatal axis that revision cannot save; add a fresh candidate if you are short.
4. **Log** one ledger row and continue until `<n_questions>` are strong.

**On stop**, write `<report>`: each strong question with its rubric scores, the novelty note (closest
answered work / the open part), why it is answerable (the study-shape that would resolve it), and why
it matters — plus any runners-up and the axis that held them back.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
iter	question	total	weakest_axis	revision
```
Example:
```
iter	question	total	weakest_axis	revision
0	how does sleep affect learning	35	specific	drafted; far too broad
1	does sleep timing affect retention	62	answerable	operationalized: spaced-review vs sleep-matched review, 1-week retention
2	does post-learning sleep within 3h beat delayed sleep for procedural retention	86	-	strong (novel per check: tested for declarative not procedural)
```
Report the **best** outcome — the strong questions and their scores — not necessarily the last
iteration's set.

## Constraints
- **A few strong questions beat many weak ones** — do not pad `<report>` with questions that do not
  clear the bar; report them as runners-up with the blocking axis instead.
- **Novelty is checked, not assumed** — when `<novelty_check>` is `lit`/`web`, actually search, cite
  the closest answered work, and never claim novelty the check contradicts. When `none`, label novelty
  unverified.
- **Grade with a fresh Grader** scoring raw 0-5 per axis (no weights); the orchestrator converts
  `raw/25 → 100` and never lets the drafter/reviser grade its own questions, so the score stays honest.
- **One focused revision per question per iteration**, targeting its weakest axis, so improvement is
  attributable and questions converge rather than thrash.
- **Keep the rubric and threshold fixed** so "strong" means the same thing throughout.
- The sandbox is self-contained — no `../` escapes. Do not pause the loop to ask whether to continue;
  run until `<n_questions>` clear the bar or `<budget>` is hit.
