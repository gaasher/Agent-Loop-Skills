#!/usr/bin/env python3
"""Validate a plan-loop tasks.json: schema shape + dependency/coverage/sizing invariants.

This is the plan-loop's objective gate — the deterministic half of the feedback signal (the
principal-engineer critique is the qualitative half). It checks the structural contract in
schemas/plan.schema.json, then the things a schema can't express:
  - every id is unique; every reference (serves, depends_on, order) points at something real;
  - the dependency graph is a DAG (no cycles);
  - `order` is a permutation of all task ids that respects every dependency (deps come first);
  - coverage: every component is served by >=1 task, and every task serves >=1 real component;
  - sizing: tasks far outside the PR range are flagged (warning, not error — big tasks are allowed).

Stdlib only, 3.9-safe. Prints one JSON object: {ok, errors, warnings, stats}. Exit 0 if ok else 1.

Usage:
    python3 validate_plan.py --tasks tasks.json [--schema schemas/plan.schema.json] [--pr-min 40 --pr-max 400]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCHEMA = os.path.join(os.path.dirname(HERE), "schemas", "plan.schema.json")


# --- a tiny JSON-Schema subset validator (only the keywords plan.schema.json uses) ---------------
def validate_schema(node, schema, path, errors):
    t = schema.get("type")
    if t == "object":
        if not isinstance(node, dict):
            errors.append("%s: expected object" % path)
            return
        for req in schema.get("required", []):
            if req not in node:
                errors.append("%s: missing required field '%s'" % (path, req))
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in node:
                validate_schema(node[key], subschema, "%s.%s" % (path, key), errors)
    elif t == "array":
        if not isinstance(node, list):
            errors.append("%s: expected array" % path)
            return
        if len(node) < schema.get("minItems", 0):
            errors.append("%s: needs >= %d items, got %d" % (path, schema["minItems"], len(node)))
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(node):
                validate_schema(item, item_schema, "%s[%d]" % (path, i), errors)
    elif t == "string":
        if not isinstance(node, str):
            errors.append("%s: expected string" % path)
    elif t == "integer":
        if not isinstance(node, int) or isinstance(node, bool):
            errors.append("%s: expected integer" % path)
    elif t in ("number",):
        if not isinstance(node, (int, float)) or isinstance(node, bool):
            errors.append("%s: expected number" % path)
    if "enum" in schema and node not in schema["enum"]:
        errors.append("%s: '%s' not one of %s" % (path, node, schema["enum"]))


# --- semantic invariants the schema can't express ------------------------------------------------
def find_cycle(adj):
    """Return a list describing a cycle in the dependency graph, or [] if acyclic (DFS, 3-color)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    stack_path = []

    def dfs(n):
        color[n] = GRAY
        stack_path.append(n)
        for m in adj.get(n, []):
            if m not in color:
                continue  # dangling dep reported elsewhere
            if color[m] == GRAY:
                i = stack_path.index(m)
                return stack_path[i:] + [m]
            if color[m] == WHITE:
                c = dfs(m)
                if c:
                    return c
        color[n] = BLACK
        stack_path.pop()
        return []

    for n in adj:
        if color[n] == WHITE:
            c = dfs(n)
            if c:
                return c
    return []


def semantic_checks(plan, pr_min, pr_max, errors, warnings, stats):
    tasks = plan.get("tasks", [])
    components = plan.get("components", [])
    order = plan.get("order", [])

    task_ids = [t.get("id") for t in tasks]
    comp_ids = {c.get("id") for c in components}

    # unique task ids
    seen = set()
    for tid in task_ids:
        if tid in seen:
            errors.append("duplicate task id '%s'" % tid)
        seen.add(tid)
    task_id_set = set(task_ids)

    # references: serves -> components, depends_on -> tasks
    served = set()
    adj = {tid: [] for tid in task_ids}
    for t in tasks:
        tid = t.get("id")
        for c in t.get("serves", []):
            if c not in comp_ids:
                errors.append("task %s serves unknown component '%s'" % (tid, c))
            served.add(c)
        for d in t.get("depends_on", []):
            if d not in task_id_set:
                errors.append("task %s depends_on unknown task '%s'" % (tid, d))
            elif d == tid:
                errors.append("task %s depends on itself" % tid)
            else:
                adj[tid].append(d)

    # coverage: every component served
    for c in sorted(comp_ids - served):
        errors.append("component '%s' is not served by any task" % c)

    # dependency graph acyclic
    cycle = find_cycle(adj)
    if cycle:
        errors.append("dependency cycle: %s" % " -> ".join(cycle))

    # order is a permutation of task ids and respects dependencies
    if sorted(order) != sorted(task_ids):
        errors.append("`order` must be a permutation of all task ids (got %d entries for %d tasks)"
                      % (len(order), len(task_ids)))
    else:
        pos = {tid: i for i, tid in enumerate(order)}
        for t in tasks:
            tid = t.get("id")
            for d in t.get("depends_on", []):
                if d in pos and tid in pos and pos[d] > pos[tid]:
                    errors.append("`order` violates dependency: %s must come before %s" % (d, tid))

    # sizing warnings (big or trivial tasks)
    locs = []
    for t in tasks:
        loc = t.get("estimated_loc")
        if isinstance(loc, int):
            locs.append(loc)
            if loc > pr_max:
                warnings.append("task %s is ~%d LOC (> %d): consider splitting into PR-sized tasks"
                                % (t.get("id"), loc, pr_max))
            elif loc < pr_min:
                warnings.append("task %s is ~%d LOC (< %d): consider merging — may be too granular"
                                % (t.get("id"), loc, pr_min))

    stats.update({
        "tasks": len(tasks),
        "components": len(components),
        "components_covered": len(served & comp_ids),
        "total_estimated_loc": sum(locs),
        "max_task_loc": max(locs) if locs else 0,
        "open_questions": len(plan.get("open_questions", [])),
    })


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", required=True, help="path to tasks.json")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA, help="path to plan.schema.json")
    ap.add_argument("--pr-min", type=int, default=40, help="below this LOC a task is flagged as too granular")
    ap.add_argument("--pr-max", type=int, default=400, help="above this LOC a task is flagged as too big")
    args = ap.parse_args(argv)

    errors, warnings, stats = [], [], {}

    if not os.path.exists(args.tasks):
        print(json.dumps({"ok": False, "errors": ["tasks file not found: %s" % args.tasks],
                          "warnings": [], "stats": {}}))
        return 1
    try:
        plan = json.load(open(args.tasks, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "errors": ["tasks.json is not valid JSON: %s" % exc],
                          "warnings": [], "stats": {}}))
        return 1

    if os.path.exists(args.schema):
        validate_schema(plan, json.load(open(args.schema, encoding="utf-8")), "plan", errors)
    else:
        warnings.append("schema not found at %s; ran semantic checks only" % args.schema)

    # Only run semantic checks if the shape is sane enough to walk (tasks present as a list).
    if isinstance(plan, dict) and isinstance(plan.get("tasks"), list):
        semantic_checks(plan, args.pr_min, args.pr_max, errors, warnings, stats)

    ok = not errors
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings, "stats": stats}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
