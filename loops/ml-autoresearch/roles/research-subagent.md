# Role: literature research subagent

Used only when the loop's `<literature>` binding is `on`. For each research question in the planning
step, run a researcher. **Spawn** a real isolated subagent where the host supports it (Claude Code: the
`Agent`/Task tool, with `effort` set per the dial below); otherwise **degrade** to doing the funnel
inline in the same context. Either way it follows the same protocol and returns the same schema. Launch
the per-question subagents in one turn for parallelism.

## Contents
- [What to give the subagent](#what-to-give-the-subagent)
- [The retrieval funnel](#the-retrieval-funnel)
- [Reading full text](#reading-full-text)
- [Tool gotchas](#tool-gotchas)
- [Scaling dial](#scaling-dial)
- [Output contract](#output-contract)

## What to give the subagent
- the **question** and its `abstraction_level` (1 = high-level architecture/prior-art; 2 = specific
  micro-opt);
- the `<domain>` phrasing (seeds queries only; never a filter — cross-domain transfer is valuable);
- the resolved **`<lit>`** command — `<lit_skill_dir>/tools/lit_search.py` (note the `tools/`
  segment), plus `--cache-dir <sandbox_root>/literature/.cache` appended after the subcommand;
- its depth caps (rounds · papers · cite-hops) and `effort` from the dial (see below);
- the contents of `schemas/literature_schema.json` (the required return shape);
- the relevant analysis summary (the limitation this question came from).

The `<lit>` subcommands (all print JSON; on failure print `{"error","fallback"}` and exit non-zero —
then fall back to the host's WebSearch/WebFetch, never fabricate a citation):

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--source s2\|openalex\|both] [--year 2020-] [--min-citations N] [--limit N]` | **Discover** — ranked papers (title, TLDR, abstract, citations, arxiv_id). Pass **`--source both`** to widen across S2 + OpenAlex. |
| `<lit> snippet "<q>" [--limit N]` | **Pinpoint a fact** — exact full-text passages (a hyperparameter value, a reported number) without reading a whole paper. |
| `<lit> cite <paperId> --direction references\|citations\|recommend [--influential-only]` | **Expand** — walk the citation graph from an anchor paper. |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf] [--section <kw>]` | **Read a chosen paper** (see Reading full text). |
| `<lit> ask "<q>" [--model sonar\|sonar-pro]` | **Synthesize** a cited high-level answer (Level-1; needs OpenRouter key, else use WebSearch). |
| `<lit> bgpt "<q>"` | **Evidence** — structured experimental results / limitations (free 50, then key). |

## The retrieval funnel
The approved order — triage before you read:
```
1. DISCOVER   <lit> search --source both  → N papers (title, TLDR, abstract, citations, arxiv_id)
2. TRIAGE     read TLDRs/abstracts → pick the top-k promising   (no full text yet)
3. GO DEEPER  (by need, within depth caps)
     a. need a specific fact/number  → <lit> snippet  (passages across the corpus)
     b. need a paper's full method   → fulltext (HTML→LaTeX→PDF) of THAT paper
4. EXPAND     <lit> cite (references / citations / recommend) → walk from an anchor
```
**Tune the funnel to the level:**
- **Level 1** (landscape): `<lit> ask` (Sonar) first for a fast cited synthesis, then `search` for
  survey/landmark papers, then `cite` to walk to recent downstream work. Verify Sonar's citations
  through `search`/`fulltext`.
- **Level 2** (exact values): `snippet` first — it returns the exact passage with the number — then
  `fulltext` on the one or two papers that matter.

**Read methodology, not abstracts.** Triage on TLDR/abstract, but extract recipes from the
**Methods/Experiments/Results** sections. Prefer recent papers with strong reported results, high
citations, reputable venues. **Attribute every finding to a specific reported result** ("dataset X +
method Y → 85.3% on benchmark Z") — a recipe with no number behind it is weak evidence.

**Evidence corroboration (high / x-high).** For a top candidate, use `<lit> bgpt` to pull structured
experimental results / limitations and corroborate the finding's `reported_gain` and `has_ablation`.

**Depth caps** (from the dial): at most `<rounds>` tool calls; read at most `<papers>` papers' full
text; follow at most `<hops>` citation hops. Stop when caps are hit.

**Repetition guard:** if a search/snippet/cite returns the same or no new information as a prior call,
do not repeat it — change strategy (different query, source, or a citation hop) or stop. Identical
consecutive calls, or an A→B→A→B cycle, means you are stuck: stop and summarize what you have.

## Reading full text
Internal mechanic — never surface this to the user. To read a paper's Methods/Results, prefer text over
PDF, in order:
1. `fulltext <id>` (auto) returns `html_url` + `ar5iv_url` — **WebFetch the html_url** (fallback
   ar5iv_url) and ask for the Methods/Experiments and Results sections.
2. If neither HTML renders, `fulltext <id> --mode latex` extracts the source sections to a text file —
   **Read that file** (under `<sandbox_root>/literature/text/`).
3. Only if both fail, `fulltext <id> --mode pdf` downloads the PDF (`literature/pdfs/`) — **Read** it.

For one specific fact, prefer `snippet` over reading a whole paper.

## Tool gotchas
Verified — heed these:
- `cite`/`recommend` need a **Semantic Scholar** `paperId`. An **OpenAlex id will not resolve** — for
  OpenAlex/DOI-sourced papers, call `cite "DOI:10.xxxx/..."` or `cite "ARXIV:2010.11929"` (S2 accepts
  those prefixes).
- `fulltext` HTML/LaTeX is **arXiv-only**. For a non-arXiv but **open-access** paper, read its
  `pdf_url` (from `search`) via `fulltext --mode pdf <pdf_url>`. Paywalled: rely on abstract + `snippet`.
- **S2 is globally rate-limited to ~1 req/s** (shared across all S2 calls and all parallel subagents).
  Use **OpenAlex for breadth** (no such limit); reserve S2 for relevance ranking, `snippet`, and `cite`
  where it is uniquely valuable.

## Scaling dial
`<research_scale>` presets (countable caps; the orchestrator may bump one make-or-break question up a
tier):

| Preset | Questions/level | Subagents/Q | rounds · papers read · cite-hops | effort |
|---|---|---|---|---|
| **low** | 1–2 | 1 | 3 · 0 · 0 (TLDR triage only) | low |
| **medium** *(default)* | 2–3 | 1 | 8 · 3 · 1 | medium |
| **high** | 3–4 | 1–2 | 16 · 6 · 2 | high |
| **x-high** | 4–6 | 2 | 30 · 10+ · 3 (full influence crawl) | max |

## Output contract
Return an object validated against `schemas/literature_schema.json` — ranked findings (best first),
each with: claim, recipe (exact hyperparameters where the source gives them), evidence (strength /
agreement / ablation / reported gain), citations (with the supporting snippet), applicability, proposed
change, files-to-edit, how-to-verify, and a keep/reject verdict. A compact instance:
```json
{
  "iteration": 3,
  "research_scale": "medium",
  "findings": [{
    "question": "Does decoupled weight decay stabilise the large FC layer?",
    "abstraction_level": 2,
    "claim": "AdamW decouples weight decay from the gradient update, regularising large layers cleanly.",
    "recipe": {"optimizer": "AdamW", "weight_decay": "0.05"},
    "evidence": {"strength": "strong", "n_papers_agree": 2, "has_ablation": true,
                 "reported_gain": "+0.4 top-1 vs Adam+L2"},
    "citations": [{"title": "Decoupled Weight Decay Regularization", "arxiv_id": "1711.05101",
                   "year": 2017, "snippet": "AdamW ... improves generalization ..."}],
    "applicability_to_our_setup": "Our FC layer dominates grad norm; decoupled wd targets exactly that.",
    "proposed_change": "Switch the optimizer to AdamW with weight_decay=0.05.",
    "files_to_edit": ["train.py"],
    "how_to_verify": "FC L2 norm drops vs iter N-1; val/train gap narrows.",
    "verdict": "keep"
  }],
  "summary": "Decoupled weight decay is the highest-value lever for the FC-dominance pathology."
}
```
Findings only — raw search dumps are not the deliverable. An **empty `findings` array is a valid, honest
result** ("no compelling evidence"). The orchestrator (not the subagent) writes `corpus.tsv` and applies
the final evidence gate (SKILL.md step 2c), so verdicts stay consistent across questions.
