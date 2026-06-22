---
name: literature-survey
description: >
  Use when the user wants a structured, saturating literature survey on a question — not a one-shot
  summary, but an evidence/contradiction matrix (sources × claims) built by iterative search until
  coverage stops growing. Each round expands the search (new sub-topic queries plus citation-graph
  walks), admits new sources, extracts their claims with verbatim snippets, and records where every
  source stands on each claim (supports / contradicts / qualifies); the feedback signal is how many
  new matrix-changing sources a round adds, and it stops at saturation, patience, or budget. The
  output is the matrix plus a synthesis of consensus, disputes, and gaps, every cell backed by a real
  citation. Not for grading a written proposal against the literature (that is a proposal-evaluation
  task) and not for generating new hypotheses — this maps what the literature already says.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Literature Survey Loop

A **search → extract → map → expand** loop that builds an **evidence/contradiction matrix** and stops
at **saturation**. The artifact is the matrix (claims × sources, with each source's stance); the
feedback signal is how many **new, matrix-changing sources** a round adds — you keep expanding until
that falls below `<min_new>` for `<patience>` rounds. Unlike a one-shot summary, the loop deliberately
hunts **contradictions** and **gaps** and keeps pulling threads until the picture stops changing.

The discipline: every cell — a source's stance on a claim — is backed by a **verbatim snippet from a
real retrieval**. The value is not a tidy narrative; it is an honest map of where the literature
**agrees, disagrees, and is silent**.

## When to use
Use this for a multi-source survey of a question where the deliverable is a structured map of the
evidence, not a paragraph. Default: run the full expand→admit→map loop below until saturation. Escape
hatch: if the user wants only a quick scan, run round 0 (seed) alone and hand back the seed matrix. Not
for grading a written proposal against the literature, and not for proposing new hypotheses.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm every value plus the live/degraded literature tier before
creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<question>` | the survey question/topic, with any scope (years, sub-fields, inclusion criteria) | — | ask the user; restate the scope back for confirmation |
| `<eval_scale>` | depth per round (`low`/`medium`/`high`, see below) | `medium` | — |
| `<matrix>` | structured output matrix (validates `schemas/matrix.schema.json`); `survey.md` written alongside | `<sandbox_root>/matrix.json` | — |
| `<sandbox_root>` | where the matrix, `survey.md`, ledger, and lit cache live | `./sandbox` | — |
| `<budget>` | max rounds | 6 | — |
| `<patience>` | stop after this many consecutive "dry" rounds | 2 | — |
| `<min_new>` | saturation threshold — a round is "dry" if it adds fewer than this many new, matrix-changing sources | 2 | — |

**Evaluation depth dial** (`<eval_scale>` caps per round — queries · citation-walks · fulltext reads ·
new-source admit cap):

| preset | queries · walks | fulltext reads | new-source cap |
|---|---|---|---|
| **low** | 2 · 0 | 0 (snippet/abstract only) | ~6 |
| **medium** *(recommended)* | 4 · 1 | 1 | ~10 |
| **high** | 6 · ≥2 | 3 | ~16 |

**Literature toolchain.** Paper search goes through the sibling **`literature-search` skill**: resolve
`<lit_skill_dir>` (it installs as a sibling, default `~/.claude/skills/literature-search/`),
`<lit_py> = python3`, and `<lit> = <lit_skill_dir>/tools/lit_search.py` (note the `tools/`
segment); append `--cache-dir <sandbox_root>/literature/.cache` after a subcommand to reuse the cache.
Subcommands used here: `search "<q>"` (discover sources), `snippet "<q>"` (verbatim passage = the
evidence for a cell), `cite <paperId> --direction references|citations|recommend` (walk the citation
graph), `fulltext <arxivId>` (deep-read one key paper). Confirm `<lit> --help` works at setup; because
this loop *is* literature retrieval, do not silently proceed if the skill is missing — tell the user
and either install it or degrade all retrieval to **WebSearch/WebFetch** (no ranked snippets or
citation-graph expansion), tagging that evidence `source:"web"`.

**S2 key (optional, never block).** A free `S2_API_KEY` makes `snippet`/`cite` reliable. Run
`<lit> keys --init`, have the user fill the printed `keys.env` themselves, never paste secrets into
chat; a missing key just degrades to the keyless pool → WebSearch. Record presence (booleans only) in
`loop.run.yaml`.

## The loop
`matrix` = sources + claims + gaps (starts empty). `dry` = consecutive dry rounds (starts 0). `<N>`
starts at 0.

Copy this checklist and tick items off:
- [ ] **Round 0 — seed.** Decompose `<question>` into sub-topics; run one `<lit> search` each, admit the most relevant sources, extract each one's key claim(s) into the matrix with a verbatim `snippet`, note obvious gaps.
- [ ] **Expand.** Pick the least-covered sub-topics and open contradictions/gaps; run new `<lit> search` queries and walk the citation graph (`<lit> cite`) from the 1-2 most central papers. Honor the `<eval_scale>` caps.
- [ ] **Admit & extract.** Dedupe against existing `sources` (by title/id); for each genuinely new source extract its key claim(s) + a verbatim `snippet`.
- [ ] **Map.** For each claim, record where each relevant source stands — **supports / contradicts / qualifies** — with its snippet; set `is_contested` when sources both support and contradict; add newly-exposed `gaps`.
- [ ] **Saturation check.** Count new, matrix-changing sources this round: `dry += 1` if fewer than `<min_new>`, else `dry = 0`. Steer the next round at whatever is still thin.
- [ ] **Log** one ledger row; `N = N + 1`; stop on saturation (`dry == <patience>`) or `<budget>`.

On stop, write `<matrix>` (validates `schemas/matrix.schema.json`) and `survey.md` — a synthesis
organized as **consensus** (well-supported claims), **disputes** (the contested claims and who is on
each side), and **gaps** (open questions), each citing its sources, plus an honest **coverage note**
naming which sub-topics are well covered and which are thin.

The matrix is the schema-validated artifact; a compact generic instance (see
`schemas/matrix.schema.json`):
```json
{
  "question": "<question>",
  "sources": [{"key": "S1", "title": "...", "source": "s2", "id": "...", "year": 2022}],
  "claims": [{
    "claim_id": "C1", "statement": "...", "is_contested": true,
    "positions": [
      {"source_key": "S1", "stance": "supports",    "snippet": "verbatim passage ..."},
      {"source_key": "S3", "stance": "contradicts",  "snippet": "verbatim passage ..."}
    ]
  }],
  "gaps": ["open question the survey surfaced"]
}
```
`source` ∈ {`s2`, `arxiv`, `web`}; `stance` ∈ {`supports`, `contradicts`, `qualifies`}.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
round	queries	new_sources	total_sources	new_claims	contested	dry
```
Example:
```
round	queries	new_sources	total_sources	new_claims	contested	dry
0	4	7	7	9	1	0
1	5	5	12	4	2	0
2	4	1	13	0	2	1
3	4	0	13	0	2	2
```
Report the new-sources trajectory so the reader sees saturation actually happen, not just the final count.

## Constraints
- **Never fabricate.** Every source, claim snippet, and stance comes from a real `<lit>` / WebFetch
  retrieval that round, and snippets are verbatim; on `{"error","fallback"}`, use WebSearch/WebFetch
  and tag the evidence `source:"web"` — the verbatim-snippet rule is what makes the matrix trustworthy.
- **Map disagreement, do not smooth it.** When sources conflict, record the contradiction explicitly
  (`is_contested`, both snippets); surfacing disputes is the point, not picking a winner.
- **Saturation is measured, not guessed** — stop because new-sources-per-round actually fell below
  `<min_new>`, and report coverage honestly rather than implying completeness the search did not reach.
- **Dedupe sources** so "new sources" counts real additions, not re-finds of the same paper.
- **No installs** — the sibling `literature-search` skill is stdlib-only; never print or commit API keys
  (`keys.env` stays gitignored at the project root). The sandbox is self-contained — no `../` escapes.
- Do not pause the loop to ask whether to continue; run until saturation, patience, or budget.

## Stops
The loop stops on the first of:
- **Saturation** — `dry == <patience>` (each of those rounds added fewer than `<min_new>` new sources).
- **Budget** — `N == <budget>` rounds reached.

Always end with: the `<matrix>` path, the synthesis (consensus / disputes / gaps), the source count and
new-sources trajectory from `ledger.tsv` showing saturation, and the coverage note naming the thin spots.
