#!/usr/bin/env python3
"""Objective code-quality metrics for changed files — stdlib only, 3.9-safe.

The swe-loop's QA agent uses this as the *objective* half of its quality gate (the
*qualitative* half is the judgement in rubrics/quality-rubric.md). It measures the
conciseness/readability signals the loop cares about — long comment blocks, oversized
functions, deep nesting, bloated files — so "simple, readable, well-organised" is backed
by numbers a model cannot wish away.

Usage:
    python3 quality_check.py <file> [<file> ...] \
        [--max-comment-block N] [--max-comment-line-len N] \
        [--max-func-loc N] [--max-nesting N] [--max-file-loc N]

Thresholds are optional. If a threshold is given and a file exceeds it, that file is a
violation, `ok` is false, and the script exits 1 (the loop treats it as a failed gate).
With no thresholds it just reports metrics and exits 0. A parse error on a .py file is
reported per-file and exits 2, so an unparseable change is a failed iteration, not a
silent pass.

Prints one JSON object to stdout:
    {"ok": bool,
     "violations": [{"path": str, "metric": str, "value": int, "limit": int}],
     "per_file": {"<path>": {"file_loc": int, "max_comment_block": int,
                              "long_comment_lines": int, "max_func_loc": int|null,
                              "max_nesting": int|null, "comment_ratio": float}},
     "thresholds": {...}}

- file_loc           : non-blank physical lines (proxy for file bloat).
- max_comment_block  : longest run of consecutive comment-only lines (catches "crazy long comments").
- long_comment_lines : count of comment lines longer than --max-comment-line-len.
- max_func_loc       : longest callable body in lines (.py only via AST; null otherwise).
- max_nesting        : deepest nesting of compound statements (.py only; null otherwise).
- comment_ratio      : comment lines / code lines (context; very high reads as over-commented).
"""

import argparse
import ast
import json
import sys

# Line-comment prefixes by extension, for the language-agnostic line pass.
_LINE_COMMENT = {
    ".py": "#", ".sh": "#", ".rb": "#", ".yaml": "#", ".yml": "#", ".toml": "#",
    ".js": "//", ".jsx": "//", ".ts": "//", ".tsx": "//", ".go": "//", ".rs": "//",
    ".java": "//", ".c": "//", ".h": "//", ".cpp": "//", ".hpp": "//",
}

_NESTERS = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try,
    ast.FunctionDef, ast.AsyncFunctionDef,
)


def _ext(path):
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 else ""


def _line_metrics(text, comment_prefix, max_comment_line_len):
    """Language-agnostic line metrics: loc, comment blocks, over-long comments, ratio."""
    file_loc = 0
    comment_lines = 0
    long_comment_lines = 0
    max_block = 0
    cur_block = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            cur_block = 0
            continue
        file_loc += 1
        is_comment = bool(comment_prefix) and line.startswith(comment_prefix)
        if is_comment:
            comment_lines += 1
            cur_block += 1
            max_block = max(max_block, cur_block)
            if max_comment_line_len is not None and len(raw) > max_comment_line_len:
                long_comment_lines += 1
        else:
            cur_block = 0
    code_lines = file_loc - comment_lines
    ratio = round(comment_lines / code_lines, 3) if code_lines else 0.0
    return {
        "file_loc": file_loc,
        "max_comment_block": max_block,
        "long_comment_lines": long_comment_lines,
        "comment_ratio": ratio,
    }


def _func_loc(node):
    lines = [node.lineno]
    for child in ast.walk(node):
        end = getattr(child, "end_lineno", None)
        if end is not None:
            lines.append(end)
    return max(lines) - node.lineno + 1


def _nesting(node, depth=0):
    deepest = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTERS) else depth
        deepest = max(deepest, _nesting(child, child_depth))
    return deepest


def _py_metrics(text):
    """AST metrics for Python: longest function body, deepest nesting."""
    tree = ast.parse(text)
    max_func = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            max_func = max(max_func, _func_loc(node))
    return {"max_func_loc": max_func, "max_nesting": _nesting(tree)}


def main():
    p = argparse.ArgumentParser(description="Objective code-quality metrics.")
    p.add_argument("files", nargs="+")
    p.add_argument("--max-comment-block", type=int, default=None)
    p.add_argument("--max-comment-line-len", type=int, default=None)
    p.add_argument("--max-func-loc", type=int, default=None)
    p.add_argument("--max-nesting", type=int, default=None)
    p.add_argument("--max-file-loc", type=int, default=None)
    args = p.parse_args()

    thresholds = {
        "max_comment_block": args.max_comment_block,
        "long_comment_lines": 0 if args.max_comment_line_len is not None else None,
        "max_func_loc": args.max_func_loc,
        "max_nesting": args.max_nesting,
        "file_loc": args.max_file_loc,
    }

    per_file = {}
    violations = []
    parse_error = False

    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            per_file[path] = {"error": "cannot read: %s" % exc}
            parse_error = True
            continue

        ext = _ext(path)
        metrics = _line_metrics(text, _LINE_COMMENT.get(ext, ""), args.max_comment_line_len)
        metrics["max_func_loc"] = None
        metrics["max_nesting"] = None
        if ext == ".py":
            try:
                metrics.update(_py_metrics(text))
            except SyntaxError as exc:
                per_file[path] = {"error": "syntax error: %s" % exc}
                parse_error = True
                continue
        per_file[path] = metrics

        # Compare against any provided thresholds.
        checks = [
            ("file_loc", args.max_file_loc),
            ("max_comment_block", args.max_comment_block),
            ("max_func_loc", args.max_func_loc),
            ("max_nesting", args.max_nesting),
        ]
        for metric, limit in checks:
            value = metrics.get(metric)
            if limit is not None and value is not None and value > limit:
                violations.append({"path": path, "metric": metric, "value": value, "limit": limit})
        if args.max_comment_line_len is not None and metrics["long_comment_lines"] > 0:
            violations.append({
                "path": path, "metric": "long_comment_lines",
                "value": metrics["long_comment_lines"], "limit": 0,
            })

    result = {
        "ok": not violations and not parse_error,
        "violations": violations,
        "per_file": per_file,
        "thresholds": {k: v for k, v in thresholds.items() if v is not None},
    }
    print(json.dumps(result, indent=2))
    if parse_error:
        sys.exit(2)
    sys.exit(0 if not violations else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — surface any failure as a non-zero gate, never a silent pass
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(2)
