# Data Analysis Findings

**Dataset:** ./orders.csv (400 rows, 7 columns)
**Question:** What is associated with higher order value, and what is associated with returns?

---

## Finding 1 — Enterprise segment is strongly associated with higher order value (VERIFIED)

**Claim:** Enterprise orders average substantially higher order value than consumer orders.

**Numbers:**
- Enterprise (n=127): mean = $184.90, median = $185.12
- Consumer (n=273): mean = $109.16, median = $109.94
- Mean difference: $75.75 (+69.4% relative to consumer)

**Effect size:** Cohen's d = 2.13 (very large by conventional thresholds)

**Verification:** Median comparison confirms direction and magnitude (median diff $75.18). Fraction above overall median ($126.68): enterprise 95.3% vs consumer 28.6% — a 66.7 percentage-point gap confirming the separation is not driven by outliers.

**Method:** Group means/medians split by `segment` column; Cohen's d computed with pooled standard deviation.

**Note:** Association only — unmeasured factors (product type, bulk purchasing) may drive or mediate the difference.

---

## Finding 2 — Mobile channel is strongly associated with higher return rate (VERIFIED)

**Claim:** Mobile channel orders are returned at a far higher rate than web or store orders.

**Numbers:**
- Mobile (n=119): return rate = 32.8% (39 returns)
- Web (n=138): return rate = 8.0% (11 returns)
- Store (n=143): return rate = 8.4% (12 returns)
- Non-mobile combined (n=281): return rate = 8.2%
- Absolute difference: +24.6 percentage points (mobile vs non-mobile)

**Effect size:** Risk ratio = 4.00 (mobile returns ~4x more often than non-mobile)

**Verification:** Independent recount by row-filtering confirms mobile 39/119 = 32.8%, web 11/138 = 8.0%, store 12/143 = 8.4% — numbers match exactly.

**Method:** Return rate computed as count(returned==1)/count(all) by channel; risk ratio = mobile_rate / non_mobile_rate.

**Note:** Association only — mobile-specific UX, product categories, or buyer behavior may mediate this gap.

---

## Finding 3 — Longer customer tenure (signup_days) is associated with higher order value (VERIFIED)

**Claim:** Customers with more days since signup tend to place higher-value orders.

**Numbers:**
- Pearson r = 0.310 (n=400), r² = 0.096 (9.6% variance explained)
- Mean order value by signup_days quartile:
  - Q1 (lowest tenure, n=100): $109.94
  - Q2 (n=100): $128.69
  - Q3 (n=100): $144.51
  - Q4 (highest tenure, n=100): $149.68
- Q4 vs Q1 difference: +$39.74 (+36.1%)

**Effect size:** Pearson r = 0.310 (moderate); monotone increase across all four quartiles confirms the trend is not driven by outliers.

**Verification:** Spearman rank correlation rs = 0.314 (independent check) agrees closely with Pearson r; quartile analysis shows monotone increase across all four groups.

**Method:** Pearson and Spearman correlations between `signup_days` and `order_value`; mean `order_value` split by `signup_days` quartile.

**Note:** Association only — segment (enterprise vs consumer) is a likely confounder, as enterprise customers may also have longer tenure. Within-segment analysis recommended to isolate the tenure effect.

---
