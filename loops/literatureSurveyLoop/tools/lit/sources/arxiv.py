"""arXiv full-text retrieval. Prefers TEXT over PDF, in order:

  1. HTML  — resolve() returns html_url + ar5iv_url for the agent to WebFetch
             (best for reading Methods/Experiments/Results as sections).
  2. LaTeX — latex_sections() fetches the e-print tarball and extracts the source
             sections (the authoritative full text when no HTML rendering exists).
  3. PDF   — pdf() downloads the PDF for the agent's Read tool (last resort).

This preference is an internal implementation detail of how the agent reads papers.
"""

import gzip
import io
import os
import re
import tarfile
import urllib.parse
import xml.etree.ElementTree as ET

from ..http import download, get_bytes

ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}

# Section titles worth extracting from LaTeX source when the agent wants the meat.
DEFAULT_SECTION_KEYWORDS = (
    "method", "approach", "model", "architecture", "experiment",
    "result", "implementation", "training", "setup", "ablation", "evaluation",
)


def arxiv_id(ref):
    """Resolve an arXiv id from a bare id or an abs/pdf/html URL; else None."""
    ref = (ref or "").strip()
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/([0-9]+\.[0-9]+)", ref)
    if m:
        return m.group(1)
    m = re.match(r"^(\d{4}\.\d{4,5})(v\d+)?$", ref)
    if m:
        return m.group(1)
    return None


def _urls(aid):
    return {
        "html_url": "https://arxiv.org/html/{}".format(aid),
        "ar5iv_url": "https://ar5iv.org/abs/{}".format(aid),
        "eprint_url": "https://arxiv.org/e-print/{}".format(aid),
        "pdf_url": "https://arxiv.org/pdf/{}.pdf".format(aid),
    }


def _metadata(aid):
    q = urllib.parse.urlencode({"id_list": aid})
    feed = get_bytes("{}?{}".format(ARXIV_API, q), bucket="search").decode("utf-8", "replace")
    entry = ET.fromstring(feed).find("a:entry", _ATOM)
    if entry is None:
        return {}
    title = entry.findtext("a:title", default="", namespaces=_ATOM) or ""
    summary = entry.findtext("a:summary", default="", namespaces=_ATOM) or ""
    return {"title": re.sub(r"\s+", " ", title).strip(),
            "abstract": re.sub(r"\s+", " ", summary).strip()}


def resolve(ref):
    """auto mode: metadata + every full-text URL, no download. The agent should
    WebFetch html_url (then ar5iv_url) to read sections; fall back to latex/pdf."""
    aid = arxiv_id(ref)
    if not aid:
        raise RuntimeError(
            "'{}' is not an arXiv id/URL. For non-arXiv papers, read the pdf_url from "
            "`search` directly.".format(ref)
        )
    out = {"arxiv_id": aid}
    out.update(_metadata(aid))
    out.update(_urls(aid))
    out["read_hint"] = (
        "WebFetch html_url (fallback ar5iv_url) and ask for the Methods/Experiments "
        "and Results sections. If neither renders, run fulltext --mode latex."
    )
    return out


def _strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def _read_tex_files(blob):
    """Return {name: comment-stripped text} for every .tex file in the e-print payload
    (gzipped tar, single gzipped .tex, or plain)."""
    files = {}
    try:
        tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
    except tarfile.TarError:
        tf = None
    if tf is not None:
        for member in tf.getmembers():
            if member.isfile() and member.name.lower().endswith(".tex"):
                fobj = tf.extractfile(member)
                if fobj is not None:
                    files[member.name] = _strip_comments(fobj.read().decode("utf-8", "replace"))
        tf.close()
        if files:
            return files
    try:
        text = gzip.decompress(blob).decode("utf-8", "replace")
    except OSError:
        text = blob.decode("utf-8", "replace")
    return {"main.tex": _strip_comments(text)}


