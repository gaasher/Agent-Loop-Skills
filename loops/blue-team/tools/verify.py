#!/usr/bin/env python3
"""Verify a patched target against a failure catalogue; report per-class status + regressions.

The blue-team loop uses this as its objective signal — the inverse of red-team's `harness.py`. Where
the attacker counts *new* failure classes, the fixer counts how many catalogue classes a patch has
*closed*, and whether the patch broke anything that previously worked. Two sources of failed cases, one
output shape:

  oracle mode (--target + --oracle, from red-team): each command reads one input on stdin and prints a
    verdict (e.g. BLOCK/ALLOW). A catalogue item is closed when target now AGREES with the oracle on it;
    a holdout item that newly DISAGREES is a regression.

  tests mode (--test-cmd + --junit, from CI/CD): the test command runs the suite and writes a JUnit XML
    report; a catalogue item (a failing test id) is closed when its test now PASSES, and any test NOT in
    the catalogue that is now failing is a regression (a previously-passing test the fix broke).

In both modes a `class` is CLOSED only when EVERY catalogue item of that class is resolved; if even one
is still failing the class is OPEN. That matches the loop's metric: drive the open-class count to zero.

Usage:
    # oracle mode
    python3 verify.py --target "<cmd>" --oracle "<cmd>" --catalogue failures.jsonl [--holdout benign.jsonl]
    # tests mode
    python3 verify.py --test-cmd "<cmd that writes JUnit>" --junit report.xml --catalogue failing.jsonl

Prints one JSON object:
    {"mode", "tested", "open_classes", "closed_classes", "open_count", "closed_count",
     "regressions", "regression_count", "still_failing"}
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

# Per-command wall-clock caps. The stdin verdict cap matches red-team/harness.py; the test-suite cap is
# larger because a whole suite runs at once.
VERDICT_TIMEOUT_S = 15
TEST_TIMEOUT_S = 300


def verdict(cmd, text):
    """Run `cmd` with `text` on stdin; return its upper-cased one-token verdict, or an ERROR marker."""
    try:
        proc = subprocess.run(
            shlex.split(cmd), input=text, capture_output=True, text=True, timeout=VERDICT_TIMEOUT_S
        )
        return proc.stdout.strip().upper() or "ERROR"
    except (subprocess.SubprocessError, OSError) as exc:
        return "ERROR:%s" % exc


def load_jsonl(path, label):
    """Load a JSONL file into a list of dicts. Missing file -> []; a bad line is skipped with a note."""
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                sys.stderr.write("skip malformed %s line %d: %s\n" % (label, n, exc))
    return out


def kind_of(target, oracle):
    """Classify a disagreement the same way harness.py does."""
    if target == "ALLOW" and oracle == "BLOCK":
        return "bypass"     # let through what should be stopped
    if target == "BLOCK" and oracle == "ALLOW":
        return "overblock"  # stopped what should be allowed
    return "error"          # one side errored / non-binary verdict


def empty_dry(mode, path):
    return {
        "mode": mode, "tested": 0, "open_classes": [], "closed_classes": [], "open_count": 0,
        "closed_count": 0, "regressions": [], "regression_count": 0, "still_failing": [],
        "note": "catalogue empty or unreadable at %s" % path,
    }


def summarize(mode, classes, still_failing, regressions, tested):
    """Shared output builder. `classes` maps class -> {"open": bool}."""
    open_classes = sorted(cls for cls, s in classes.items() if s["open"])
    closed_classes = sorted(cls for cls, s in classes.items() if not s["open"])
    return {
        "mode": mode,
        "tested": tested,
        "open_classes": open_classes,
        "closed_classes": closed_classes,
        "open_count": len(open_classes),
        "closed_count": len(closed_classes),
        "regressions": regressions,
        "regression_count": len(regressions),
        "still_failing": still_failing[:5],
    }


def run_oracle_mode(args):
    catalogue = load_jsonl(args.catalogue, "catalogue")
    if not catalogue:
        return empty_dry("oracle", args.catalogue)

    classes = {}
    still_failing = []
    for c in catalogue:
        cls = c.get("class", "unlabeled")
        text = c.get("text", "")
        slot = classes.setdefault(cls, {"open": False})
        t = verdict(args.target, text)
        o = verdict(args.oracle, text)
        if t != o:
            slot["open"] = True
            still_failing.append({
                "id": c.get("id"), "text": text, "class": cls,
                "kind": kind_of(t, o), "target": t, "oracle": o,
            })

    # A regression is any holdout item the patched target now gets wrong (most often a new over-block).
    regressions = []
    holdout = load_jsonl(args.holdout, "holdout")
    for h in holdout:
        text = h.get("text", "")
        t = verdict(args.target, text)
        o = verdict(args.oracle, text)
        if t != o:
            regressions.append({
                "id": h.get("id"), "text": text, "class": h.get("class", "regression"),
                "kind": kind_of(t, o), "target": t, "oracle": o,
            })

    return summarize("oracle", classes, still_failing, regressions, len(catalogue) + len(holdout))


def parse_junit(path):
    """Return {test_id: passed_bool} from a JUnit XML report. id = '<classname>.<name>'."""
    if not os.path.exists(path):
        raise SystemExit("verify.py: JUnit report not found at %s (did --test-cmd write it?)" % path)
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    status = {}
    for suite in suites:
        for tc in suite.findall("testcase"):
            test_id = ("%s.%s" % (tc.get("classname", ""), tc.get("name", ""))).strip(".")
            failed = tc.find("failure") is not None or tc.find("error") is not None
            status[test_id] = not failed  # skipped/passed both count as "not failing"
    return status


def run_tests_mode(args):
    catalogue = load_jsonl(args.catalogue, "catalogue")
    if not catalogue:
        return empty_dry("tests", args.catalogue)

    # Run the suite; we read pass/fail from the JUnit report it writes, not from the exit code.
    try:
        subprocess.run(shlex.split(args.test_cmd), capture_output=True, text=True, timeout=TEST_TIMEOUT_S)
    except (subprocess.SubprocessError, OSError) as exc:
        raise SystemExit("verify.py: test command failed to run: %s" % exc)

    status = parse_junit(args.junit)
    catalogue_ids = {c.get("test") for c in catalogue}

    classes = {}
    still_failing = []
    for c in catalogue:
        cls = c.get("class", "unlabeled")
        test_id = c.get("test")
        slot = classes.setdefault(cls, {"open": False})
        passed = status.get(test_id, False)  # missing from report = treat as still failing
        if not passed:
            slot["open"] = True
            still_failing.append({"id": c.get("id"), "test": test_id, "class": cls})

    # A regression is any test the fix newly broke: failing now AND not one of the cases we set out to fix.
    regressions = [
        {"test": tid, "class": "regression"}
        for tid, passed in sorted(status.items())
        if not passed and tid not in catalogue_ids
    ]

    return summarize("tests", classes, still_failing, regressions, len(status))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalogue", required=True, help="failures to close, JSONL")
    # oracle mode
    ap.add_argument("--target", help="oracle mode: patched system under test (reads stdin)")
    ap.add_argument("--oracle", help="oracle mode: frozen ground-truth verdict (reads stdin)")
    ap.add_argument("--holdout", help="oracle mode: benign/known-good inputs that must keep passing")
    # tests mode
    ap.add_argument("--test-cmd", dest="test_cmd", help="tests mode: command that runs the suite + writes JUnit")
    ap.add_argument("--junit", help="tests mode: path to the JUnit XML the test command writes")
    args = ap.parse_args(argv)

    if args.test_cmd or args.junit:
        if not (args.test_cmd and args.junit):
            ap.error("tests mode needs both --test-cmd and --junit")
        result = run_tests_mode(args)
    elif args.target and args.oracle:
        result = run_oracle_mode(args)
    else:
        ap.error("choose a mode: oracle (--target + --oracle) or tests (--test-cmd + --junit)")

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
