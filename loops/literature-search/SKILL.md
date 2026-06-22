---
name: literature-search
description: >
  Use when a loop needs scholarly literature — paper discovery, novelty checks, full-text snippet
  search, citation-graph traversal, single-paper reads, or experimental-result extraction. A shared,
  stdlib-only CLI (`tools/lit_search.py`) over Semantic Scholar + arXiv (plus optional OpenAlex,
  Perplexity Sonar, bgpt.pro), all JSON. Not a loop itself: install it alongside the loops and let any
  of them call it instead of vendoring their own copy. Degrades to the caller's WebSearch/WebFetch.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Literature Search (shared toolchain)

This skill is **not a loop** — it is the literature-retrieval dependency several loops use for paper
discovery and novelty checks. It bundles `tools/lit_search.py` (a stdlib-only entrypoint) and the
`tools/lit/` package: Semantic Scholar (S2) for semantic search + snippets + the citation graph and
arXiv for full-text reads (the keyless core), plus optional OpenAlex, Perplexity Sonar (`ask`), and
bgpt.pro (`bgpt`) when their keys are set. Every subcommand prints JSON; on a terminal failure it
prints `{"error","fallback"}` and exits non-zero so the caller degrades to its built-in
**WebSearch/WebFetch**. No installs, Python ≥3.9.

## How a loop uses it

A consuming loop resolves these once at setup and reuses them:
- **`<lit_skill_dir>`** — where this skill is installed. After `cp -r loops/* ~/.claude/skills/` it
  sits as a **sibling** of the calling loop, e.g. `~/.claude/skills/literature-search/` (adjust per
  host). If it cannot be resolved, the caller falls back to WebSearch/WebFetch — depending on it never
  hard-breaks a loop, it only enriches it.
- **`<lit>`** — the literature CLI as a **single command token**: `<lit_skill_dir>/tools/lit_search.py`.
  The entrypoint is executable and carries a `#!/usr/bin/env python3` shebang, so it runs directly with
  no `python3` prefix. To reuse a cache across calls, append `--cache-dir <sandbox_root>/literature/.cache`
  **after the subcommand** (a per-subcommand flag, not global).
- **`<lit_py>`** — only needed for the **fallback** form on a host that doesn't honour the execute bit:
  `<lit_py> <lit_skill_dir>/tools/lit_search.py`, with `<lit_py> = python3` (any ≥3.9 interpreter).

> **Invoke `<lit>` as one command — keep it a single shell token.** In particular **zsh does not
> word-split unquoted variables**, so storing the two-word `python3 .../lit_search.py` in a variable and
> calling `$VAR` tries to exec one long (nonexistent) filename. Use the executable single-token form
> above, call the script path directly, or split explicitly (`${=VAR}` in zsh).

## Subcommands

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--year 2020-] [--min-citations N] [--limit N] [--source s2\|openalex\|both] [--sort relevance\|citations\|recent]` | semantic discovery — related papers (titles, TLDR, abstract, citations, arxiv_id). Defaults to `--source s2` (relevance); add `openalex`/`both` to widen discovery |
| `<lit> snippet "<q>" [--limit N]` | full-text passage search — pinpoint a verbatim fact/number without reading a paper |
| `<lit> cite <paperId> --direction references\|citations\|recommend` | walk the citation graph (backward / forward / "more like this") |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf]` | deep-read one paper's methods/results (HTML > LaTeX > PDF) |
| `<lit> ask "<question>" [--model sonar\|sonar-pro\|sonar-reasoning]` | Perplexity Sonar synthesis — a cited high-level answer (needs `OPENROUTER_API_KEY`; else use WebSearch) |
| `<lit> bgpt "<q>" [--num N] [--days-back N]` | bgpt.pro structured experimental-result/limitations extraction (free for 50 results, then `BGPT_API_KEY`) |
| `<lit> keys [--init]` | report which API keys are present (booleans only); `--init` writes/extends `keys.env` |

The S2 + arXiv core (`search`/`snippet`/`cite`/`fulltext`) needs no keys. The optional extras
(`search --source openalex|both`, `ask`, `bgpt`) widen discovery and synthesis when their keys are set.

## API keys (the shared convention — optional, never block)

This skill is the canonical home for the project's key convention (it is the installed code that
implements it). Keys live in **one gitignored `keys.env` at the project root** (the nearest `.git`
ancestor of the working dir, else the CWD), shared by every skill in the project.

- Plain `KEY=VALUE` lines; `#` comments; blank lines ignored; `0600` perms.
- **A real OS environment variable always wins** over the file (CI/power users can just `export`).
- **All keys are optional** — a missing key degrades that one feature gracefully, down to WebSearch.
- **Secrets never enter the conversation** — the user edits `keys.env` themselves; skills read only
  presence as booleans, never values.

Onboarding flow: `<lit> keys` (report what's present) → `<lit> keys --init` (create/append slots,
append-only, never overwrites; prints the path) → user opens `keys.env` and pastes the keys they want
(in-session: `! $EDITOR ./keys.env`) → `<lit> keys` again, then proceed. Never block on keys.

- **`S2_API_KEY`** (free) — the one most worth setting; a dedicated 1 req/s for `search`/`snippet`/`cite`.
- **`OPENALEX_EMAIL`** (free, any email) — OpenAlex "polite pool" for faster `--source openalex|both`.
- **`OPENROUTER_API_KEY`** (paid) — enables `ask` (Perplexity Sonar); without it `ask` is disabled.
- **`BGPT_API_KEY`** (free for 50 results, then paid) — enables `bgpt` beyond the free tier.

## Constraints
- **Stdlib only** — never add a dependency or assume one is installed; it must run under bare `python3`.
- **Self-contained** — everything lives under this folder; no `../` escapes, no `docs/` links.
- **Fail closed to a fallback** — on any source error, emit `{"error","fallback"}` and exit non-zero
  rather than raising, so callers degrade cleanly.
