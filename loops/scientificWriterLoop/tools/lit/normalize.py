"""Boundary 1: map every backend's raw response onto ONE paper dict, so the
orchestrator sees identical fields no matter which source answered.

The canonical shape:
    source, paper_id, title, authors, year, venue, citations,
    influential_citations, tldr, abstract, arxiv_id, doi, pdf_url
"""

import re


def _paper(**kw):
    base = {
        "source": None, "paper_id": None, "title": None, "authors": [],
        "year": None, "venue": None, "citations": None,
        "influential_citations": None, "tldr": None, "abstract": None,
        "arxiv_id": None, "doi": None, "pdf_url": None,
    }
    base.update(kw)
    return base


def from_s2(p):
    ext = p.get("externalIds") or {}
    tldr = p.get("tldr") or {}
    oa = p.get("openAccessPdf") or {}
    abstract = p.get("abstract") or None
    return _paper(
        source="semantic_scholar",
        paper_id=p.get("paperId"),
        title=p.get("title"),
        authors=[a.get("name") for a in (p.get("authors") or [])][:6],
        year=p.get("year"),
        venue=p.get("venue"),
        citations=p.get("citationCount"),
        influential_citations=p.get("influentialCitationCount"),
        tldr=tldr.get("text"),
        abstract=abstract[:1200] if abstract else None,
        arxiv_id=ext.get("ArXiv"),
        doi=ext.get("DOI"),
        pdf_url=oa.get("url"),
    )


def dedupe(papers, limit):
    """Drop duplicates by DOI then normalized title, preserving order (first wins)."""
    def key(p):
        doi = (p.get("doi") or "").lower()
        if doi:
            return doi
        return re.sub(r"\W+", "", (p.get("title") or "").lower())[:60]

    seen, out = set(), []
    for p in papers:
        k = key(p)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out[:limit]
