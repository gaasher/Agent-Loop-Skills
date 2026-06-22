#!/usr/bin/env python3
"""Render val_acc-over-iterations progress charts from the showcase run ledgers.

Reads the tracked TSVs in showcase/<loop>/results.tsv and writes PNGs to assets/.
Reproducible from the committed data: `python showcase/plot_progress.py` (needs matplotlib).
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    iters, accs, keeps, descs = [], [], [], []
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            iters.append(int(row["iter"]))
            accs.append(float(row["val_acc"]))
            keeps.append(row["status"].strip() == "keep")
            descs.append(row.get("description", ""))
    return iters, accs, keeps, descs


def running_best(accs, keeps):
    best, out = -1.0, []
    for a, k in zip(accs, keeps):
        if k and a > best:
            best = a
        out.append(best if best > 0 else accs[0])
    return out


def chart(loop, title, color, out):
    iters, accs, keeps, _ = load(os.path.join(ROOT, "showcase", loop, "results.tsv"))
    best = running_best(accs, keeps)
    fig, ax = plt.subplots(figsize=(8.4, 4.3), dpi=150)
    fig.patch.set_facecolor("white")
    # the path the agent actually took
    ax.plot(iters, accs, color="#c9ccd1", lw=1.6, zorder=1)
    # running best (the kept frontier)
    ax.step(iters, best, where="post", color=color, lw=2.6, zorder=2, label="running best")
    for i, a, k in zip(iters, accs, keeps):
        if k:
            ax.scatter(i, a, s=70, color=color, edgecolor="white", lw=1.2, zorder=3)
        else:
            ax.scatter(i, a, s=46, color="#e2554e", marker="x", lw=1.8, zorder=3, alpha=0.85)
    base, peak = accs[0], max(b for b in best)
    ax.annotate(f"baseline {base:.3f}", (iters[0], base), textcoords="offset points",
                xytext=(8, -14), fontsize=9, color="#555")
    pk_i = iters[accs.index(peak)] if peak in accs else iters[-1]
    ax.annotate(f"best {peak:.3f}  (+{(peak-base)*100:.1f} pts)", (pk_i, peak),
                textcoords="offset points", xytext=(-4, 10), fontsize=10,
                fontweight="bold", color=color)
    rng = max(best) - min(accs)
    ax.set_ylim(min(accs) - 0.10 * rng, max(best) + 0.20 * rng)
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("iteration"); ax.set_ylabel("val_acc")
    ax.set_xticks(iters)
    ax.grid(axis="y", color="#eee", lw=1)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    # legend marker glyphs
    ax.scatter([], [], s=70, color=color, edgecolor="white", label="keep")
    ax.scatter([], [], s=46, color="#e2554e", marker="x", label="discard (reverted)")
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    dest = os.path.join(ROOT, "assets", out)
    fig.savefig(dest, bbox_inches="tight")
    print("wrote", dest, f"({base:.3f} -> {peak:.3f})")


if __name__ == "__main__":
    chart("ml-autoresearch",
          "ml-autoresearch  —  val_acc over 10 iterations  (CIFAR-10, 5-epoch budget)",
          "#2f7d4f", "ml-autoresearch.png")
    chart("tournament-autoresearch",
          "tournament-autoresearch  —  val_acc over 11 iterations  (CIFAR-10, 5-epoch budget)",
          "#3457a6", "tournament-autoresearch.png")
