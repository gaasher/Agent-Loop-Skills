---
name: research-question-loop
description: >
  Use when the user has a vague topic or area of interest and wants it sharpened into a few strong,
  answerable, novel research questions. Each iteration scores the candidate questions against a fixed
  rubric (specific, answerable, novel, feasible, significant) — doing a quick literature/web check for
  whether each is already settled — and revises the weak axes: narrowing the over-broad, operationalizing
  the unanswerable, pivoting the already-answered toward what is still open. It loops until enough
  questions clear the bar. Bind it to your topic at setup.
metadata:
  version: "0.1.0"
---

# Research Question Loop

A **sharpen → score → revise** loop for the *framing* stage of research. The artifact is a small set of
research questions; the feedback signal is how many **clear the bar** — specific, answerable, novel,
feasible, and significant. You start from a vague topic, draft candidate questions, score each against a
fixed rubric (checking novelty against the literature), and rewrite the weak axis of the promising ones
until enough are strong. The goal is **a few excellent questions**, not many mediocre ones.

A good research question is the hard part of research: too broad and it cannot be answered; too narrow
and it does not matter; already settled and there is no point. This loop drives toward the narrow band
that is **answerable, novel, and worth answering**.

## Scope & limitations
This loop produces and refines **questions**, grounded by a *light* novelty check (a few searches), not
a full survey — for an exhaustive map use the literature-survey loop, and to turn a question into
testable predictions use the hypothesis-generation loop. The novelty check needs web/literature access;
without it, novelty is the loop's best judgment and should be labeled as unverified.

---

## 0. The literature toolchain (for the novelty check)

The **Novel** axis is checked against real literature via the shared **`literature-search` skill**
(`lit_search.py` over Semantic Scholar + arXiv) rather than a copy vendored here. Resolve once and reuse:
- **`<lit_skill_dir>`** — where the `literature-search` skill is installed. After the repo install step
  it sits as a **sibling** of this loop, e.g. `~/.claude/skills/literatureSearch/` (adjust per host).
- **`<lit_py>`** — `python3` (any ≥3.9). **`<lit>`** — `<lit_py> <lit_skill_dir>/lit_search.py`; append
  `--cache-dir <sandbox_root>/literature/.cache` after the subcommand to reuse a cache.

For this loop the two relevant moves are **`<lit> search "<q>"`** (is a direct answer already published?
what is the closest answered work?) and **`<lit> snippet "<q>"`** (pinpoint the answering passage). Each
prints JSON; on failure it prints `{"error","fallback"}` and exits non-zero — then fall back to
WebSearch/WebFetch. See the `literature-search` skill's `SKILL.md` for the full subcommand list and the
optional free `S2_API_KEY`.

**Check at setup whether the skill is installed** — probe `<lit_skill_dir>/lit_search.py` (try the
sibling-skill path, e.g. `~/.claude/skills/literatureSearch/`). If it is missing, **do not silently
fall back** — tell the user it is not installed and offer the choice:
- **Install it** (recommended for a real novelty check) — point them at the repo's install step
  (`cp -r agent-loop-skills/loops/* ~/.claude/skills/`, adjusting the destination per host), or just
  the one skill: `cp -r agent-loop-skills/loops/literatureSearch ~/.claude/skills/`. Then re-resolve
  `<lit_skill_dir>` and use `<novelty_check>: lit`.
- **Proceed without it** — set `<novelty_check>: web` (host WebSearch/WebFetch) or `none` (unverified
  novelty). The loop degrades cleanly and never hard-depends on the sibling skill.

Record the resolved choice in `<novelty_check>` so re-runs are non-interactive.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm in one line, and skip to §2. Otherwise resolve each
binding, then write `loop.run.yaml` (see `schema.example.yaml` for a commented template).
**Detect host:** `AskUserQuestion` available → Claude Code (infer + recommend); else ask as quoted
plain-text prompts.

- **`<topic>`** — the area of interest (and any scope: field, population, constraints, what the user
  already cares about).
