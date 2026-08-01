# Public-data pilot preregistration amendment 01

**Date:** 2026-08-01  
**Applies to:** `PUBLIC_DATA_PILOT_PREREGISTRATION.md`, version 0.1  
**Timing:** adopted before target extraction, model fitting, or non-target diagnostic use  
**Reason:** integrated novelty, model, data, and independent red-team reconciliation  

## 1. Governing estimand and terminology

The dated Stage 1 novelty amendment is adopted. The governing core is England, 2008–2019; EHS endpoints are 2008–09 and 2018–19. Great Britain WAS and United Kingdom macro-financial moments keep their source geographies. Data from 2020 onward form a separately scored regime exercise. The Stage 0 2006–08 to 2020–22 target remains preserved only as historical provenance.

The primitive \(z_T\) is a latent aggregate **top non-housing resource flow**. It is not observed desired saving, active net saving, a wealth share, or a preference wedge. “Top-resource pressure” names the endogenous housing/portfolio response to this flow under a stated saving motive. The primitive \(z_M\) is the corresponding aggregate middle-resource flow.

The paper's amended question is:

> Can a latent top non-housing resource-flow shock be distinguished from direct middle-resource loss and established credit, supply, tax, rate, demographic, social-comparison, rental-segmentation, and institutional-investor mechanisms in England over 2008–2019; and, if so, what is its model-implied contribution?

## 2. Required stock-to-flow and measurement bridge

Before Gate D runs, executable equations must map \(z_T\) through household active accumulation into the distribution of non-housing wealth and then into the registered Great Britain top-decile stock-share moment. The bridge must separately record opening stocks, active acquisition/saving, withdrawals, debt changes, realised returns, valuation changes, entry/exit, and the denominator effect. A contemporaneous property-price revaluation cannot enter \(z_T\).

The observation layer must also state:

- how \(p^O\) and \(p^L\) map to the single published aggregate HPI;
- how dwelling stocks map to household tenure shares;
- how the age-25–44 England outcome maps to lifecycle states;
- how permanent model types differ from round-specific observed wealth ranks; and
- which objects are absent rather than measured with zero.

Public data do not identify gross \(F^{OL}\), \(F^{LO}\), or landlord identity. Those objects are model/scenario outputs and optional validation extensions, not public-core calibration targets or verified historical flows.

## 3. Shock paths, primitives, and closure

IDENT-0 estimates fixed scalar amplitudes on preregistered annual path bases. The first deliberately difficult basis is a common linear 2008–2019 ramp for \(z_T\) and \(z_M\); distinct recovery must come from equilibrium and measurement responses, not from giving the shocks visibly different time shapes. Credit, tax, rate, demographic, social-comparison, rental-segmentation, institutional-entry, and planning/supply DGPs must have named primitive owners. Housing supply is shocked through \(A^H\), permit/land capacity, or an installation-cost wedge—not through endogenous \(\Delta H\).

Every experiment records aggregate and per-recipient units plus a closure identifier. Three diagnostic classes are permitted:

1. `D1_RESOURCE_INJECTION`: \(dz_T>0\), other household resource blocks fixed, aggregate resources explicitly increase by the same amount;
2. `D2_RESOURCE_LOSS`: \(dz_M<0\), other household resource blocks fixed, aggregate resources explicitly fall by the same amount; and
3. `E0_REDISTRIBUTION`: \(dz_T=-dz_M\), with fiscal and foreign residuals zero.

No D1 or D2 result is called a budget-neutral policy. Any historical experiment must replace these diagnostics with a source-backed incidence and fiscal/foreign closure. The incidence module must reject an unlabeled or arithmetically inconsistent closure.

## 4. Authoritative synthetic-identification criteria

Sections 11.2–11.7 of version 0.1 remain controlling except as amended here. No threshold stated in a model note may loosen them.

- Retain the 64-point, three-step-size Jacobian audit, 313 truth cases, 6,573 fits, 32 starts, recovery tolerances, 5% null false-positive ceiling, 90% shock-classification requirement, and optimiser-stability rule.
- Strengthen sign recovery: when the true absolute \(z_T\) amplitude is at least 0.20 normalised range units, recover its sign in at least **95%** of noisy fits. Apply the same rule to \(z_M\).
- For intervals generated under the synthetic Gaussian design, empirical coverage of nominal 95% intervals must lie in **[0.90, 0.98]**. This is a Monte Carlo calibration diagnostic, not a claim about real administrative-data confidence coverage.
- Where an administrative moment uses the non-statistical 2% scaling convention, call the resulting real-data profile an **objective contour**, not a 95% confidence set. A chi-square cutoff may be labelled probabilistically only when a valid likelihood/GMM covariance argument is supplied.
- Add rival-only adversarial DGPs for social-comparison demand, institutional rental-supply entry/crowding out, rental-owner segmentation/efficiency, and planning/permit restriction. In zero-\(z_T\) cases, no more than 5% of profile intervals may exclude zero, and no more than 10% may classify \(z_T\) as the largest active block.
- IDENT-0 must repeat the audit with gross-flow and landlord-identity observations absent, matching the public-data core.

`PASS-IDENT-0` authorizes MIN-EXEC construction only. The complete gate must be rerun on MIN-EXEC and again on the final long-duration-mortgage estimation model before historical attribution.

## 5. Economic materiality and identified-set width

Before empirical outcomes are inspected, the smallest historically meaningful absolute contributions are fixed at:

- 1.0 percentage point for the age-25–44 owner-occupation share;
- 1.0 percentage point for the private-renter household share;
- 5% for the England house-price level; and
- 3% for the house-price-to-stock-rent index ratio.

A pressure estimate is not called economically material unless its uncertainty or identified set excludes zero and reaches at least one threshold without violating the other registered sign and rival tests. An interval spanning both signs beyond these thresholds is uninformative. A precise upper bound below the thresholds supports a publishable near-zero result, not a positive-mechanism claim.

## 6. Attribution and diagnostic governance

The phrase “sealed holdout” is replaced prospectively by **prospectively frozen non-target diagnostic**. These diagnostics remain excluded from fitting, tuning, model selection, and parameter bounds, but they are not described as blinded or statistically independent because public trends and source families have already been inspected.

The no-pressure comparison must be re-estimated under the same parameter bounds, starts, loss, and target information as the full model. Report uncertainty around every RMSE comparison; the 10% rule is a descriptive incremental-fit threshold, not a formal test.

“Two-order Shapley” is replaced by:

- two-path order sensitivity for the two focal blocks \(z_T,z_M\); and
- exact subset-weighted Shapley attribution for a small full rival set, or a preregistered seeded Monte Carlo Shapley approximation when exact enumeration is computationally infeasible.

All prospectively frozen non-target diagnostics stay unused until the relevant model version and Gate D manifest are hash-pinned.

## 7. Implementation order

1. IDENT-0 shock ledger, measurement bridge, observation schedule, local response model, and adversarial DGPs.
2. Safe Gate A preparation and official benchmark reproduction where access permits.
3. MIN-EXEC only after `PASS-IDENT-0`.
4. Final model with long-duration mortgages only after MIN-EXEC structural gates.
5. Historical fit and attribution only after final-model Gate D.

Failure at IDENT-0 or either later Gate D redirects the paper to identified sets, scenarios, or a credible near-zero bound. It prohibits a unique historical top-resource contribution.
