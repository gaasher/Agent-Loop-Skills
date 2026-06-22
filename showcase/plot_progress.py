#!/usr/bin/env python3
"""Render the tournament-autoresearch progress chart from the showcase ledger.

A faithful port of Andrej Karpathy's autoresearch analysis plot
(github.com/karpathy/autoresearch, analysis.ipynb) — same schema: a running-best
step line, prominent green "kept" dots, faint gray "discarded" dots, and each
kept experiment labeled with its change at a 30 degree rotation. Adapted only for
a higher-is-better metric (val_acc): running *max*, region at/above baseline.

Reproducible from the committed data:  python showcase/plot_progress.py  (needs matplotlib).
"""
import csv
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path, ycol, status_col, desccol):
    """Return parallel lists (x, y, status_upper, description) from a TSV ledger."""
    xs, ys, st, desc = [], [], [], []
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            try:
                y = float(row[ycol])
            except (KeyError, ValueError):
                continue
            xs.append(int(row["iter"]))
            ys.append(y)
            st.append((row.get(status_col, "") or "").strip().upper())
            desc.append((row.get(desccol) or "").strip())
    return xs, ys, st, desc


def chart(tsv, ycol, status_col, desccol, title_name, ylabel, out):
    xs, ys, st, desc = load(os.path.join(ROOT, tsv), ycol, status_col, desccol)

    fig, ax = plt.subplots(figsize=(16, 8))

    # baseline is the first experiment; higher val_acc is better
    baseline = ys[0]

    # only plot points at or above baseline (the interesting region)
    keep_region = [i for i in range(len(xs)) if ys[i] >= baseline - 0.0005]

    # discarded as faint background dots
    di = [i for i in keep_region if st[i] == "DISCARD"]
    ax.scatter([xs[i] for i in di], [ys[i] for i in di],
               c="#cccccc", s=12, alpha=0.5, zorder=2, label="Discarded")

    # kept experiments as prominent green dots
    ki = [i for i in keep_region if st[i] == "KEEP"]
    ax.scatter([xs[i] for i in ki], [ys[i] for i in ki],
               c="#2ecc71", s=50, zorder=4, label="Kept",
               edgecolors="black", linewidths=0.5)

    # running maximum step line (the frontier)
    kept_all = [i for i in range(len(xs)) if st[i] == "KEEP"]
    kept_x = [xs[i] for i in kept_all]
    kept_y = [ys[i] for i in kept_all]
    running_max, m = [], None
    for v in kept_y:
        m = v if m is None else max(m, v)
        running_max.append(m)
    ax.step(kept_x, running_max, where="post", color="#27ae60",
            linewidth=2, alpha=0.7, zorder=3, label="Running best")

    # label each kept experiment with its description. The last two kept points
    # sit high on the climb, so their labels read *downward* into the open area
    # below the frontier instead of spilling off the top edge; the rest go up.
    labels = []
    n_pts = len(kept_all)
    for j, i in enumerate(kept_all):
        d = re.sub(r"^iter\d+-a\d+:\s*", "", desc[i]).strip()
        if len(d) > 45:
            d = d[:42] + "..."
        if j >= n_pts - 2:  # last two: annotate downward
            labels.append(ax.annotate(d, (xs[i], ys[i]), textcoords="offset points",
                                      xytext=(6, -6), fontsize=8.0, color="#1a7a3a", alpha=0.9,
                                      rotation=-60, ha="left", va="top"))
        else:               # the rest: annotate upward (Karpathy's schema)
            labels.append(ax.annotate(d, (xs[i], ys[i]), textcoords="offset points",
                                      xytext=(6, 6), fontsize=8.0, color="#1a7a3a", alpha=0.9,
                                      rotation=60, ha="left", va="bottom"))

    n_total = len(xs)
    n_kept = sum(1 for s in st if s == "KEEP")
    ax.set_xlabel("Experiment #", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{title_name}: {n_total} Experiments, {n_kept} Kept Improvements", fontsize=14)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.2)
    ax.set_xticks(xs)

    # y-axis: headroom above for the upward labels, room below for the two
    # downward ones (Karpathy used a symmetric 0.15 margin; the steep rotated
    # labels need a little more on each side).
    best = max(kept_y)
    rng = best - baseline
    ax.set_ylim(baseline - 0.42 * rng, best + 0.50 * rng)

    plt.tight_layout()
    dest = os.path.join(ROOT, "assets", out)
    plt.savefig(dest, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", dest, f"(baseline {baseline:g} -> best {best:g}, {n_kept}/{n_total} kept)")


if __name__ == "__main__":
    chart("showcase/tournament-autoresearch/results.tsv", "val_acc", "status", "description",
          "Tournament Autoresearch Progress", "Validation Accuracy (higher is better)",
          "tournament-autoresearch.png")
