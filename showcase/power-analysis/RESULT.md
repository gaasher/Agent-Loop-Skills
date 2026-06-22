# experimentDesignLoop — sandbox run (Sonnet, 2026-06-21)

Brief: flawed study design (volunteers vs last-year cohort, n~50) for a tutorial effect
(continuous outcome, d=0.4). Runner: Sonnet, budget=6, target_power=0.80.
Result: solved n=100/group via Monte-Carlo power_sim (50->0.50, 80->0.71, 95->0.78, 100->0.80;
ground truth ~100), and fixed all 6 validity flaws (confounding, randomization, selection,
optional stopping, pre-specification, measurement). Output: two-arm RCT + full preregistration.
Both gates (power>=0.80 AND zero open flaws) cleared.
Skill tweak: allow fixing a tightly-coupled flaw pair (e.g. control+randomization) together.
