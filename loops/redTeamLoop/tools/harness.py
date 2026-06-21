#!/usr/bin/env python3
"""Run adversarial candidates against a target + a ground-truth oracle; log distinct failures.

The redTeamLoop uses this as its objective signal. For each candidate message it runs the
target command and the oracle command (each reads the message on stdin and prints a verdict
such as BLOCK/ALLOW), and records a FAILURE whenever they disagree:
  - target ALLOW / oracle BLOCK -> "bypass"      (target let through what it should stop)
  - target BLOCK / oracle ALLOW -> "overblock"   (target stopped what it should allow)
Failures are appended to a log and de-duplicated by the candidate's `class` label, so the
loop can count DISTINCT failure classes and stop when a round surfaces no new class.

Usage:
    python3 harness.py --target "<cmd>" --oracle "<cmd>" --inputs candidates.jsonl --log failures.jsonl

candidates.jsonl: {"id", "text", "class"}  (class = the technique/label you are testing)
Prints one JSON object:
    {"tested", "failures_this_run", "new_classes", "total_classes", "examples"}
"""

import argparse
import json
import os
import shlex
import subprocess
import sys


def verdict(cmd, text):
    try:
        proc = subprocess.run(
            shlex.split(cmd), input=text, capture_output=True, text=True, timeout=15
        )
        return proc.stdout.strip().upper() or "ERROR"
    except (subprocess.SubprocessError, OSError) as exc:
        return "ERROR:%s" % exc


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args(argv)

    prior = load_jsonl(args.log)
    seen_classes = {row.get("class") for row in prior}

    candidates = load_jsonl(args.inputs)
    new_failures = []
    for c in candidates:
        text = c.get("text", "")
        t = verdict(args.target, text)
        o = verdict(args.oracle, text)
        if t == o:
            continue
        kind = "bypass" if (t == "ALLOW" and o == "BLOCK") else (
            "overblock" if (t == "BLOCK" and o == "ALLOW") else "error")
        new_failures.append({
            "id": c.get("id"), "text": text, "class": c.get("class", "unlabeled"),
            "kind": kind, "target": t, "oracle": o,
        })

    # Append this run's failures to the log.
    with open(args.log, "a", encoding="utf-8") as fh:
        for f in new_failures:
            fh.write(json.dumps(f) + "\n")

    run_classes = {f["class"] for f in new_failures}
    new_classes = sorted(run_classes - seen_classes)
    total_classes = sorted(seen_classes | run_classes)
    print(json.dumps({
        "tested": len(candidates),
        "failures_this_run": len(new_failures),
        "new_classes": new_classes,
        "total_classes": total_classes,
        "examples": new_failures[:5],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
