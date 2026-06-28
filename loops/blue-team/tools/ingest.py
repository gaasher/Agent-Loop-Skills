#!/usr/bin/env python3
"""Normalize a failure source into a blue-team catalogue — so the loop points straight at failed cases.

The blue-team loop fixes a catalogue of known-failing cases. Those cases come from somewhere real; this
adapter turns the common sources into the one catalogue shape the loop reads, stdlib only:

  - red-team   : red-team's failures.jsonl (oracle disagreements) → catalogue of {id, text, class}
  - junit      : a CI/CD JUnit XML report (e.g. `pytest --junitxml`) → catalogue of {id, test, class}
                 for each FAILING testcase (a <testcase> with a <failure>/<error> child)
  - pytest-ids : a plain list of failing test node ids, one per line → {id, test, class}

A test id is "<classname>.<name>" (junit) or the raw node id (pytest-ids); the `class` is the failure
group the loop closes one at a time — derived from the test class/module unless you pass --class-from.

Usage:
    python3 ingest.py --from junit      --in report.xml     --out catalogue.jsonl
    python3 ingest.py --from red-team   --in failures.jsonl --out catalogue.jsonl
    python3 ingest.py --from pytest-ids --in failed.txt     --out catalogue.jsonl
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


def _derive_class(raw):
    """Group key from a test class/module name: drop a leading 'Test', lowercase. Empty -> 'misc'."""
    base = raw.split(".")[-1]
    if base.startswith("Test"):
        base = base[4:]
    return base.lower() or "misc"


def from_junit(path, class_from):
    rows = []
    root = ET.parse(path).getroot()
    # Accept either <testsuite> at the root or a <testsuites> wrapper.
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    for suite in suites:
        for tc in suite.findall("testcase"):
            if tc.find("failure") is None and tc.find("error") is None:
                continue  # only failing cases enter the catalogue
            classname = tc.get("classname", "")
            name = tc.get("name", "")
            test_id = ("%s.%s" % (classname, name)).strip(".")
            group = name if class_from == "name" else _derive_class(classname or name)
            rows.append({"id": test_id, "test": test_id, "class": group})
    return rows


def from_red_team(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                sys.stderr.write("skip malformed line %d: %s\n" % (n, exc))
                continue
            rows.append({
                "id": obj.get("id", "f%d" % n),
                "text": obj.get("text", ""),
                "class": obj.get("class", "unlabeled"),
            })
    return rows


def from_pytest_ids(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            nodeid = line.strip()
            if not nodeid or nodeid.startswith("#"):
                continue
            # "file.py::Class::test" -> group by the segment before the last "::" (class or file).
            parts = nodeid.split("::")
            group = _derive_class(parts[-2]) if len(parts) > 1 else _derive_class(parts[0])
            rows.append({"id": nodeid, "test": nodeid, "class": group})
    return rows


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="src", required=True,
                    choices=["red-team", "junit", "pytest-ids"])
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--class-from", choices=["classname", "name"], default="classname",
                    help="junit only: derive the failure class from the test's class (default) or name")
    args = ap.parse_args(argv)

    if not os.path.exists(args.inp):
        ap.error("input not found: %s" % args.inp)

    if args.src == "junit":
        rows = from_junit(args.inp, args.class_from)
    elif args.src == "red-team":
        rows = from_red_team(args.inp)
    else:
        rows = from_pytest_ids(args.inp)

    with open(args.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    classes = sorted({r["class"] for r in rows})
    print(json.dumps({"cases": len(rows), "classes": classes, "out": args.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
