# Proposal-grading rubric

How the **Judge** turns a ScholarEval evaluation into a single **0–100 grade** for the
research proposal. This rubric is **fixed** — unlike a self-refining rubric, the Judge
**never edits it**. A research proposal loop needs a
*stable bar*: if the rubric drifted, you could not tell whether a higher grade meant a better
proposal or just a slacker judge. The pass threshold is only meaningful against a fixed ruler.

## What the grade measures

The grade scores the **proposal**, read **through ScholarEval's literature-grounded
evidence** — not the proposal's own prose. A confident-sounding proposal with thin literature
support scores low; a plainly written one whose methods are well-supported and whose
contributions survive comparison scores high. This is the whole point of grounding the loop
in ScholarEval rather than a generic writing critic.

## The three axes (score each 0–5, anchored)

### 1. Soundness — *are the proposed methods empirically defensible?*
Read the ScholarEval `soundness` entries. Per method, weigh **Support** against
**Contradictions**.
- **5** — every method has strong, on-point Support; any Contradictions are minor and already
  addressed by the proposal.
- **3** — methods are mostly supported, but ≥1 has a real, unaddressed Contradiction that
  threatens a result.
- **1** — a core method is contradicted by similar prior attempts with no mitigation, or rests
  on no supporting evidence at all.
- **0** — the central method is refuted by the literature (similar approaches reliably fail).

### 2. Contribution — *does it advance the field, dimension by dimension?*
Read the ScholarEval `contribution` entries. Per dimension, weigh **Strengths** against
**Weaknesses**. The top of this scale is the loop's north star: a proposal whose contribution,
if executed, would be a **genuinely novel, publishable, potentially field-advancing or
state-of-the-art** result — novelty *shown* against named prior work, not asserted.
- **5** — clear, defended, significant novelty on ≥1 important dimension, demonstrated against
  specific prior work; the contribution reads as publishable and field-advancing; Weaknesses
  are narrow.
- **3** — some genuine contribution, but most dimensions are incremental over named prior work.
- **1** — nearly every dimension is already covered by existing papers; novelty is mostly
  asserted, not shown.
- **0** — the contribution is subsumed by a single prior work the proposal does not improve on.

### 3. Evidence quality — *can we trust this evaluation at all?* (the meta-check)
ScholarEval is itself an LLM pipeline; the grade is only as good as the evidence under it.
Score how well the evaluation's points are **grounded in real retrieved citations**
(`cites` → `evidence`, each with a verbatim `snippet`).
- **5** — virtually every consequential point cites a real, on-topic snippet; no fabrication.
- **3** — the main points are grounded, but several claims have empty `cites` or weak snippets.
- **1** — large parts of the evaluation are ungrounded assertion.
- **0** — citations are missing or do not support their claims (possible fabrication).

## Aggregating to 0–100

```
grade = 100 × ( w_s·soundness + w_c·contribution + w_e·evidence_quality ) / 5
default weights:  w_s = 0.45 · w_c = 0.35 · w_e = 0.20   (must sum to 1)
```
Weights live in `loop.run.yaml` (`grade_weights`) so a run can re-weight once at setup —
but they are **frozen for the whole run**, never tuned mid-loop.

## Hard gates (force `pass = false` regardless of grade)

A proposal cannot "pass" by averaging over a fatal flaw:
1. **`soundness == 0`** — a core method the literature says will fail. No amount of
   contribution rescues an idea that cannot work.
2. **`evidence_quality <= 1`** — the grade rests on ungrounded/fabricated evidence, so it is
   not trustworthy. Re-run ScholarEval (deeper retrieval) before trusting any grade.
3. **An ungrounded fatal Contradiction** — a Contradiction the Judge deems result-threatening
   that the proposal neither addresses nor the Reviser can wave away.

Record each triggered gate in the verdict's `gate_failures`.

## Scoring procedure (each iteration)
1. **Evidence gate first.** Walk `evidence`; flag points whose `cites` are empty or whose
   snippet does not support the claim. Discount those points before scoring 1 and 2, then set
   axis 3 from how much survived.
2. **Chain-of-thought, then form-fill.** Reason per axis in `rationale`-style notes, *then*
   write the 0–5 integers — do not score first and rationalize after (G-Eval form-filling).
3. **Aggregate** to `grade`; apply hard gates → `pass`.
4. **Prioritize fixes.** Turn the highest-leverage unaddressed Contradictions / Weaknesses /
   Suggestions into ranked `fixes` for the Reviser — the items most likely to lift the lowest
   axis. One tight batch, not a laundry list.

> **Build-time check:** the fixed-rubric choice, the evidence gate, and grading-through-
> evidence (not prose) are deliberate. If you revisit them, keep the bar stable across a run —
> that property is what makes "iterate until a passing grade" well-defined.
