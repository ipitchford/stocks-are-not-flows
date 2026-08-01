# Public-data pilot preregistration amendment 03

**Date:** 2026-08-01  
**Applies to:** `PUBLIC_DATA_PILOT_PREREGISTRATION.md` version 0.1 and amendments 01–02  
**Timing:** adopted after `FAIL-IDENT-0` and after feasibility inspection of the public EHS live table, but before the manifest-bound Gate A public-data pipeline run  
**Reason:** authorize a licence-free EHS point-estimate bridge, record the post-IDENT-0 redirect, and correct the property-flow evidence boundary

## 1. Post-IDENT-0 scope

The authoritative IDENT-0 v2 run returned `FAIL-IDENT-0`. The registered stop
rule is therefore active:

- no MIN-EXEC model will be built;
- no unique historical top-resource contribution will be estimated;
- the synthetic 3-of-4 constructed-rival result is a designed specificity
  warning, not an empirical false-positive rate; and
- Gate A continues only as a source-bound accounting and partial-identification
  application.

Public observations may motivate outcome scales and constrain explicitly
declared sets. They do not convert the latent top non-housing resource flow into
an observed treatment and do not supply empirical response coefficients for the
IDENT-0 design matrix.

## 2. Open EHS point-estimate bridge

The official open live table `FA1201 (S106): age of household reference person
by tenure` contains annual unrounded survey-weighted household counts for HRP
age bands 25–34 and 35–44 and for the three broad tenures: owner occupation,
social renting, and private renting. For each EHS year, the open point estimate
for tenure $k$ among HRPs aged 25–44 is prospectively fixed as

$$
\widehat{s}_{k,25\text{--}44}
=100\times
\frac{\widehat{N}_{k,25\text{--}34}+\widehat{N}_{k,35\text{--}44}}
{\widehat{N}_{all,25\text{--}34}+\widehat{N}_{all,35\text{--}44}}.
$$

This authorizes a new open source record, `EHS_FA1201_OPEN`, for:

- `AF01_OWNER_25_44` and `AF02_PRS_25_44` **point estimates**;
- the three-broad-tenure point-estimate path corresponding to the public part
  of `AF03_TENURE_PATH`; and
- reproduction checks against the table's within-age percentages.

The public table does not expose replicate weights, strata/PSU variables, or
the covariance needed for the registered design-based confidence intervals. It
also does not provide the full fine-tenure categories registered for the EUL
analysis. Accordingly:

- design-based confidence intervals for `AF01` and `AF02` remain
  `UKDS_EHS_EUL` dependencies;
- the fine-category version of `AF03` remains EUL-dependent; and
- public counts must not be treated as independent observations when age bands
  are combined or endpoint changes are formed.

## 3. Outcome-viewing disclosure

During source-feasibility work on 2026-08-01, before this amendment and before
the pipeline was implemented, the open table was inspected and the registered
combination above was hand-calculated. The observed point estimates were:

| England, HRP age 25–44 | 2008–09 | 2018–19 | Change |
|---|---:|---:|---:|
| Owner occupation | 60.5270% | 48.5783% | -11.9487 pp |
| Private renting | 22.1325% | 34.4594% | +12.3269 pp |
| Social renting | 17.3405% | 16.9623% | -0.3783 pp |

These values are therefore labelled **previously observed public accounting
facts**, not untouched confirmatory outcomes. The manifest-bound run tests
source pinning, extraction, arithmetic, denominators, and reproducibility; it
does not test a newly revealed directional hypothesis. No confidence interval
or causal interpretation is attached to the open-table changes.

The HPI/PIPR endpoint calculation was also performed during the same
feasibility work. From January 2015 to December 2019, England HPI increased by
22.388%, PIPR increased by 11.939%, and the January-2015-normalized ratio of the
two indices increased by 9.3346%. This is likewise a **previously observed
public accounting fact**. It is a relative price-to-stock-rent index, not a
gross or net rental yield, and the manifest-bound run is a reproduction rather
than untouched confirmation of its value.

The net-supply component table was inspected during implementation feasibility.
Before the manifest-bound run, an absolute reconciliation tolerance of 50
dwellings was fixed for the published unrounded component sum against the
published total. The observed source residuals are retained in output rather
than forced to zero. This is a schema and arithmetic quality-control rule, not
an inferential threshold or an untouched test outcome.

## 4. Property-flow evidence correction

“Gross owner-to-landlord and landlord-to-owner flows are absent” is narrowed to
the following source-bound statement:

> The unrestricted open public core does not directly label seller tenure,
> buyer landlord status, or gross owner-to-landlord and landlord-to-owner
> conversions.

It is not permissible to say that those flows have never been measured. Prior
Bank of England and academic work matches Land Registry transactions to
proprietary WhenFresh/Zoopla rental listings. The Bank's 2023 measure classifies
owner-occupier-to-landlord, landlord-to-owner-occupier, and
landlord-to-landlord property flows for England and Wales using four-year
listing rules and data beginning in November 2008. The measure is incomplete,
lagged, revision-prone, and subject to classification error; crucially, it does
not observe the purchaser's top non-housing resources.

Linked listing-transaction data available under safeguarded or proprietary
access may support a later property-flow validation module. Such access is not
part of this open Gate A run and would require a separate decision, licence,
and protocol. No first-linkage, first-flow-measure, or wholly-unmeasured-flow
claim is permitted.

## 5. Public Gate A block map

The manifest-bound open-data run may execute:

- `AF01` and `AF02` as point estimates only;
- the three-broad-tenure point-estimate portion of `AF03`;
- `AF07` England HPI;
- `AF08` as two separately labelled rent-method segments, never level-spliced;
- `AF09` as a normalized price-to-stock-rent index, never a rental-yield level;
- `AF11` net additions and the registered stock denominator;
- `AF12` on the exact common support of the two quoted-rate series; and
- `AF13` if the FCA table schema and long-run definitions pass validation.

`AF10` remains conditional on an audited England/Wales geography concordance.
Raw PPD address or postcode fields must not be redistributed; only derived
annual counts and non-identifying validation summaries may leave the raw-data
boundary. `AF14` is limited to moments explicitly published in the EPLS 2018
report or open tables; intentions are not realized exits or acquisitions.

`AF04`–`AF06`, EHS design covariance, and the full fine-tenure path remain
EUL-blocked. Their absence is reported as missing evidence, never imputed with
zero or replaced by an adjacent published statistic.

## 6. Claim ceiling for the redirected paper

The public accounting paths may establish measured aggregate changes at their
stated geographies and denominators. They cannot identify whether top-resource
pressure, middle-resource loss, credit, supply, tax, rates, demographics,
social comparison, rental segmentation, or institutional entry generated those
changes.

Any set-valued attribution must state its response-set provenance. The current
IDENT-0 loadings and four constructed rival signatures are synthetic design
inputs. They can establish algebraic observational equivalence inside the
stress-test system, but they cannot be described as England elasticities,
empirical rival prevalence, or statistical confidence coverage.
