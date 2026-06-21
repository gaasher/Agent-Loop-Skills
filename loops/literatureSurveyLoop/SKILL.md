---
name: literature-survey-loop
description: >
  Use when the user wants a structured literature survey on a question — not a one-shot summary, but an
  evidence/contradiction matrix built by iterative search until coverage saturates. Each round expands
  the search (new sub-topic queries plus citation-graph walks from key papers), admits new sources,
  extracts their claims, and updates a matrix of which sources support, contradict, or qualify each
  claim — then steers the next round at the gaps and disputes. It stops when fresh rounds stop adding
  new sources or claims. The output is the matrix plus a synthesis of consensus, disputes, and gaps,
  every cell backed by a real citation. Bind it to your survey question at setup.
metadata:
  version: "0.1.0"
---

# Literature Survey Loop

A **search → extract → map → expand** loop that builds an **evidence/contradiction matrix** and stops at
**saturation**. The artifact is the matrix (claims × sources, with each source's stance); the feedback
signal is how many **new sources and new claims** a round adds — you keep expanding until that goes to
near zero. Unlike a one-shot summary, the loop deliberately hunts **contradictions** and **gaps** and
keeps pulling threads until the picture stops changing.

The discipline: every cell of the matrix — a source's stance on a claim — is backed by a **verbatim
snippet from a real retrieval**. The value is not a tidy narrative; it is an honest map of where the
literature **agrees, disagrees, and is silent**.

---

## 0. The literature toolchain (read once)

All literature access goes through the shared **`literature-search` skill** (`lit_search.py` over
Semantic Scholar + arXiv) — stdlib-only, not a copy vendored here:
- **`<lit_skill_dir>`** — where the `literature-search` skill is installed; after the repo install step
  it sits as a **sibling** of this loop, e.g. `~/.claude/skills/literatureSearch/` (adjust per host).
- **`<lit_py>`** — `python3`.
- **`<lit>`** — `<lit_py> <lit_skill_dir>/lit_search.py`. To reuse a cache across calls, append
  `--cache-dir <sandbox_root>/literature/.cache` **after the subcommand** (it is a per-subcommand flag,
  not global), e.g. `<lit> search "<q>" --cache-dir <sandbox_root>/literature/.cache`.

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--year 2018-] [--min-citations N] [--limit N]` | discover sources for a sub-topic |
| `<lit> snippet "<q>" [--limit N]` | pull a verbatim passage — the evidence for a matrix cell |
| `<lit> cite <paperId> --direction references\|citations\|recommend` | walk the citation graph to expand coverage |
| `<lit> fulltext <arxivId>` | deep-read one key paper when the abstract is not enough |
| `<lit> keys [--init]` | report which API keys are present (booleans only) |

On failure each prints `{"error","fallback"}` (exit non-zero) — then use **WebSearch/WebFetch** and tag
that evidence `source:"web"`. `S2_API_KEY` (free) makes `snippet`/`cite` reliable; optional, degrades.

**Check at setup whether the skill is installed** — probe `<lit_skill_dir>/lit_search.py`. Because this
loop's whole method is literature retrieval, do not silently fall back if it is missing — tell the user
and offer the choice:
- **Install it** (strongly recommended for this loop) — the repo install step
  (`cp -r agent-loop-skills/loops/* ~/.claude/skills/`, adjust per host), or just the one skill:
  `cp -r agent-loop-skills/loops/literatureSearch ~/.claude/skills/`. Then re-resolve `<lit_skill_dir>`.
- **Proceed without it** — the survey runs on the host's WebSearch/WebFetch only (substantially
  degraded: no ranked snippets or citation-graph expansion).

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm in one line, and skip to §2. Otherwise resolve each
binding, then write `loop.run.yaml`. **Detect host:** `AskUserQuestion` available → Claude Code (infer +
recommend); else ask as quoted plain-text prompts.

- **`<question>`** — the survey question/topic (and any scope: years, sub-fields, inclusion criteria).
- **`<eval_scale>`** — depth per round: `low` (2 queries · 0 fulltext · ~6 new sources cap), `medium`
  *(default)* (4 queries + 1 citation-walk · 1 fulltext · ~10), `high` (6 queries + citation-walks · 3
  fulltext · ~16).
- **`<matrix>`** — output matrix file (default `<sandbox_root>/matrix.json`, validates
  `schemas/matrix.schema.json`) and a human-readable `<sandbox_root>/survey.md`.
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (max rounds, default 6), **`<patience>`**
  (default 2 — stop after this many rounds that each add fewer than `<min_new>` new sources).
- **`<min_new>`** — the saturation threshold: a round is "dry" if it adds fewer than this many *new,
  matrix-changing* sources (default 2).

**S2 key onboarding (optional, never block):** `<lit> keys`; if absent, `<lit> keys --init` (append-only
`keys.env` at project root, gitignored) and ask the user to paste their free key (`! $EDITOR
./keys.env`) or "skip". Never ask for the secret in chat.

**Confirm and go.** Print the bindings + the live/degraded tier; create nothing until the user confirms
(skip only when `loop.run.yaml` existed). Initialise the ledger (§3) and an empty matrix.

---

## 2. The loop

`matrix` = sources + claims + gaps (starts empty). `dry` = consecutive dry rounds (starts 0).

**Round 0 — seed.** Decompose `<question>` into its main sub-topics. Run an initial `<lit> search` per
sub-topic, admit the most relevant sources, and extract each one's key claim(s) into the matrix with a
verbatim `snippet`. Record any obvious gaps.

### Each round N (until `dry == <patience>` or `N == <budget>`):

1. **Expand.** Pick the least-covered sub-topics and the open contradictions/gaps, and run **new
   queries** for them; also **walk the citation graph** (`<lit> cite`) from the 1–2 most central papers
   to reach work plain search missed. Honor the `<eval_scale>` caps.
2. **Admit & extract.** Dedupe against existing `sources` (by title/id). For each genuinely new source,
   extract its key claim(s) and a verbatim `snippet`.
3. **Map.** For each claim (new or existing), record where each relevant source stands —
   **supports / contradicts / qualifies** — with its snippet. Mark a claim `is_contested` when sources
   both support and contradict it. Add newly-exposed `gaps`.
4. **Saturation check.** Count the **new, matrix-changing sources** this round. If fewer than
   `<min_new>`, `dry += 1`; else `dry = 0`. Steer next round at whatever is still thin.
5. **Log** one ledger row (§3) and continue.

**Stop** on saturation (`dry == <patience>`) or `<budget>`. Write `<matrix>` (the JSON matrix) and
`survey.md`: a synthesis organized as **consensus** (well-supported claims), **disputes** (the contested
claims and who is on each side), and **gaps** (open questions), each citing the sources — plus an honest
**coverage note**: which sub-topics are well covered and which are thin, so the reader knows the map's edges.

---

## 3. Ledger

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

---

## 4. Hard constraints (never violate)
- **Never fabricate.** Every source, claim snippet, and stance comes from a real `lit_search.py` /
  WebFetch retrieval; snippets are verbatim. On `{"error","fallback"}`, use WebSearch/WebFetch.
- **Map disagreement, do not smooth it.** When sources conflict, record the contradiction explicitly
  (`is_contested`, both snippets) — surfacing disputes is the point, not picking a winner.
- **Saturation is measured, not guessed** — stop because new-sources-per-round actually fell, and report
  the coverage honestly rather than implying completeness the search did not reach.
- **Dedupe sources** so "new sources" counts real additions, not re-finds of the same paper.
- Do not install packages (`lit_search.py` is stdlib-only); never print/commit API keys. Self-contained
  folder — no `../` escapes. Do not pause the loop to ask whether to continue.

## 5. When the loop stops
End with: the `<matrix>` path, the synthesis (consensus / disputes / gaps), the source count and
new-sources trajectory (from `ledger.tsv`) showing saturation, and the coverage note naming the thin spots.
