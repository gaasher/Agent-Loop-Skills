#!/usr/bin/env python3
"""Render metric-over-iterations progress charts from the showcase run ledgers.

Reads the tracked TSVs in showcase/<loop>/ and writes PNGs to assets/.
Reproducible from the committed data: `python showcase/plot_progress.py` (needs matplotlib).
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patheffects import withStroke

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "text.color": "#20242e",
    "axes.edgecolor": "#e5e7eb",
    "axes.labelcolor": "#6b7280",
    "xtick.color": "#6b7280",
    "ytick.color": "#6b7280",
})

INK = "#20242e"
MUTE = "#8a8f98"
REVERT = "#e0857f"


def load(path, ycol, status_col=None):
    iters, ys, keeps = [], [], []
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            try:
                y = float(row[ycol])
            except (KeyError, ValueError):
                continue
            iters.append(int(row["iter"]))
            ys.append(y)
            keeps.append(status_col is None or row.get(status_col, "").strip() == "keep")
    return iters, ys, keeps


def running_best(ys, keeps):
    best, out = None, []
    for y, k in zip(ys, keeps):
        if k and (best is None or y > best):
            best = y
        out.append(best if best is not None else ys[0])
    return out


def chart(tsv, ycol, status_col, title, subtitle, ylabel, accent, out, footnote=None):
    iters, ys, keeps = load(os.path.join(ROOT, tsv), ycol, status_col)
    best = running_best(ys, keeps)
    base, peak = ys[0], max(best)
    has_revert = status_col is not None and not all(keeps)

    fig, ax = plt.subplots(figsize=(9.2, 4.9), dpi=200)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")

    # accent area showing the climb from baseline -> running best
    ax.fill_between(iters, base, best, step="post", color=accent, alpha=0.10, lw=0, zorder=1)
    # baseline reference
    ax.axhline(base, color="#d9dee6", lw=1.1, dashes=(5, 5), zorder=1)
    # the path the agent actually took (faint, behind)
    ax.plot(iters, ys, color="#c2c8d2", lw=1.5, alpha=0.9, zorder=2)
    # the kept frontier
    ax.step(iters, best, where="post", color=accent, lw=3.2, solid_capstyle="round",
            solid_joinstyle="round", zorder=4)

    for i, y, k in zip(iters, ys, keeps):
        if k:
            ax.scatter(i, y, s=230, color=accent, alpha=0.13, lw=0, zorder=3)      # halo
            ax.scatter(i, y, s=82, color=accent, edgecolor="white", lw=2, zorder=6)  # core
        else:
            ax.scatter(i, y, s=58, marker="x", color=REVERT, lw=2.1, alpha=0.85, zorder=5)

    rng = (max(best) - min(ys)) or 1.0
    ax.set_ylim(min(ys) - 0.12 * rng, max(best) + 0.26 * rng)
    ax.set_xlim(iters[0] - 0.4, iters[-1] + 0.4)

    ax.annotate(f"baseline  {base:g}", (iters[0], base), textcoords="offset points",
                xytext=(10, -16), fontsize=9.5, color=MUTE, fontweight="medium")
    pk_i = iters[ys.index(peak)] if peak in ys else iters[-1]
    ax.annotate(f"best  {peak:g}   ▲ +{peak-base:g}", (pk_i, peak), textcoords="offset points",
                xytext=(0, 16), fontsize=11, fontweight="bold", color=accent, ha="center",
                bbox=dict(boxstyle="round,pad=0.4", fc=accent, alpha=0.12, ec="none"),
                path_effects=[withStroke(linewidth=3, foreground="white")])

    ax.set_xlabel("iteration", fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(iters)
    ax.tick_params(length=0, labelsize=9.5)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#eef1f5", lw=1.3)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#e5e7eb")

    # legend (compact, frameless)
    h = [plt.Line2D([], [], color=accent, lw=3.2, label="running best"),
         plt.Line2D([], [], marker="o", color="white", markerfacecolor=accent,
                    markeredgecolor="white", markersize=9, lw=0, label="kept change")]
    if has_revert:
        h.append(plt.Line2D([], [], marker="x", color=REVERT, lw=0, markersize=8,
                            markeredgewidth=2, label="reverted"))
    leg = ax.legend(handles=h, loc="lower right", frameon=False, fontsize=9.3,
                    handletextpad=0.5, labelspacing=0.5)
    for t in leg.get_texts():
        t.set_color("#4b5563")

    fig.subplots_adjust(left=0.085, right=0.965, top=0.80, bottom=0.205 if footnote else 0.125)
    fig.text(0.085, 0.935, title, fontsize=15.5, fontweight="bold", color=INK)
    fig.text(0.085, 0.875, subtitle, fontsize=10, color=MUTE)
    if footnote:
        fig.text(0.085, 0.04, footnote, fontsize=8.4, style="italic", color=MUTE)

    dest = os.path.join(ROOT, "assets", out)
    fig.savefig(dest, facecolor="white")
    plt.close(fig)
    print("wrote", dest, f"({base:g} -> {peak:g})")


SOTA = ("Why not SOTA? By design — a deliberately tiny CNN, 5 epochs, run locally on a laptop (Apple MPS). "
        "The demo is the loop's decision-making, not the absolute accuracy; there's plenty of headroom left.")

if __name__ == "__main__":
    chart("showcase/tournament-autoresearch/results.tsv", "val_acc", "status",
          "tournament-autoresearch",
          "val_acc over 11 iterations — competing agents, a self-calibrating judge  ·  CIFAR-10",
          "val_acc", "#3b6fe0", "tournament-autoresearch.png", footnote=SOTA)
    chart("showcase/research-proposal/ledger.tsv", "grade", None,
          "research-proposal",
          "ScholarEval grade over 5 iterations — literature-grounded evaluate → grade → revise",
          "grade  (0–100)", "#8b5cf6", "research-proposal.png",
          footnote="A single illustrative run. Grade = ScholarEval's 0–100 rubric "
                   "(soundness · contribution · evidence); the core research question is frozen and may not be weakened.")
