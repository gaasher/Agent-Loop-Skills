---
name: hypothesis-gen
description: >
  Use when the user wants to generate and literature-vet a pool of novel, testable research hypotheses
  for a question or domain. A multi-agent loop: a Generator proposes candidate hypotheses, a
  LiteratureScout grounds each in real retrieved literature (already known? closest prior work? what
  gap does it fill?), and a Judge scores them against a fixed rubric and keeps the strong,
  non-duplicate ones; rounds repeat — mutating toward the open gaps — until fresh rounds stop adding
  keepers. Not for sharpening or decomposing a research question (no grounding/scoring there), and not
  for grading an existing written proposal against the literature.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Hypothesis Generation Loop

A **multi-agent, literature-grounded** generation loop. The artifact is a growing **pool of
hypotheses**; the feedback signal is the count of **strong, distinct hypotheses** that clear the bar —
where "strong" is decided against real retrieved literature, not assertion. Each round: **generate →
ground → judge → keep → mutate toward the gaps**, until the pool stops growing (saturation).

The discipline: a hypothesis enters the pool only if the literature says it is **not already
established** (novelty), prior work makes it **plausible** (grounding), and a **feasible test** exists.
Generating is not confirming — the output is a ranked set of strong *candidates to test*, each stated
with how to test it.

The cast (all in `roles/`):
- `roles/Generator.md` — proposes a batch of candidate hypotheses aimed at the open gaps.
- `roles/LiteratureScout.md` — grounds each candidate in real literature (novelty · support · gap);
  emits `litscout.json` (validates `schemas/litscout.schema.json`).
- `roles/Judge.md` — scores each against the **fixed rubric** and decides keep/kill/dedupe; emits
  `verdict.json` (validates `schemas/verdict.schema.json`).

**Spawn-or-degrade.** On Claude Code, spawn Generator / LiteratureScout / Judge as real `Agent`
subagents each round; otherwise adopt each role inline in this context. You are the orchestrator.

## When to use
Use when the user wants candidate hypotheses *generated and vetted* for a question or domain. Default:
run the full generate→ground→judge loop below until saturation. Escape hatch: if the user only wants a
single batch (no looping), run one round and report the kept hypotheses. Not for sharpening or
decomposing a question, and not for grading an existing written proposal.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm every value plus the live/degraded literature tier before
creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<question>` | the research question / domain, plus any scope (field, population, constraints) | — | ask the user |
| `<gen_n>` | candidate hypotheses the Generator proposes per round | 6 | — |
| `<keep_threshold>` | rubric score (0-100) a hypothesis must clear to enter the pool | 65 | — |
| `<eval_scale>` | LiteratureScout grounding depth (`low`/`medium`/`high`, see below) | `medium` | — |
| `<sandbox_root>` | where rounds, ledger, and lit cache live | `./sandbox` | — |
| `<budget>` | max rounds | 6 | — |
| `<patience>` | stop after this many rounds with no new kept hypothesis | 2 | — |
| `<report>` | final ranked hypothesis set | `<sandbox_root>/hypotheses.md` | — |

**Grounding depth dial** (`<eval_scale>` caps per round — candidates examined deeply · queries each ·
papers read full-text):

| preset | candidates deep | queries each | fulltext reads |
|---|---|---|---|
| **low** | 2 | 1 | 0 (snippet/abstract only) |
| **medium** *(recommended)* | all | 2 | 1 |
| **high** | all | 3 | 3 |

**Literature toolchain.** Paper search goes through the sibling **`literature-search` skill** — resolve
`<lit_skill_dir>` (it installs as a sibling, e.g. `~/.claude/skills/literature-search/`),
`<lit_py> = python3`, and `<lit> = <lit_skill_dir>/tools/lit_search.py` (note the `tools/`
segment); append `--cache-dir <sandbox_root>/literature/.cache` after a subcommand to reuse the cache.
Confirm `<lit> --help` works at setup; if the skill is absent, tell the user and either install it
(copy the repo's `loops/literature-search` folder into `~/.claude/skills/`) or degrade all retrieval to
WebSearch/WebFetch (tag that evidence `source:"web"`). The keyless S2 + arXiv core needs no setup; a
free `S2_API_KEY` makes `snippet`/`cite` reliable.

**API key (optional, never block).** The `literature-search` skill owns the key convention: run
`<lit> keys --init`, then have the user fill the printed `keys.env` themselves and never paste secrets
into chat. Re-run `<lit> keys` to record the tier in `loop.run.yaml` (`literature_tiers`, presence
only). A missing key just degrades to the keyless pool → WebSearch.

**Initialise the sandbox** once bindings are confirmed:
```
<sandbox_root>/
├── loop.run.yaml        ← resolved bindings + literature_tiers
├── ledger.tsv           ← header only (see Ledger)
└── literature/.cache/   ← lit_search on-disk cache
```
Start with an empty `pool` and `gaps` seeded from `<question>`; create no round files until the loop runs.

## The loop
`pool` = the kept hypotheses (starts empty). `gaps` = open questions the LiteratureScout has surfaced
(starts empty; seed from `<question>`). `dry` = consecutive rounds with no new keep (starts 0). `<N>`
starts at 1.

Copy this checklist and tick items off:
- [ ] **Generate** — run `roles/Generator.md` (spawn-or-degrade) with `<question>`, the current `pool`, `gaps`, and `<gen_n>`; it writes `round<N>/candidates.json` (`<gen_n>` specific, testable, plausibly-novel candidates aimed at the gaps, none duplicating the pool).
- [ ] **Ground** — run `roles/LiteratureScout.md` (spawn-or-degrade) on `candidates.json` with `<lit>` and the `<eval_scale>` caps; it writes `round<N>/litscout.json` (validates `schemas/litscout.schema.json`) — per candidate: novelty + closest prior work, support, gap, testability, each citing **real** evidence.
- [ ] **Judge** — as `roles/Judge.md`, apply the fixed rubric + evidence gate to `litscout.json`, checking each candidate against the `pool` for duplicates; write `round<N>/verdict.json` (validates `schemas/verdict.schema.json`): scores, `total`, `keep`, `duplicate_of`.
- [ ] **Update** — add every `keep:true` non-duplicate to `pool` (with scores + grounding + how-to-test); add this round's `gap` points to `gaps`. If ≥1 new keep, `dry = 0`; else `dry += 1`.
- [ ] **Log** one ledger row (see Ledger); `N = N + 1`.
- [ ] **Stop check** — `dry == <patience>` (saturation) or `N > <budget>` → stop (see Stops).

**Re-ground every round** — novelty is judged from a *fresh* literature check each round, never carried
over, so "the literature already covers this" reliably kills a crowded idea. Every cited snippet comes
from a real retrieval that round; on `{"error","fallback"}` fall back to WebSearch/WebFetch — never
invent a paper.

`schemas/litscout.schema.json` gates the LiteratureScout output — a generic instance:
```json
{"round": 2,
 "evaluations": [{"hid": "r2h1", "novelty_assessment": "novel",
   "closest_prior_work": [{"claim": "X tested for facts, not skills", "cites": ["E1"]}],
   "support": [{"claim": "spacing aids motor consolidation", "cites": ["E2"]}],
   "gap": [{"claim": "long-term procedural retention untested at scale", "cites": ["E1"]}],
   "testability_note": "RCT: spaced vs massed schedule, 1-month retention."}],
 "evidence": [{"key": "E1", "title": "...", "source": "s2", "id": "a1b2", "snippet": "...verbatim..."}]}
