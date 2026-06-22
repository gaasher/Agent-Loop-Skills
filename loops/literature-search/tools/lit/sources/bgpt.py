"""bgpt.pro: structured extraction of raw experimental results (methods, sample sizes,
limitations, quality scores) — useful for the evidence-grading step. Free for the first
50 results, then set BGPT_API_KEY ($0.02/result).
"""

import os

from ..http import request

URL = "https://bgpt.pro/api/mcp-search"


def search(query, num=10, days_back=None):
    body = {"query": query, "num_results": num}
    if days_back:
        body["days_back"] = days_back
    key = os.environ.get("BGPT_API_KEY")
    if key:
        body["api_key"] = key  # the free tier works without a key
    data = request(URL, method="POST", body=body, bucket="search")
    return {"source": "bgpt", "results": data.get("results", data)}