- **`<n_questions>`** — how many strong questions to deliver (default 3).
- **`<pass_threshold>`** — rubric score (0–100) a question must clear to count as strong (default 75).
- **`<novelty_check>`** — how to check whether a question is already answered: `lit` (use the shared
  `literature-search` skill via `<lit>`, §0 — default when it is installed), `web` (use the host's
  WebSearch/WebFetch), or `none` (skip; novelty is unverified judgment). When resolving this, run the
  §0 install check: if the `literature-search` skill is absent, offer the user install-or-proceed
  rather than defaulting silently.
- **`<report>`** — the output question set (default `<sandbox_root>/questions.md`).
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8 iterations).

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` existed). Then initialise the ledger (§3).

---

## 2. The loop

The **rubric** (score each question 0–5 per axis):

| Axis | 5 | 3 | 1 |
|---|---|---|---|
| **Specific** | one clear construct/relationship, well-scoped | direction clear, scope loose | broad/ambiguous topic, not a question |
| **Answerable** | a concrete study/analysis could resolve it; the answer-shape is clear | resolvable in principle, approach unclear | not empirically/analytically decidable |
| **Novel** | open per the novelty check; closest work cited | partly addressed; a real twist remains | already answered (check found a direct answer) |
| **Feasible** | data/methods/access plausibly exist | feasible with effort | needs unavailable data or impossible measurement |
| **Significant** | answering it changes understanding or practice | a useful increment | marginal even if answered |

**Grading — raw points, scored by a separate subagent (no weights).** Each axis is worth **0–5 raw
points** straight from the rubric above; there are no per-axis weights. **Spawn a freshly instantiated
grader subagent** (spawn-or-degrade) — separate from whoever drafted or revised the questions, so the
score is independent and not self-graded — and give it each candidate plus its novelty evidence (§0).
It returns the five raw per-axis points. Sum them to a **raw score out of 25**, then convert to the
0–100 score you use everywhere:

`total = 100 × raw / 25`   (e.g. raw 20/25 → `total` 80).

A question is **strong** when `total ≥ <pass_threshold>` **and** no axis scored 1 (a single fatal axis
sinks it regardless of `total`).

**Iteration 0 — frame & draft.** Restate `<topic>` and what is interesting about it; draft 3–5 candidate
questions spanning different angles (mechanism, comparison, condition/boundary, application).

**Then, until stop (`<n_questions>` strong, or budget):**

1. **Score** each candidate with the grader subagent. First gather **novelty evidence** — run the
   `<novelty_check>` (§0): `<lit> search`/`snippet` (or WebSearch) for the question's core; if a direct
   answer exists, note the closest answered work; if only related work exists, note the open part. Then
   hand the candidate + that evidence to a freshly instantiated **grader subagent**, which returns the
   raw per-axis points; convert `raw/25 → total/100` (see the rubric block above).
2. **Diagnose** each promising question's **lowest axis** — the one thing keeping it from strong.
3. **Revise** that axis (one focused move per question): narrow an over-broad question to a specific
   population/condition; operationalize an unanswerable one into a measurable comparison; pivot an
   already-answered one toward the part the check showed is still open; raise significance by tying it to
   a decision or a contested claim. Drop questions with a fatal axis that revision cannot save, and add a
   fresh candidate if you are short.
4. **Log** one ledger row (§3); continue until `<n_questions>` questions are strong.

**Stop** when `<n_questions>` questions clear the bar, or at `<budget>`. Write `<report>`: each strong
question with its rubric scores, the novelty note (closest answered work / the open part), why it is
answerable (the study-shape that would resolve it), and why it matters — plus any runners-up and the axis
that held them back.

---

## 3. Ledger

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

---

## 4. Hard constraints
- **A few strong questions beat many weak ones** — do not pad `<report>` with questions that do not clear
  the bar; report them as runners-up with the blocking axis instead.
- **Novelty is checked, not assumed** — when `<novelty_check>` is `web`, actually search; cite the closest
  answered work, and never claim novelty the check contradicts. When `none`, label novelty unverified.
- **One focused revision per question per iteration**, targeting its weakest axis, so improvement is
  attributable and questions converge rather than thrash.
- **Keep the rubric and threshold fixed** so "strong" means the same thing throughout.
- **Grade with a separately instantiated subagent** scoring raw 0–5 points per axis (no weights); the
  orchestrator converts `raw/25 → 100` and never lets the drafter/reviser grade its own questions.
- The sandbox is self-contained (no `../` escapes). Do not pause the loop to ask whether to continue.
