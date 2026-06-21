---
name: hypothesis-gen-loop
description: >
  Use when the user wants a set of novel, testable, literature-grounded research hypotheses for a
  question or domain — generated, vetted against the literature, and ranked. A multi-agent loop: a
  Generator proposes candidate hypotheses, a LiteratureScout grounds each in real retrieved literature
  (is it already known? what is the closest prior work? what gap does it fill?), and a Judge scores them
  against a fixed rubric (novelty, grounding, testability, specificity, significance) and keeps the
  strong, non-duplicate ones. It loops — mutating toward the open gaps the literature surfaces — until
  fresh rounds stop adding new hypotheses. Like researchProposalLoop, but it generates hypotheses
  instead of grading a proposal.
metadata:
  version: "0.1.0"
---

# Hypothesis Generation Loop

A **multi-agent, literature-grounded** generation loop. The artifact is a growing **pool of
hypotheses**; the feedback signal is the number of **strong, distinct hypotheses** that clear the bar —
where "strong" is decided against real retrieved literature, not vibes. Each round: **generate →
ground → judge → keep → mutate toward the gaps**, until the pool stops growing (saturation).

The cast (all roles in `roles/`, spawned as isolated subagents where the host supports it, else adopted
inline — **spawn-or-degrade**). **You are the orchestrator.**
- `roles/Generator.md` — proposes a batch of candidate hypotheses aimed at the open gaps.
- `roles/LiteratureScout.md` — grounds each candidate in real literature (novelty · support · gap),
  the ScholarEval analog; emits feedback validated against `schemas/litscout.schema.json`.
- `roles/Judge.md` — scores each against the **fixed rubric** and decides keep/kill/dedupe
  (`schemas/verdict.schema.json`).

The discipline: a hypothesis enters the pool only if the literature says it is **not already
established** (novelty), prior work makes it **plausible** (grounding), and a **feasible test** exists.
Generating is not confirming — the output is a ranked set of strong *candidates to test*, each with how
to test it.

---

## 0. The literature toolchain (read once)

All literature access goes through `tools/lit_search.py` (vendored, stdlib-only, no installs). Resolve
once and reuse:
- **`<skill_dir>`** — this folder. **`<lit_py>`** — `python3` (any ≥3.9).
- **`<lit>`** — `<lit_py> <skill_dir>/tools/lit_search.py`. To reuse a cache across calls, append
  `--cache-dir <sandbox_root>/literature/.cache` **after the subcommand** (it is a per-subcommand flag,
  not global), e.g. `<lit> search "<q>" --cache-dir <sandbox_root>/literature/.cache`.

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--year 2018-] [--min-citations N] [--limit N]` | discover related work (titles, TLDR, abstract, citations, arxiv_id) |
| `<lit> snippet "<q>" [--limit N]` | pinpoint a verbatim passage — novelty/support evidence |
| `<lit> cite <paperId> --direction references\|citations\|recommend` | walk the citation graph |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf]` | deep-read one paper's methods/results |
| `<lit> keys [--init]` | report which API keys are present (booleans only) |

On failure each prints `{"error","fallback"}` and exits non-zero — then fall back to your built-in
**WebSearch/WebFetch** (tag that evidence `source:"web"`). `S2_API_KEY` (free) makes `snippet`/`cite`
reliable; it is optional and the tool degrades without it.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm in one line, and skip to §2. Otherwise resolve each
binding, then write `loop.run.yaml`. **Detect host:** `AskUserQuestion` available → Claude Code (infer
+ recommend); else ask as quoted plain-text prompts.

- **`<question>`** — the research question / domain (and any scope: field, population, constraints).
- **`<gen_n>`** — candidates the Generator proposes per round (default 6).
- **`<keep_threshold>`** — rubric score (0–100) a hypothesis must clear to enter the pool (default 65).
- **`<eval_scale>`** — LiteratureScout depth: `low` (2 candidates deep · 1 query each · 0 fulltext),
  `medium` *(default)* (all candidates · 2 queries · 1 fulltext), `high` (3 queries · 3 fulltext).
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (max rounds, default 6), **`<patience>`**
  (default 2 — stop after this many rounds with no new kept hypothesis).
- **`<report>`** — final ranked set (default `<sandbox_root>/hypotheses.md`).

