#!/usr/bin/env python3
"""Benchmark a SQLite query: wall-clock latency + a result-set fingerprint.

The queryOptimizeLoop uses this as its objective signal. A candidate query is only kept
when it is FASTER (lower `median_ms`) AND returns the SAME rows (matching `hash`) as the
baseline — so a "faster" query that silently changes results is rejected.

Usage:
    python3 bench.py --db DB.sqlite --query query.sql [--setup indexes.sql] [--repeat 5]

- Runs against a throwaway COPY of --db, so optional --setup DDL (e.g. CREATE INDEX) does
  not mutate the seed database and each measurement starts from the same clean state.
- Times only query execution + row fetch (the copy and any --setup run outside the timer),
  taking the median over --repeat runs after one warm-up.
- The fingerprint is sha256 over the multiset of rows (sorted), so a different ROW ORDER
  does not by itself count as different results. If ordering is part of the contract, the
  loop must check the ORDER BY separately (noted in the SKILL).

Prints one JSON object:
    {"median_ms": float, "min_ms": float, "rows": int, "hash": "<sha256>"}
On a SQL error it prints {"error": "..."} and exits non-zero, so the loop treats a broken
candidate as a failed iteration rather than a phantom speedup.
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _fingerprint(rows):
    # Order-independent multiset hash: sort the repr of each row, then hash the joined list.
    encoded = "\n".join(sorted(repr(r) for r in rows)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bench(db_path, query_sql, setup_sql, repeat):
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(tmp_fd)
    try:
        shutil.copyfile(db_path, tmp_path)
        conn = sqlite3.connect(tmp_path)
        try:
            if setup_sql and setup_sql.strip():
                conn.executescript(setup_sql)
                conn.commit()

            cur = conn.cursor()

            # Warm-up (build page cache / query plan) — not timed.
            cur.execute(query_sql)
            warm_rows = cur.fetchall()
            fingerprint = _fingerprint(warm_rows)
            row_count = len(warm_rows)

            timings = []
            for _ in range(repeat):
                start = time.perf_counter()
                cur.execute(query_sql)
                cur.fetchall()
                timings.append((time.perf_counter() - start) * 1000.0)
            timings.sort()
            mid = timings[len(timings) // 2]
            return {
                "median_ms": round(mid, 3),
                "min_ms": round(timings[0], 3),
                "rows": row_count,
                "hash": fingerprint,
            }
        finally:
            conn.close()
    finally:
        os.remove(tmp_path)


def main(argv):
    parser = argparse.ArgumentParser(description="Benchmark a SQLite query.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--setup", default=None, help="optional DDL (e.g. CREATE INDEX) file")
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        query_sql = _read(args.query)
        setup_sql = _read(args.setup) if args.setup and os.path.exists(args.setup) else None
        result = bench(args.db, query_sql, setup_sql, args.repeat)
    except (OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
