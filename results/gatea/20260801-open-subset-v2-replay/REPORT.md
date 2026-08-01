# Public Gate A accounting report

**Decision:** `OPEN-SUBSET-REPRODUCED+FULL-GATE-A-HELD`  
**Full Gate A authorized:** `false`  
**Protocol:** `public-pilot-0.1+amendments-01-03`  
**Core period:** England housing 2008-2019; GB/UK sources retain publisher geography  
**Run manifest SHA-256:** `f00bfcace904d7a3cb6fcb8746d1fb0346b38e74de6d67224d868ccb0a03a57b`

The hash-pinned open subset reproduced the declared accounting paths. This is not a pass of the full evidence gate and does not identify a top-resource contribution.

## Accounting facts

### AF01_OWNER_25_44_POINT

| Field | Value |
|---|---|
| geography | England |
| population | private households with HRP age 25-44 |
| base_period | 2008-09 |
| base_pct | 60.5270 |
| end_period | 2018-19 |
| end_pct | 48.5783 |
| change_pp | -11.9487 |
| uncertainty | design covariance unavailable in open table |
| viewing_status | previously observed during feasibility |

### AF02_PRS_25_44_POINT

| Field | Value |
|---|---|
| geography | England |
| population | private households with HRP age 25-44 |
| base_period | 2008-09 |
| base_pct | 22.1325 |
| end_period | 2018-19 |
| end_pct | 34.4594 |
| change_pp | 12.3269 |
| uncertainty | design covariance unavailable in open table |
| viewing_status | previously observed during feasibility |

### AF03_BROAD_TENURE_PATH

| Field | Value |
|---|---|
| status | point-estimate path reproduced for owner/private/social only |
| years | 11 |
| fine_tenure_and_covariance | EUL blocked |

### AF07_HPI_PATH

| Field | Value |
|---|---|
| geography | England |
| base_date | 2008-01-01 |
| base_index | 63.3 |
| end_date | 2019-12-01 |
| end_index | 82.0 |
| endpoint_pct_change | 29.5419 |
| endpoint_100_log_change | 25.8834 |

### AF08_RENT_SEGMENTS

| Field | Value |
|---|---|
| geography | England |
| iphrp_period | 2008-01-01 to 2014-12-01 |
| iphrp_pct_change | 12.6554 |
| pipr_period | 2015-01-01 to 2019-12-01 |
| pipr_pct_change | 11.9390 |
| level_splice | prohibited |

### AF09_PRICE_RENT_INDEX

| Field | Value |
|---|---|
| geography | England |
| period | 2015-01-01 to 2019-12-01 |
| price_to_stock_rent_pct_change | 9.3346 |
| stock_rent_to_price_pct_change | -8.5377 |
| interpretation | normalized relative index; not a gross or net rental yield |
| viewing_status | previously observed during feasibility |

### AF11_NET_ADDITIONS

| Field | Value |
|---|---|
| geography | England |
| first_period | 2008-09 |
| first_rate_pct | 0.8119 |
| last_period | 2018-19 |
| last_rate_pct | 1.0233 |
| denominator | all dwellings including vacant dwellings at start of FY |

### AF12_MORTGAGE_COST

| Field | Value |
|---|---|
| geography | United Kingdom |
| common_start | 2012-01-01 |
| common_end | 2019-12-01 |
| common_months | 96 |
| first_spread_pp | 2.0100 |
| last_spread_pp | 0.5100 |
| mean_spread_pp | 1.2573 |
| annual_owner_path_years | 12 |
| annual_btl_and_spread_complete_years | 8 |
| interpretation | quoted product rates; not realized borrower costs |

## Validation checks

