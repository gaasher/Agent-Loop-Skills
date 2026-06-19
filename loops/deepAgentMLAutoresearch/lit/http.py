"""HTTP plumbing shared by every source: backoff, per-operation throttle, on-disk
cache, and a uniform User-Agent. Source modules only build URLs and normalize results;
all the cross-cutting concerns live here.

3.9-safe: no PEP-604 unions, no match statements.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

USER_AGENT = "deepAgentMLAutoresearch/0.1 (agent-loop-skills lit_search.py)"

# Minimum seconds between calls in the same throttle bucket. Search endpoints are the
# rate-limited ones (Semantic Scholar caps unauthenticated search hard); metadata and
# downloads are cheaper. Tune via configure().
_MIN_INTERVAL = {"search": 1.0, "default": 0.2}

_CACHE_DIR = None
_LAST_CALL = {}  # bucket -> last call timestamp


def configure(cache_dir=None):
    """Point the cache at <sandbox>/literature/.cache (or wherever the CLI says)."""
    global _CACHE_DIR
    _CACHE_DIR = cache_dir
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)


def _throttle(bucket):
    interval = _MIN_INTERVAL.get(bucket, _MIN_INTERVAL["default"])
    last = _LAST_CALL.get(bucket, 0.0)
    wait = interval - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL[bucket] = time.time()


def _cache_key(method, url, body):
    raw = method + "\n" + url + "\n" + (json.dumps(body, sort_keys=True) if body else "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _cache_read(key):
    if not _CACHE_DIR:
        return None
    path = os.path.join(_CACHE_DIR, key + ".json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None
    return None


def _cache_write(key, value):
    if not _CACHE_DIR:
        return
    path = os.path.join(_CACHE_DIR, key + ".json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh)
    except OSError:
        pass


def request(url, method="GET", headers=None, body=None, bucket="default",
            cache=True, retries=4, backoff=2.0):
    """Issue a JSON request. Reads/writes the on-disk cache for idempotent reads,
    self-throttles per bucket, and retries 429/5xx with exponential backoff.

    Raises RuntimeError on terminal failure so the CLI can emit a clean fallback.
    """
    key = _cache_key(method, url, body)
    if cache:
        hit = _cache_read(key)
        if hit is not None:
            return hit

    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    last_err = None
    for attempt in range(retries):
        _throttle(bucket)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
            result = json.loads(raw) if raw else {}
            if cache:
                _cache_write(key, result)
            return result
        except urllib.error.HTTPError as e:
            last_err = "HTTP {}: {}".format(e.code, e.reason)
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
                last_err = "{} - {}".format(last_err, detail)
            except Exception:
                pass
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = "network error: {}".format(e)
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            break
        except ValueError as e:  # JSON decode
            last_err = "bad JSON from {}: {}".format(url, e)
            break
    raise RuntimeError(last_err or "request failed")


def get_bytes(url, bucket="default", retries=3, backoff=2.0):
    """Fetch raw bytes (XML feeds, e-print tarballs) for callers that parse or unpack
    the payload themselves. Not cached. Raises RuntimeError on terminal failure."""
    headers = {"User-Agent": USER_AGENT}
    last_err = None
    for attempt in range(retries):
        _throttle(bucket)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = str(e)
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            break
    raise RuntimeError("fetch failed for {}: {}".format(url, last_err))


def download(url, dest):
    """Write a binary file to dest (PDF — the full-text fallback after HTML and LaTeX
    source). Returns dest."""
    payload = get_bytes(url)
    with open(dest, "wb") as fh:
        fh.write(payload)
    return dest
