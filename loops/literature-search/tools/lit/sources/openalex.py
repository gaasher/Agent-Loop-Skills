"""OpenAlex: discovery with filtering by citation count, recency, and venue — the
complement to Semantic Scholar's relevance ranking. Keyless; set OPENALEX_EMAIL to
join the faster 'polite pool'.
"""

import os
import re
import urllib.parse

from ..http import request
from ..normalize import from_openalex

BASE = "https://api.openalex.org"


def search(query, limit=12, year=None, min_citations=0, sort="relevance"):
    params = {"search": query, "per-page": min(limit, 50)}
    filters = []
    if year:
        m = re.match(r"^(\d{4})?-?(\d{4})?$", year)
        if m:
            lo, hi = m.group(1), m.group(2)
            if lo:
                filters.append("from_publication_date:{}-01-01".format(lo))
            if hi:
                filters.append("to_publication_date:{}-12-31".format(hi))
    if min_citations:
        filters.append("cited_by_count:>{}".format(min_citations - 1))
    if filters:
        params["filter"] = ",".join(filters)
    if sort == "citations":
        params["sort"] = "cited_by_count:desc"
    elif sort == "recent":
        params["sort"] = "publication_date:desc"
    email = os.environ.get("OPENALEX_EMAIL")
    if email:
        params["mailto"] = email
    url = "{}/works?{}".format(BASE, urllib.parse.urlencode(params))
    data = request(url, bucket="search")
    return [from_openalex(w) for w in (data.get("results") or [])][:limit]
