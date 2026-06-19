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


def _reconstruct_abstract(inv_index):
    """OpenAlex returns abstracts as an inverted index {word: [positions]} (not
    plaintext, for licensing reasons). Rebuild the prose by placing each word at its
    positions and joining in order."""
    if not inv_index:
        return None
    positions = {}
    for word, idxs in inv_index.items():
        for i in idxs:
            positions[i] = word
    text = " ".join(positions[i] for i in sorted(positions))
    return text[:1200] or None


def from_openalex(w):
    ids = w.get("ids") or {}
    doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
    loc = w.get("primary_location") or {}
    source_obj = loc.get("source") or {}
    # OpenAlex has no dedicated arXiv field — sniff it out of the landing-page URL.
    arxiv_id = None
    for cand in (loc.get("landing_page_url"), ids.get("openalex")):
        if cand and "arxiv.org" in cand:
            m = re.search(r"arxiv\.org/abs/([0-9.]+)", cand)
            if m:
                arxiv_id = m.group(1)
    return _paper(
        source="openalex",
        paper_id=(ids.get("openalex") or "").split("/")[-1] or None,
        title=w.get("title"),
        authors=[
            (a.get("author") or {}).get("display_name")
            for a in (w.get("authorships") or [])
        ][:6],
        year=w.get("publication_year"),
        venue=source_obj.get("display_name"),
        citations=w.get("cited_by_count"),
        abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
        arxiv_id=arxiv_id,
        doi=doi,
        pdf_url=loc.get("pdf_url"),
    )


def dedupe(papers, limit):
    """Merge across sources by DOI then normalized title. First occurrence wins, so
    callers should place the higher-trust source (Semantic Scholar) first."""
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