| Check | Status | Expected |
|---|---:|---|
| ehs_2008-09_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2008-09_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2009-10_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2009-10_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2010-11_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2010-11_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2011-12_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2011-12_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2012-13_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2012-13_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2013-14_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2013-14_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2014-15_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2014-15_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2015-16_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2015-16_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2016-17_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2016-17_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2017-18_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2017-18_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_2018-19_tenure_closure | PASS | three broad tenures close to the common 25-44 denominator |
| ehs_2018-19_published_percentage_reproduction | PASS | maximum age-specific difference no greater than 1e-10 percentage points |
| ehs_core_path | PASS | 11 EHS financial years from 2008-09 through 2018-19 |
| ehs_unweighted_sample_availability | PASS | only 2013-14 lacks a published 25-44 unweighted sample size |
| hpi_schema | PASS | ['Date', 'Region_Name', 'Area_Code', 'Index'] |
| hpi_england_months | PASS | 144 unique consecutive months from 2008-01-01 |
| hpi_geography_and_domain | PASS | England only with a positive unadjusted all-property index |
| iphrp_schema | PASS | frozen version-25 long-format CSVW fields |
| iphrp_england_months | PASS | 84 unique consecutive months from 2008-01-01 |
| iphrp_geography_and_domain | PASS | England only with a positive historical stock-rent index |
| pipr_schema | PASS | 40-column Table 1 with time, area, overall index, and rental price |
| pipr_england_months | PASS | 60 unique consecutive months from 2015-01-01 |
| pipr_geography_and_domain | PASS | England only with positive PIPR index and estimated monthly rent |
| hpi_annual_support | PASS | 12 annual means and 11 within-core December-to-December growth values |
| price_rent_normalization | PASS | 60 matched months and January 2015 ratio exactly one |
| net_additions_core_years | PASS | FY2008-09 through FY2018-19 |
| net_additions_component_reconciliation | PASS | absolute published component residual no greater than 50 dwellings |
| boe_schema | PASS | ['DATE', 'IUMBV34', 'IUMZID4'] |
| boe_owner_months | PASS | 144 unique consecutive months from 2008-01-01 |
| boe_common_support | PASS | 96 unique consecutive months from 2012-01-01 |
| boe_registered_support_gate | PASS | at least 36 consecutive common-support months |
| boe_positive_rate_domain | PASS | all published quoted rates strictly positive |
| boe_annual_common_support | PASS | zero BTL months in 2008-2011 and twelve common months in every 2012-2019 year |

## Source receipts

| Source | Mode | Bytes | SHA-256 |
|---|---|---:|---|
| EHS_FA1201_OPEN | offline_hash_verified_copy | 106370 | `f095268b6330ec5e4733b0474f53d8b79d7a6932dc939e0b65196799d54252ac` |
| HMLR_UKHPI_INDICES_2026_05 | offline_hash_verified_copy | 5793660 | `cacaef81b8f09c0b1c67c9a8a7c077134384a1be4dd1b1ddf26a9c52656620a5` |
| ONS_IPHRP_HIST_V25 | offline_hash_verified_copy | 434278 | `bf87cfd293323df5c558a203635d69c16b9b1c48485d410afc19563c016228f1` |
| ONS_PIPR_2026_07_22 | offline_hash_verified_copy | 18370943 | `d429e553ade454903b731f6c257609f14d0c2171822791e09c21a9d53d5e24a9` |
| MHCLG_DWELLING_STOCK_LT104_2026_05 | offline_hash_verified_copy | 13637 | `ecd02eb8e520e4fef7878bda35db002ca2360cb45112416db6619863b211a1fa` |
| MHCLG_NET_SUPPLY_LT120_2025_11 | offline_hash_verified_copy | 14471 | `548101e535b7db4e0718a1ef3129e343169cb3982f1cd8e03c0f247e93c5d219` |
| BOE_QUOTED_RATES_2008_2019 | offline_hash_verified_copy | 3119 | `d5c17cabc1103c3396695f389c6384b745ce58e8f4f07787f83d82a62127f009` |

## Outputs still blocked

| Output | Reason |
|---|---|
| AF01_AF02_DESIGN_COVARIANCE | EHS public tables do not expose survey-design covariance; UKDS EUL microdata remain required |
| AF03_FINE_TENURE | the open table contains three broad tenures rather than the registered fine categories |
| AF04_AF06_NHW | net financial plus net business wealth and tenure-by-rank require WAS EUL microdata |
| AF10_PPD_TURNOVER | an audited England/Wales geography concordance is required before streaming PPD |
| AF13_FCA_MLAR | the long-run FCA table is prepared as a separate schema-pinning extension |
| AF14_EPLS | only explicitly published 2018 report moments may enter a later bounded holdout module |
| GROSS_TENURE_FLOWS | not labelled in the unrestricted open core; prior proprietary linked-listing estimates are context, not open inputs |

## Assurance boundary

- The open EHS results are point estimates without public design covariance.
- IPHRP and PIPR are separate method segments and are never level-spliced.
- The price-to-stock-rent index is not a gross or net rental yield.
- Dwelling-stock and household-tenure denominators are not interchangeable.
- Quoted mortgage rates are United Kingdom offers, not realized England borrower costs.
- No public series identifies the latent top non-housing resource flow.
- WAS net non-housing wealth outputs and full EHS inference remain EUL-blocked.
- This run cannot authorize structural estimation, unique attribution, or causal language.

The EHS endpoint values and the 2015–2019 HPI/PIPR relative-index change were observed during feasibility work. Their appearance here is a source and arithmetic reproduction, not untouched confirmation.
