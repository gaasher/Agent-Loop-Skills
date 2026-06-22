# Experiment Design: Interactive Tutorial Quiz Score Study

**Version:** 3 (FINAL — all validity checks passed)
**Date:** 2026-06-21

---

## Hypothesis

A new interactive tutorial increases students' quiz scores compared to the current static tutorial.
The minimal effect of interest is +6 points on a 0–100 scale (Cohen's d = 0.4, SD = 15).

---

## Arms / Conditions

- **Control arm:** Students use the existing static tutorial (the current standard).
- **Treatment arm:** Students use the new interactive tutorial.

Both arms receive the same quiz immediately after the tutorial. No other instruction differences
exist between arms during the study period.

---

## Unit of Analysis

Individual student. Each student is assigned to exactly one arm and contributes one quiz score.

---

## Eligibility and Enrollment

All students enrolled in the course section(s) included in the study are eligible. Participation
in the tutorial and quiz is a standard course requirement (not opt-in), so the sample is the full
enrolled class cohort rather than a self-selected volunteer subset. Students with prior exposure
to either tutorial (e.g., repeat enrollees) are excluded before randomization.

The study targets enrollment of at least 200 eligible students (100 per arm). If a single section
does not provide 200 students, additional sections from the same institution and same academic term
are included, maintaining the same instructor team and curriculum.

---

## Assignment Method

Students are **randomly assigned** (simple randomization, 1:1 ratio) using a computer-generated
random allocation sequence produced before enrollment opens. Assignments are sealed and concealed
from enrollment staff until after all students are enrolled and eligibility is confirmed. Both arms
run concurrently in the same academic term with the same instructor(s). The randomization sequence
is held by a study coordinator not involved in grading or instruction.

---

## Primary Outcome

Quiz score (continuous, 0–100 scale), measured by the identical quiz administered to both arms
immediately after the tutorial session ends.

**Measurement fidelity protocol:**
1. All student quiz submissions are anonymized (student ID replaced by a study code) before
   grading. The condition assignment key is held separately and not disclosed to graders.
2. A rubric is prepared and locked before any grading begins (included as Appendix A of this
   pre-registration document).
3. A randomly selected 15% of submissions are independently scored by a second grader blind to
   both condition and primary grader scores. Cohen's kappa or intraclass correlation coefficient
   (ICC) is computed as a fidelity check; an ICC < 0.85 triggers re-grading of the full set.
4. Any grader who becomes aware of a student's condition is recused from grading that student's
   submission.

---

## Planned Statistical Test

Two-sample independent t-test (two-tailed, alpha = 0.05) comparing mean quiz score between
treatment and control. This is the **one pre-specified primary analysis**. No secondary hypothesis
tests are conducted without labeling them exploratory.

---

## Assumed Effect Size

- Baseline mean: 70 points (SD = 15)
- Minimal effect of interest: +6 points (Cohen's d = 0.4)
- Alpha: 0.05 (two-tailed)

---

## Sample Size

**100 students per arm (200 total).**
Power simulation (seed=1, 2000 sims):
```
python3 power_sim.py --design two-sample-mean --effect 6 --sd 15 --alpha 0.05 --n 100
→ {"power": 0.8035, "n_per_group": 100, "effect": 6.0, "alpha": 0.05}
```
Achieved simulated power = **0.80** (meets target ≥ 0.80).

Power is computed at the minimal effect worth detecting (d = 0.4), not an inflated estimate.

---

## Stopping Rule

**No early stopping.** Data collection continues until all enrolled students complete the tutorial
and quiz (target n = 200). The single pre-specified analysis runs once at that point, and only
once. No interim analyses or peeking at accumulating data are permitted.

If fewer than 200 students complete the study due to attrition, a pre-specified sensitivity
analysis (intent-to-treat vs. completers) is conducted and labeled exploratory.

---

## Multiple Comparisons

There is **one primary outcome** (quiz score) and **one pre-specified primary test** (two-sample
t-test). No multiplicity correction is needed for the primary analysis. Any subgroup analyses
or secondary outcomes are labeled exploratory and reported separately, with no adjustment to
the primary verdict.

---

## Open Flaws (iteration 3)

1. ~~**Confounding / No concurrent control:** FIXED — concurrent randomized control group.~~
2. ~~**No randomization:** FIXED — simple random assignment; concealed allocation.~~
3. ~~**Selection / sampling:** FIXED — full enrolled cohort; multi-section if needed.~~
4. ~~**Optional stopping:** FIXED — single analysis at study end; no interim looks.~~
5. ~~**Outcome & analysis pre-specification:** FIXED — primary outcome, test, alpha, and stopping
   rule are all fixed in this document before data collection; this document serves as the
   pre-registration to be lodged on OSF/AsPredicted before any data are collected.~~
6. ~~**Measurement:** FIXED — locked rubric; anonymized grading; 15% double-graded ICC fidelity
   check; graders recused if condition becomes known.~~

**All validity checklist items resolved. Power = 0.8035 ≥ 0.80.**

---

## Preregistration

*This section is to be submitted verbatim to a public registry (e.g., OSF Registries or
AsPredicted.org) before data collection begins. The timestamp of registration serves as
proof of pre-specification.*

**Title:** Randomized Controlled Trial of Interactive vs. Static Tutorial on Quiz Performance

**Hypothesis:** Students randomly assigned to the new interactive tutorial will score higher on
the post-tutorial quiz than students assigned to the current static tutorial. The minimal effect
of interest is 6 points (Cohen's d = 0.4 with SD = 15).

**Primary outcome:** Mean quiz score (0–100) measured immediately post-tutorial.

**Planned primary analysis:** Two-sample independent t-test (two-tailed, alpha = 0.05), one
analysis at study end, no interim looks. Decision rule: reject the null if p < 0.05.

**Sample size:** 100 per arm (200 total), derived from power simulation at effect = 6 points,
SD = 15, alpha = 0.05, target power = 0.80 → achieved simulated power = 0.8035.

**Randomization:** Computer-generated 1:1 simple randomization; allocation concealed until
all students are enrolled and eligibility is confirmed.

**Stopping rule:** No early stopping. Single analysis after all 200 enrolled students complete
the tutorial and quiz.

**Blinding:** Students are not informed of which arm they are in until after quiz grading is
complete. Graders are blind to condition assignment. A second independent grader scores 15%
of submissions to verify fidelity (ICC threshold: 0.85).

**Exclusion criteria:** Students with prior exposure to either tutorial version.

**Secondary / exploratory analyses (not primary, not used for the primary verdict):**
- Sensitivity analysis: intent-to-treat vs. completer populations.
- Exploratory subgroup: quiz performance by prior performance quintile (no multiplicity
  correction; results labeled exploratory).

---

*Iteration 3: Pre-specification formalized (this document IS the pre-registration); measurement
fidelity protocol added (locked rubric, blinded grading, ICC double-grading check). All 6
validity flaws resolved. Power = 0.8035. Study is ready for pre-registration and data collection.*
