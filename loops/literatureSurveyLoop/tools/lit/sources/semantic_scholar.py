"""Semantic Scholar: semantic relevance search (SPECTER2 + learned ranker), full-text
snippet search, and the citation graph (references / citations / recommendations).

Results stay in relevance order — semantic relevance is the priority here. Use OpenAlex
when you want citation- or recency-sorted discovery instead.

Keyless by default; set S2_API_KEY for a dedicated 1 req/s rate.
"""

import os
import urllib.parse

from ..http import request
from ..normalize import from_s2

GRAPH = "https://api.semanticscholar.org/graph/v1"
REC = "https://api.semanticscholar.org/recommendations/v1"

PAPER_FIELDS = ("title,abstract,tldr,year,citationCount,influentialCitationCount,"
                "venue,externalIds,openAccessPdf,authors.name")


def _headers():
    key = os.environ.get("S2_API_KEY")
    return {"x-api-key": key} if key else {}


def search(query, limit=12, year=None, min_citations=0, open_access=False):
    """Relevance search (kept in relevance order). Oversamples then filters by
    citations client-side, since the relevance endpoint has no minCitationCount param."""
    params = {"query": query, "fields": PAPER_FIELDS, "limit": min(max(limit * 3, limit), 100)}
    if year:
        params["year"] = year  # "2020-" or "2018-2023"
    if open_access:
        params["openAccessPdf"] = ""
    url = "{}/paper/search?{}".format(GRAPH, urllib.parse.urlencode(params))
    data = request(url, headers=_headers(), bucket="s2")
    papers = [from_s2(p) for p in (data.get("data") or [])]
    if min_citations:
        papers = [p for p in papers if (p.get("citations") or 0) >= min_citations]
    return papers[:limit]


def snippet(query, limit=10):
    """Full-text passage search — returns the exact snippets matching a query, for
    pinpoint facts (a hyperparameter value, a reported number) without reading a paper."""
    params = {"query": query, "limit": min(limit, 100)}
    url = "{}/snippet/search?{}".format(GRAPH, urllib.parse.urlencode(params))
    data = request(url, headers=_headers(), bucket="s2")
    out = []
    for item in (data.get("data") or []):
        sn = item.get("snippet") or {}
        paper = item.get("paper") or {}
        out.append({
            "text": sn.get("text"),
            "section": sn.get("snippetKind") or sn.get("section"),
            "paper_title": paper.get("title"),
            "paper_id": paper.get("paperId") or paper.get("corpusId"),
        })
    return out


def cite(paper_id, direction="references", limit=15, influential_only=False):
    """Follow the citation graph. direction:
        references  -> papers this one cites (foundations, go backward)
        citations   -> papers citing this one (improvements, go forward)
        recommend   -> S2's learned 'more like this'
    influential_only keeps just the edges S2 flags as influential."""
    if direction == "recommend":
        url = "{}/papers/forpaper/{}?fields={}&limit={}".format(
            REC, urllib.parse.quote(paper_id), PAPER_FIELDS, limit)
        data = request(url, headers=_headers(), bucket="s2")
        return [from_s2(p) for p in (data.get("recommendedPapers") or [])]

    if direction not in ("references", "citations"):
        raise RuntimeError("direction must be references|citations|recommend")
    nested = "citedPaper" if direction == "references" else "citingPaper"
    params = {
        "fields": "isInfluential," + PAPER_FIELDS,
        "limit": min(limit * 3 if influential_only else limit, 1000),
    }
    url = "{}/paper/{}/{}?{}".format(
        GRAPH, urllib.parse.quote(paper_id), direction, urllib.parse.urlencode(params))
    data = request(url, headers=_headers(), bucket="s2")
    out = []
    for item in (data.get("data") or []):
        if influential_only and not item.get("isInfluential"):
            continue
        paper = from_s2(item.get(nested) or {})
        paper["is_influential"] = item.get("isInfluential")
        out.append(paper)
    return out[:limit]
