#!/usr/bin/env python3
"""Static complexity metrics for Python files — stdlib only, 3.9-safe.

The optimize-loop uses this as its objective feedback signal in code mode: the loop keeps a
refactor only when the test suite stays green AND the `complexity` reported here drops.
Lower is better.

Usage:
    python3 metrics.py <file.py> [<file2.py> ...]

Prints one JSON object to stdout:
    {"complexity": int, "max_nesting": int, "loc": int, "functions": int,
     "per_file": {"<path>": {...}, ...}}

- complexity   : summed cyclomatic complexity (decision points + 1 per callable),
                 the primary signal the loop minimizes.
- max_nesting  : deepest nesting of compound statements inside any function (tie-breaker).
- loc          : non-blank, non-comment physical source lines (tie-breaker).
- functions    : number of def/async def (context, not optimized directly).

On a parse error it reports the file with an "error" field and a non-zero exit, so the
loop treats an unparseable refactor as a failed iteration rather than a silent zero.
"""

import ast
import json
import sys

# Nodes that each add one independent path through a callable (radon-style).
# `match` (ast.Match) only exists on py3.10+; guard so this stays 3.9-safe.
_MATCH = getattr(ast, "Match", ())

_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,          # ternary
    ast.ExceptHandler,
    ast.With,           # context entry is a branch point for our purposes
    ast.AsyncWith,
    ast.Assert,
    ast.comprehension,  # each `for` clause in a comprehension
) + ((_MATCH,) if _MATCH else ())

# Compound statements that increase nesting depth.
_NESTERS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)


def _complexity(tree):
    """Cyclomatic complexity over a parsed module: 1 per callable + decision points."""
    score = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score += 1
        elif isinstance(node, _BRANCH_NODES):
            score += 1
        elif isinstance(node, ast.BoolOp):
            # `a and b and c` adds 2 paths beyond the first operand.
            score += len(node.values) - 1
    return score


def _max_nesting(node, depth=0):
    deepest = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTERS) else depth
        deepest = max(deepest, _max_nesting(child, child_depth))
    return deepest


def _loc(source):
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _functions(tree):
    return sum(
        1
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def analyze(path):
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    return {
        "complexity": _complexity(tree),
        "max_nesting": _max_nesting(tree),
        "loc": _loc(source),
        "functions": _functions(tree),
    }


def main(argv):
    if not argv:
        print(json.dumps({"error": "usage: metrics.py <file.py> [...]"}))
        return 2

    per_file = {}
    totals = {"complexity": 0, "max_nesting": 0, "loc": 0, "functions": 0}
    had_error = False

    for path in argv:
        try:
            result = analyze(path)
        except (OSError, SyntaxError) as exc:
            per_file[path] = {"error": str(exc)}
            had_error = True
            continue
        per_file[path] = result
        totals["complexity"] += result["complexity"]
        totals["max_nesting"] = max(totals["max_nesting"], result["max_nesting"])
        totals["loc"] += result["loc"]
        totals["functions"] += result["functions"]

    out = dict(totals)
    out["per_file"] = per_file
    print(json.dumps(out))
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))