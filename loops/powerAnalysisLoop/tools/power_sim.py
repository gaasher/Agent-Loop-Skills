#!/usr/bin/env python3
"""Monte-Carlo statistical power for a planned experiment — stdlib only, 3.9-safe.

The experimentDesignLoop uses this as its objective signal: given an assumed effect size and a
per-group sample size, it simulates the experiment many times and reports the fraction in which
the planned test reaches significance — i.e. the power. The loop raises N / sharpens the design
until power clears the target.

Two designs:
  two-sample-mean : control ~ Normal(0, sd), treatment ~ Normal(effect, sd); Welch t-style z-test.
  two-proportion  : control ~ Bernoulli(baseline), treatment ~ Bernoulli(baseline+effect); z-test.

Usage:
    python3 power_sim.py --design two-sample-mean --effect 0.4 --sd 1.0 --n 100 [--alpha 0.05] [--sims 2000] [--seed 1]
    python3 power_sim.py --design two-proportion --baseline 0.40 --effect 0.05 --n 1500

Note: uses the normal critical value (statistics.NormalDist.inv_cdf), a good approximation that is
slightly optimistic for very small n (< ~20 per group); fine for typical design sizes.
Prints one JSON object: {"design","n_per_group","effect","alpha","sims","power"}.
"""

import argparse
import json
import random
import statistics
import sys

_Z = statistics.NormalDist()


def _mean_sd(xs):
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return m, var ** 0.5


def power_two_sample_mean(effect, sd, n, zcrit, sims, rng):
    nd_c = statistics.NormalDist(0.0, sd)
    nd_t = statistics.NormalDist(effect, sd)
    rejects = 0
    for _ in range(sims):
        c = [nd_c.inv_cdf(rng.random()) for _ in range(n)]
        t = [nd_t.inv_cdf(rng.random()) for _ in range(n)]
        mc, sc = _mean_sd(c)
        mt, st = _mean_sd(t)
        se = (sc * sc / n + st * st / n) ** 0.5
        if se > 0 and abs((mt - mc) / se) > zcrit:
            rejects += 1
    return rejects / sims


def power_two_proportion(baseline, effect, n, zcrit, sims, rng):
    p_c, p_t = baseline, baseline + effect
    rejects = 0
    for _ in range(sims):
        xc = sum(1 for _ in range(n) if rng.random() < p_c)
        xt = sum(1 for _ in range(n) if rng.random() < p_t)
        pc, pt = xc / n, xt / n
        pooled = (xc + xt) / (2 * n)
        se = (2 * pooled * (1 - pooled) / n) ** 0.5
        if se > 0 and abs((pt - pc) / se) > zcrit:
            rejects += 1
    return rejects / sims


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", choices=["two-sample-mean", "two-proportion"],
                    default="two-sample-mean")
    ap.add_argument("--effect", type=float, required=True)
    ap.add_argument("--sd", type=float, default=1.0)
    ap.add_argument("--baseline", type=float, default=0.5)
    ap.add_argument("--n", type=int, required=True, help="sample size per group")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    zcrit = _Z.inv_cdf(1 - args.alpha / 2)
    if args.design == "two-sample-mean":
        power = power_two_sample_mean(args.effect, args.sd, args.n, zcrit, args.sims, rng)
    else:
        power = power_two_proportion(args.baseline, args.effect, args.n, zcrit, args.sims, rng)

    print(json.dumps({
        "design": args.design,
        "n_per_group": args.n,
        "effect": args.effect,
        "alpha": args.alpha,
        "sims": args.sims,
        "power": round(power, 4),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