def _resolve_inputs(files):
    """Inline \\input/\\include references starting from the main document, so section
    bodies that were split across files are reunited with their \\section headers."""
    def lookup(ref):
        ref = ref.strip().strip('"')
        wanted = {ref, ref + ".tex", ref.split("/")[-1], ref.split("/")[-1] + ".tex"}
        for k in files:
            if k in wanted or k.split("/")[-1] in wanted:
                return k
        return None

    main = None
    for k, v in files.items():
        if "\\begin{document}" in v:
            main = k
            break
    if main is None:
        for k, v in files.items():
            if "\\documentclass" in v:
                main = k
                break
    if main is None:
        return "\n".join(files.values())

    seen = set()

    def expand(name, depth=0):
        if not name or name in seen or depth > 12:
            return ""
        seen.add(name)
        text = files.get(name, "")
        return re.sub(r"\\(?:input|include)\{([^}]*)\}",
                      lambda m: expand(lookup(m.group(1)), depth + 1), text)

    return expand(main)


def _full_source(blob):
    files = _read_tex_files(blob)
    if not files:
        return ""
    if len(files) == 1:
        return next(iter(files.values()))
    return _resolve_inputs(files)


def _sections(tex, keywords):
    """Return [(title, body)] for \\section's whose title matches any keyword."""
    matches = list(re.finditer(r"\\section\*?\{([^}]*)\}", tex))
    out = []
    for i, m in enumerate(matches):
        title = m.group(1)
        if not any(k in title.lower() for k in keywords):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
        out.append((re.sub(r"\s+", " ", title).strip(), tex[start:end].strip()))
    return out


def latex_sections(ref, keywords=None, out_dir="./literature/text"):
    aid = arxiv_id(ref)
    if not aid:
        raise RuntimeError("'{}' is not an arXiv id/URL.".format(ref))
    keywords = tuple(k.lower() for k in (keywords or DEFAULT_SECTION_KEYWORDS))
    blob = get_bytes(_urls(aid)["eprint_url"])
    tex = _full_source(blob)
    secs = _sections(tex, keywords)
    # If matched bodies are suspiciously small, extraction likely missed content
    # (e.g. unresolved includes) — fall back to the full source instead.
    if secs and sum(len(b) for _, b in secs) < 800:
        secs = []
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "arxiv_{}.txt".format(aid))
    if secs:
        body = "\n\n".join("## {}\n{}".format(t, b) for t, b in secs)
        matched = [t for t, _ in secs]
        note = "Matched sections only. Raw LaTeX (math as source)."
    else:
        # No section titles matched — hand back the whole source (truncated) so the
        # agent still has full text to work with.
        body = tex[:60000]
        matched = []
        note = "No section titles matched; full source (truncated). Raw LaTeX."
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(body)
    return {"arxiv_id": aid, "mode": "latex", "path": dest,
            "sections_matched": matched, "note": "Read this file. " + note}


def pdf(ref, out_dir="./literature/pdfs"):
    aid = arxiv_id(ref)
    os.makedirs(out_dir, exist_ok=True)
    if aid:
        url = _urls(aid)["pdf_url"]
        dest = os.path.join(out_dir, "arxiv_{}.pdf".format(aid))
    elif ref.startswith("http") and ref.lower().endswith(".pdf"):
        url = ref
        dest = os.path.join(out_dir, re.sub(r"\W+", "_", ref.split("/")[-1]) or "paper.pdf")
    else:
        raise RuntimeError("'{}' is not an arXiv id or a .pdf URL.".format(ref))
    download(url, dest)
    return {"arxiv_id": aid, "mode": "pdf", "path": dest, "pdf_url": url,
            "note": "Read this PDF with your Read tool (fallback after HTML/LaTeX)."}


def fulltext(ref, mode="auto", section=None, out_dir=None):
    if mode == "auto":
        return resolve(ref)
    if mode == "latex":
        return latex_sections(ref, [section] if section else None,
                              out_dir or "./literature/text")
    if mode == "pdf":
        return pdf(ref, out_dir or "./literature/pdfs")
    raise RuntimeError("unknown mode '{}' (use auto|latex|pdf)".format(mode))
