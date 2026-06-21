---
name: literature-search
description: >
  Shared literature-search toolchain for the other loops — a self-contained, stdlib-only CLI
  (`lit_search.py`) over Semantic Scholar + arXiv (with optional OpenAlex, Perplexity Sonar, and
  bgpt.pro) that does semantic paper discovery, full-text snippet search, citation-graph traversal,
  single-paper full-text reads, landscape synthesis, and experimental-result extraction — all JSON.
  Not a loop itself: install it alongside the loops and let any of them (research-question,
  research-proposal, hypothesis-gen, literature-survey, scientific-writer, deep-agent, …) call it for
  paper search and novelty checks instead of vendoring their own copy. Degrades to the caller's
  WebSearch/WebFetch on failure.
metadata:
  version: "0.1.0"
---

# Literature Search (shared toolchain)

This skill is **not a loop** — it is the literature-retrieval dependency that several loops use
for paper discovery and novelty checks. It bundles `lit_search.py` (a stdlib-only entrypoint) and
the `lit/` package: Semantic Scholar (S2) for semantic search + snippets + the citation graph and
arXiv for full-text reads (the keyless core), plus optional OpenAlex (citation/recency-sorted
discovery), Perplexity Sonar (`ask`), and bgpt.pro (`bgpt`) when their keys are set. Every subcommand
prints JSON; on a terminal failure it prints `{"error","fallback"}` and exits non-zero so the calling
agent degrades to its built-in **WebSearch/WebFetch**. No installs, Python ≥3.9.

## How a loop uses it

A consuming loop resolves these once at setup and reuses them:
- **`<lit_skill_dir>`** — where this skill is installed. After the repo's install step
  (`cp -r loops/* ~/.claude/skills/`) it sits as a **sibling** of the calling loop, e.g.
  `~/.claude/skills/literatureSearch/` (adjust per host — see `docs/compatibility.md`).
- **`<lit_py>`** — `python3` (any ≥3.9 interpreter).
- **`<lit>`** — `<lit_py> <lit_skill_dir>/lit_search.py`. To reuse a cache across calls, append
  `--cache-dir <sandbox_root>/literature/.cache` **after the subcommand** (it is a per-subcommand
  flag, not global).

**If this skill is not installed** (or the path cannot be resolved), the caller falls back to its
own WebSearch/WebFetch — so depending on it never hard-breaks a loop; it only enriches it.

## Subcommands

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--year 2020-] [--min-citations N] [--limit N] [--source s2\|openalex\|both] [--sort relevance\|citations\|recent]` | semantic discovery — related papers (titles, TLDR, abstract, citations, arxiv_id). **Defaults to `--source s2`** (relevance); add `openalex`/`both` to widen discovery (OpenAlex adds citation/recency sorting via `--sort`) |
| `<lit> snippet "<q>" [--limit N]` | full-text passage search — pinpoint a verbatim fact/number without reading a paper |
| `<lit> cite <paperId> --direction references\|citations\|recommend` | walk the citation graph (backward / forward / "more like this") |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf]` | deep-read one paper's methods/results (HTML > LaTeX > PDF) |
| `<lit> ask "<question>" [--model sonar\|sonar-pro\|sonar-reasoning]` | Perplexity Sonar synthesis — a cited high-level answer (needs `OPENROUTER_API_KEY`; else use WebSearch) |
| `<lit> bgpt "<q>" [--num N] [--days-back N]` | bgpt.pro structured experimental-result/limitations extraction (free for 50 results, then `BGPT_API_KEY`) |
| `<lit> keys [--init]` | report which API keys are present (booleans only) |

The S2 + arXiv core (`search`/`snippet`/`cite`/`fulltext`) needs no keys. The optional extras
(`search --source openalex|both`, `ask`, `bgpt`) widen discovery and synthesis when their keys are set.

## API keys (optional, never block)

Keys live in one gitignored `keys.env` at the project root, shared by every skill (see
`docs/api-keys.md`). Run `<lit> keys` to see what is present; `<lit> keys --init` writes a
placeholder `keys.env` (append-only, never overwrites). All keys are **optional** — each feature
degrades cleanly without its key. Never paste a secret into chat; have the user edit `keys.env`.

- **`S2_API_KEY`** (free) — makes `search`/`snippet`/`cite` reliable (a dedicated 1 req/s instead of
  the saturated keyless pool). The one most worth setting.
- **`OPENALEX_EMAIL`** (free, any email) — OpenAlex "polite pool" for faster `--source openalex|both`.
- **`OPENROUTER_API_KEY`** (paid) — enables `ask` (Perplexity Sonar); without it `ask` is disabled.
- **`BGPT_API_KEY`** (free for 50 results, then paid) — enables `bgpt` beyond the free tier.

## Constraints
- **Stdlib only** — never add a dependency or assume one is installed; it must run under bare
  `python3`.
- **Self-contained** — everything lives under this folder; no `../` escapes.
- **Fail closed to a fallback** — on any source error, emit `{"error","fallback"}` and exit
  non-zero rather than raising, so callers can degrade cleanly.
