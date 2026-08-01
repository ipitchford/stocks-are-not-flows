# Public-data pilot preregistration amendment 02

**Date:** 2026-08-01  
**Applies to:** `PUBLIC_DATA_PILOT_PREREGISTRATION.md` version 0.1 and amendment 01  
**Timing:** adopted before any manifest-bound IDENT-0 gate run, target extraction, or empirical fitting  
**Reason:** resolve the signed 313-case synthetic design against the directional resource-closure taxonomy; freeze public-unit observation adapters

## 1. Signed synthetic coordinates and elementary closures

The 313-case design retained by amendment 01 contains positive and negative
anchors and arbitrary joint values for both focal coordinates. The D1 and D2
labels in amendment 01 describe only two economically salient directions and do
not cover their reverse synthetic perturbations. They are not discarded.
Instead, IDENT-0 registers four elementary open-economy diagnostic receipts:

1. `D1_RESOURCE_INJECTION`: $dz_T>0$, $dz_M=0$, and aggregate resources rise by $dz_T$;
2. `D1R_TOP_RESOURCE_WITHDRAWAL`: $dz_T<0$, $dz_M=0$, and aggregate resources fall by $dz_T$;
3. `D2_RESOURCE_LOSS`: $dz_M<0$, $dz_T=0$, and aggregate resources fall by $dz_M$; and
4. `D2R_MIDDLE_RESOURCE_INJECTION`: $dz_M>0$, $dz_T=0$, and aggregate resources rise by $dz_M$.

The reverse labels are synthetic recovery coordinates, not proposed historical
interventions. A joint truth case carries a `C0_COMPOSITE_OPEN` receipt whose
children are the applicable elementary receipts and whose aggregate-resource
change is their sum. The receipt preserves the children; it may not collapse
them into a single causal story.

The all-zero anchor carries `N0_NO_CHANGE`, an empty compositional receipt with
zero aggregate-resource change. It is not silently assigned to D1, D2, or E0.

`E0_REDISTRIBUTION` remains the special direct receipt for $dz_T=-dz_M>0$
with zero fiscal, foreign, and other residuals. A reverse or otherwise arbitrary
joint change remains a composition unless separately registered. Neither an
elementary D1/D2 receipt nor a nonzero-sum composition is called budget neutral.

Signed estimator amplitudes are local coordinates around the synthetic zero.
The executable measurement tangent is audited in all four elementary
directions. A historical experiment still requires source-backed incidence,
recipient masses, and fiscal/foreign closure; these synthetic receipts provide
no historical source.

## 2. Public-unit observation adapters

The local response panel stores deviations. The registered data boundary keeps
the units in version 0.1:

- `T01_O_BASE`, `T02_O_END`, `T03_PRS_BASE`, and `T04_PRS_END` are percentage
  levels. IDENT-0 adds the local percentage-point response to hash-pinned
  positive synthetic baseline levels. These synthetic levels test recovery and
  are not English estimates.
- `T07_RENT_END` remains a median nominal weekly cash-rent level in pounds. If
  the internal response is ℓ log-percent, the adapter is
  $R^{model}=R^0\exp(\ell/100)$, with positive hash-pinned synthetic $R^0$
  and a raw-pound synthetic scale. The empirical model must replace the
  synthetic baseline and scale with the registered EHS statistic and its
  design-based uncertainty.
- Identity/deviation adapters remain in the natural units already stated for
  the other targets.

The ordered adapter IDs, baselines, scales, target labels, and source commit are
manifest inputs. Changing them after a gate run creates a new gate version.

## 3. Annual-state limits on frozen diagnostics

`H05_PRICE_RENT_INDEX` remains non-modelled in IDENT-0. Its frozen definition is
the 60-month January 2015–December 2019 path, and the annual prototype has no
registered monthly interpolation operator or covariance. Five annual values
must not substitute for it.

The previously drafted `H_PRS_DWELLING_STOCK` convenience series is removed
from the prospectively frozen diagnostic schedule because version 0.1 did not
register it. PRS dwelling stock may remain an internal accounting output. It
can enter a later gate only after a prospective amendment fixes an ID, source,
financial-year denominator, observation map, covariance, and falsification
use.

## 4. Assurance boundary

The IDENT-0 wealth bridge is a stylized local top-rank measurement tangent. Its
normalized stocks, group allocation, and terminal loadings are design inputs,
not estimated wealth elasticities. Passing its accounting mutations establishes
unit and stock-flow coherence only.

`PASS-IDENT-0` remains impossible unless every controlling criterion has a
manifest-bound evidence object and passes. A fail-fast blocking criterion may
terminate the remaining Monte Carlo workload; the report must list every
unrun criterion and may issue only `FAIL-IDENT-0`, never a partial pass.