```
`schemas/verdict.schema.json` gates the Judge output — a generic instance:
```json
{"round": 2,
 "verdicts": [{"hid": "r2h1",
   "scores": {"novelty": 4, "grounding": 4, "testability": 5, "specificity": 4, "significance": 4},
   "total": 82.0, "keep": true, "gate_failures": [], "duplicate_of": null,
   "rationale": "Closest work shows X untested for skills -> novel; supported; clean RCT named."}]}
```

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text. Header:
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
Per-round `candidates.json` / `litscout.json` / `verdict.json` live in `round<N>/`. Report the **best**
state of the pool when stopping, not just the last round. Leave `ledger.tsv`, `round*/`, and
`literature/` untracked.

## Constraints
- **Never fabricate citations or snippets** — every evidence entry is a real `<lit>`/WebFetch retrieval
  from that round, verbatim; the evidence gate exists to catch fabrication.
- **Novelty is decided by the literature, not assertion** — a hypothesis the search shows is already
  established is killed, however appealing; "I think it's novel" with no closest-work search caps novelty.
- **Generate ≠ confirm** — kept hypotheses are strong *candidates to test*, each stated with its test;
  never report them as established findings.
- **The rubric is fixed** and the keep-bar is stable across rounds, so saturation is a meaningful stop.
- **Reward distinct hypotheses, not volume** — duplicates and rewordings are cut.
- **No installs** — the sibling `literature-search` skill is stdlib-only; never print or commit API keys
  (`keys.env` stays gitignored at the project root). The sandbox is self-contained — no `../` escapes.
- Do not pause the loop to ask whether to continue; run until saturation or budget.

## Stops
The loop stops on the first of:
- **Saturation** — `dry == <patience>` consecutive rounds add no new kept hypothesis.
- **Budget** — `<budget>` rounds reached.

End with the **ranked hypothesis set** (`<report>` path) — each hypothesis with its statement, novelty
assessment + closest prior work (cited), supporting evidence (cited), the gap it fills, and how to test
it — plus the pool-size trajectory from `ledger.tsv` and the **strongest unexplored gaps**, so the user
sees both the vetted hypotheses and where a deeper run would look next.
