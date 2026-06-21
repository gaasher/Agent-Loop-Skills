"""argparse dispatch for the lit_search CLI. Each subcommand calls a source function
and prints JSON. On terminal failure it prints {"error","fallback"} and exits non-zero
so the agent degrades to its built-in WebSearch / WebFetch.
"""

import argparse
import json
import os
import sys

from . import http, keys
from .normalize import dedupe
from .sources import arxiv, semantic_scholar as s2

FALLBACK = "Fall back to your built-in WebSearch / WebFetch tools."


def _emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _fail(msg, fallback=FALLBACK):
    print(json.dumps({"error": msg, "fallback": fallback}, indent=2))
    sys.exit(1)


def _search(a):
    try:
        papers = s2.search(a.query, a.limit, a.year, a.min_citations, a.open_access)
    except RuntimeError as e:
        _fail("Semantic Scholar failed: {}".format(e))
        return
    papers = dedupe(papers, a.limit)
    _emit({"query": a.query, "count": len(papers), "results": papers})


def _snippet(a):
    _emit({"query": a.query, "snippets": s2.snippet(a.query, a.limit)})


def _cite(a):
    _emit({"seed": a.paper_id, "direction": a.direction,
           "results": s2.cite(a.paper_id, a.direction, a.limit, a.influential_only)})


def _fulltext(a):
    _emit(arxiv.fulltext(a.ref, a.mode, a.section, a.out_dir))


def _keys(a):
    path = a.env_file or keys.default_env_path()
    if a.init:
        keys.ensure_template(path)
    out = {"env_file": path}
    out.update(keys.report())
    _emit(out)


def _build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cache-dir", default=None,
                        help="on-disk cache dir (recommended: <sandbox>/literature/.cache)")
    common.add_argument("--env-file", default=None,
                        help="key file to load (default: keys.env at the project/repo root)")

    p = argparse.ArgumentParser(
        prog="lit_search",
        description="Self-contained literature search (stdlib only, Python >=3.9).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", parents=[common],
                        help="semantic discovery (Semantic Scholar)")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=12)
    sp.add_argument("--year", help='e.g. "2020-" or "2018-2023"')
    sp.add_argument("--min-citations", type=int, default=0)
    sp.add_argument("--open-access", action="store_true", help="only papers with a free PDF")
    sp.set_defaults(func=_search)

    sp = sub.add_parser("snippet", parents=[common],
                        help="full-text passage search across the corpus (pinpoint facts)")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.set_defaults(func=_snippet)

    sp = sub.add_parser("cite", parents=[common], help="follow the citation graph")
    sp.add_argument("paper_id", help="Semantic Scholar paperId (seed)")
    sp.add_argument("--direction", choices=["references", "citations", "recommend"],
                    default="references")
    sp.add_argument("--limit", type=int, default=15)
    sp.add_argument("--influential-only", action="store_true")
    sp.set_defaults(func=_cite)

    sp = sub.add_parser("fulltext", parents=[common],
                        help="read a specific paper (HTML > LaTeX > PDF)")
    sp.add_argument("ref", help="arXiv id, arxiv URL, or .pdf URL")
    sp.add_argument("--mode", choices=["auto", "latex", "pdf"], default="auto")
    sp.add_argument("--section", help="latex mode: keyword to match section titles")
    sp.add_argument("--out-dir", default=None)
    sp.set_defaults(func=_fulltext)

    sp = sub.add_parser("keys", parents=[common],
                        help="report which API keys are present (booleans only)")
    sp.add_argument("--init", action="store_true",
                    help="write a placeholder keys.env at --env-file if missing")
    sp.set_defaults(func=_keys)

    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    keys.load_env_file(args.env_file)
    http.configure(cache_dir=args.cache_dir)
    try:
        args.func(args)
    except RuntimeError as e:
        _fail(str(e))


if __name__ == "__main__":
    main()