**S2 key onboarding (optional, never block):** run `<lit> keys`; if `S2_API_KEY` is absent, run
`<lit_py> <skill_dir>/tools/lit_search.py keys --init` (creates/append-only `keys.env` at the project
root — confirm it is gitignored) and ask the user to paste their free key themselves (`! $EDITOR
./keys.env`), or say "skip" to run on the keyless pool / WebSearch. Never ask for the secret in chat.

**Confirm and go.** Print the bindings + the live/degraded literature tier; create nothing until the
user confirms (skip only when `loop.run.yaml` existed). Initialise the ledger (§3) and the empty pool.

---

## 2. The loop

`pool` = the kept hypotheses (starts empty). `gaps` = open questions the LiteratureScout has surfaced
(starts empty; seed from the question). `dry` = consecutive rounds with no new keep (starts 0).

### Each round N (until `dry == <patience>` or `N == <budget>`):

1. **Generate.** Run `roles/Generator.md` (spawn-or-degrade) with `<question>`, the current `pool`, and
   `gaps`. It writes `round<N>/candidates.json` — `<gen_n>` specific, testable, plausibly-novel
   candidates aimed at the gaps, none duplicating the pool.
2. **Ground.** Run `roles/LiteratureScout.md` (spawn-or-degrade) on `candidates.json` with `<lit>` and
   the `<eval_scale>` caps. It writes `round<N>/litscout.json` — per candidate: novelty assessment +
   closest prior work, support, gap, testability — every point citing **real** retrieved evidence.
3. **Judge.** As `roles/Judge.md`, apply the fixed rubric + evidence gate to `litscout.json`, checking
   each candidate against the `pool` for duplicates. Write `round<N>/verdict.json`: scores, `total`,
   `keep`, `duplicate_of`.
4. **Update.** Add every `keep:true` non-duplicate hypothesis to `pool` (with its scores + grounding +
   how-to-test). Add the new open questions from this round's `gap` points to `gaps`. If the round added
   ≥1 new kept hypothesis, set `dry = 0`; else `dry += 1`.
5. **Log** one ledger row (§3) and continue.

**Re-ground every round** — novelty is judged from a *fresh* literature check each round, never carried
over, so "the literature already covers this" reliably kills a crowded idea.

**Stop** on saturation (`dry == <patience>`) or `<budget>`. Write `<report>`: the pool ranked by score,
each hypothesis with its **statement, novelty assessment + closest prior work (cited), supporting
evidence (cited), the gap it fills, and how to test it**, plus a short list of the strongest open gaps
still unexplored (leads for a deeper run).

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
round	generated	kept_new	pool_size	top_kept
```
Example:
```
round	generated	kept_new	pool_size	top_kept
1	6	3	3	spaced practice aids procedural (not just declarative) retention [82]
2	6	2	5	sleep-timed review beats time-of-day-matched review [78]
3	6	0	5	-
```
Per-round `candidates.json` / `litscout.json` / `verdict.json` live in `round<N>/`. Do not commit
`ledger.tsv`, `round*/`, or `literature/` — leave them untracked.

---

## 4. Hard constraints (never violate)
- **Never fabricate citations or snippets.** Every evidence entry is a real `lit_search.py` / WebFetch
  retrieval from that round; snippets are verbatim. On `{"error","fallback"}`, use WebSearch/WebFetch —
  never invent a paper.
- **Novelty is decided by the literature, not assertion.** A hypothesis the search shows is already
  established is killed, however appealing; "I think it's novel" with no closest-work search caps novelty.
- **Generate ≠ confirm.** Kept hypotheses are strong *candidates to test*, each stated with its test —
  never reported as established findings.
- **The rubric is fixed** and the keep-bar is stable, so saturation is meaningful.
- **Reward distinct hypotheses**, not volume — duplicates and rewordings are cut.
- Do not install packages (`lit_search.py` is stdlib-only); never print/commit API keys (`keys.env`
  stays gitignored). The skill folder is self-contained — no `../` escapes.
- Do not pause the loop to ask whether to continue; run until saturation or budget.

## 5. When the loop stops
End with: the **ranked hypothesis set** (`<report>` path), the pool size and score trajectory across
rounds (from `ledger.tsv`), and the **strongest unexplored gaps** — so the user sees both the vetted
hypotheses and where a deeper search would look next.
