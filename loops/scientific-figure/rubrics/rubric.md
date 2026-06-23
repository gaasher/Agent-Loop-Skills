# Figure-grading rubric

How the **critic** turns a rendered figure into a single **0–100 grade**. This rubric is **fixed** —
the critic **never edits it**. A generator↔critic loop needs a *stable bar*: if the rubric drifted, you
could not tell whether a higher grade meant a better figure or just a slacker critic. The pass
threshold is only meaningful against a fixed ruler.

## What the grade measures

The grade scores the **figure** — the rendered image *and* the numbers it shows — read **against the
frozen `<goals>`** (the figure's intended message, distilled from `<brief>` at setup). A pretty figure
that misses the message scores low; a figure that lands the message honestly and looks publication-ready
scores high. Eloquence in the brief earns nothing; only what the rendered figure actually communicates
is graded.

## The five axes (score each 1–5, anchored)

5 = publication-quality on this axis, 1 = severely deficient.

### 1. Message & fit — *does it land the intended message?*
Does the figure deliver `<goals>`'s message **at a glance** (a few seconds, without decoding)? One clear
narrative, not three competing ones. Is the **chart type correct** for the data and the claim it
supports, and appropriate for the audience?
- **5** — message graspable in seconds; ideal chart type for the data + claim.
- **3** — message recoverable but needs decoding, or a serviceable-but-suboptimal chart type.
- **1** — wrong chart type for the claim, or no discernible single message.

### 2. Aesthetic — *is it publication-pretty?*
Palette coherent and **colorblind-safe**; typography and font sizes legible; layout and panel sizing
balanced; overall polish.
- **5** — journal-cover quality; nothing you would change.
- **3** — clean but unremarkable, or one palette/typography issue.
- **1** — harsh, default-ugly, or illegible.

### 3. Clarity & cleanliness — *can a reader parse it unaided?*
Axes **labeled with units** and sensible ticks/ranges; nothing (data, legend, labels, annotations) cut
off; not crowded, not sparse; legend placed **off** the data; **no chartjunk / 3D distortion**; caption
(if present) self-contained.
- **5** — nothing to add or remove; reads cleanly on its own.
- **3** — minor crowding, too much spacing, a missing unit, or a slightly awkward legend.
- **1** — unlabeled, clipped, or cluttered to the point of confusion.

### 4. Integrity — *is it honest?* (the hard-gate axis)
Do the **numbers in the figure equal the numbers in the data**? **Honest axes** — no truncated or dual
axis that exaggerates, no hidden log; uncertainty (error bars / CI / n) shown where relevant; the
encoding does not mislead. The critic **recomputes a sample of the plotted values from `<data_paths>`**
rather than trusting the generator.
- **5** — values faithful to the data, axes honest, uncertainty shown where it matters.
- **3** — honest, but uncertainty is missing where a reviewer would expect it.
- **1** — a plotted value contradicts the data, or an axis materially misleads *(triggers a hard gate)*.

### 5. Domain completeness — *is the science complete?* (conditional, literature-checked)
**Active only when the figure makes an external domain claim** — a named signalling pathway, gene set,
canonical benchmark, taxonomy, or mechanism. The **critic auto-detects** this from the figure + brief;
there is no user toggle. When active, the critic verifies the domain content against retrieved
literature (S2/arXiv via `<lit>`): does the figure **faithfully and completely** represent it? e.g. a
MAPK-cascade figure includes RAF→MEK→ERK; a CIFAR-10 benchmark figure includes the standard baselines.
- **5** — complete and correct versus the literature.
- **3** — mostly complete; one non-critical omission.
- **1** — a key node/gene/baseline the literature treats as essential is missing or wrong.
- **When inactive, this axis is dropped** (n_axes = 4), exactly as `scientific-writer` drops its code axis.

## Journal-spec anchoring (when `<style>` names a journal)

When `<style>` names a target journal/venue, its figure guidelines are fetched once at setup into
`<sandbox_root>/style/journal_spec.md` (via WebSearch/WebFetch). Then axes **2 (Aesthetic)** and **3
(Clarity)** are graded **against the concrete numbers in that spec** — exact column width, minimum font
size, required fonts, line weights, color mode, panel-label convention — not against generic taste. A
figure that violates a hard journal requirement (font below the minimum, wrong column width, RGB where
CMYK is required) **cannot score 5** on the affected axis. Both roles read the *same* cached spec, so the
generator conforms to exactly what the critic grades against.

## Aggregating to 0–100

```
overall_score = 100 × ( Σ axis scores ) / ( 5 × n_axes )
n_axes = 5 (domain axis active) or 4 (inactive). Equal weight, no per-axis weighting.
```

## Hard gates (force `pass = false` regardless of overall_score)

A figure cannot "pass" by averaging over a fatal flaw. The critic must **independently confirm** each
before listing it in `gate_failures`:
1. **A figure value that contradicts the data** — the critic recomputed it from `<data_paths>` and it
   differs. A fabricated/incorrect number is fatal.
2. **A misleading axis** — a truncated/dual axis or hidden-log encoding that materially exaggerates the
   effect.
3. **Fabricated data presented as real** — a data-looking plot with no `<data_paths>` backing it (an
   illustrative figure must read as illustrative, never as a fake data plot).

## Scoring procedure (each iteration)
1. **Spot-check first.** Recompute a sample of the figure's plotted values from `<data_paths>`; walk any
   external domain claim through `<lit>`. Record each as a `spotcheck`.
2. **Chain-of-thought, then form-fill.** Reason per axis in the `justification`, *then* write the 1–5
   integer — never score first and rationalize after (G-Eval form-filling).
3. **Aggregate** to `overall_score`; apply the hard gates → `pass`.
4. **Prioritize fixes.** Turn the highest-leverage gaps into ranked, executable `findings` for the
   generator (block/gate items first) — one tight batch, not a laundry list.

> **Pass** = `overall_score >= <pass_threshold>` **AND** `gate_failures` empty. **No credit for effort
> or elapsed iterations**; a surface-only change that doesn't improve what the figure communicates does
> not move the grade.

> **Build-time check:** the fixed rubric, the integrity hard gate, and grading-the-rendered-figure (not
> the brief's prose) are deliberate. If you revisit them, keep the bar stable across a run — that
> property is what makes "iterate until a passing grade" well-defined.
