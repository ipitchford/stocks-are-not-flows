# Data boundary

Raw licensed microdata are never committed. Public and licensed sources keep
their publisher geography and denominator:

- England: EHS and England housing/price/supply series;
- Great Britain: Wealth and Assets Survey;
- United Kingdom: mortgage and contextual macro-financial series; and
- England and Wales: Land Registry ownership datasets when separately licensed.

The first public-data stage records immutable retrieval receipts, hashes,
licences, official benchmark reproduction, variable concordances, and
exclusion/denominator flows. EHS and WAS EUL downloads require the user to
accept the relevant licences; this repository does not automate acceptance.

The v1.0.0 public discussion preprint redistributes only the seven official,
open-publication files under `results/gatea/20260801-open-subset-v2/raw/`.
Their source URLs, retrieval timestamps, SHA-256 digests, publishers, and Open
Government Licence statements are in `SOURCE_RECEIPTS.json` and
`THIRD_PARTY_DATA.md`. No EUL, safeguarded, proprietary, or address-level data
are included.

Prospectively frozen non-target diagnostics are excluded from fitting, tuning,
parameter bounds, and model selection. They are not described as blinded or
statistically independent.
