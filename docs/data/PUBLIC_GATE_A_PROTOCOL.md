# Public Gate A accounting protocol

**Version:** 0.1 + preregistration amendments 01–03  
**Decision scope:** licence-safe public accounting only  
**Authoritative upstream result:** `FAIL-IDENT-0`

## Purpose and stop rule

This run reproduces a bounded set of official public housing series and their
registered arithmetic. It does not rescue the failed unique-attribution design.
The only authorized success label is
`OPEN-SUBSET-REPRODUCED+FULL-GATE-A-HELD`. The runner has no code path that can
emit a full Gate A pass, authorize MIN-EXEC, or estimate a historical
top-resource contribution.

The following remain controlling absences: EHS design covariance and fine
tenure, WAS net financial plus business wealth by rank and tenure, an audited
PPD England/Wales concordance, source-backed rival response sets, and a direct
observation of purchaser top non-housing resources.

## Source boundary

`configs/gatea_public.json` fixes each official HTTPS download by source ID,
publisher, landing page, exact URL, filename, byte ceiling, media type, host
allowlist, access tier, licence statement, and SHA-256. A redirect outside the
allowlist, oversized response, media mismatch, or hash drift stops the run.
Offline replay is accepted only when the local bytes match the same registered
digest. Raw files are copied into a new, non-overwriting run directory.

The core window and provenance seed are fixed at 2008–2019 and `20260801`.
There are no stochastic transformations in Gate A; the seed is retained solely
to bind this run to the wider preregistered programme.

The open subset comprises:

- EHS FA1201 broad-tenure weighted household counts for HRP age 25–44;
- HM Land Registry unadjusted all-property England HPI;
- ONS historical IPHRP through 2014 and PIPR from 2015, retained as separately
  labelled method segments;
- MHCLG dwelling stock and components of net housing supply;
- Bank of England quoted owner and buy-to-let mortgage rates on exact common
  support.

The source files are public under their recorded publisher terms. This protocol
does not authorize redistribution of EUL, safeguarded, proprietary listing, or
address-level PPD data.

## Registered transformations

For each EHS year, owner, private-renter, and social-renter weighted counts for
ages 25–34 and 35–44 are added and divided by the common all-tenure denominator.
The three counts and shares must close. These are point estimates only: no
independence assumption or confidence interval is permitted without the survey
design covariance. If a sheet does not publish age-band unweighted sample
sizes, the output remains missing; its all-age sample total is not substituted.

Monthly England HPI must contain 144 consecutive observations from January
2008 through December 2019. Historical IPHRP must contain 84 consecutive
observations through December 2014; PIPR must contain 60 consecutive
observations from January 2015 through December 2019. IPHRP and PIPR levels are
never spliced. The registered price-to-stock-rent series uses only matched HPI
and PIPR months, normalizes each to January 2015, and divides the two normalized
indices. It is not a gross or net rental yield.

Annual HPI levels are arithmetic means of all 12 monthly observations. Annual
growth is 100 times the December-to-December log difference; 2008 is missing
because December 2007 lies outside the extracted core. The annual-average log
level is normalized to the 2008 annual mean for the registered target path.

Annual net additions are divided by all dwellings, including vacant dwellings,
at the start of the corresponding financial year. Publisher component
residuals are reported rather than forced to zero. The implementation-stage
schema check accepts an absolute source-table component residual of at most 50
dwellings; this tolerance was set during pre-run table inspection and is a
quality-control rule, not an inferential threshold or untouched result. Quoted mortgage products are
UK offer rates, not realized England borrower costs; missing BTL observations
before January 2012 are retained as missing.
Annual owner-rate means require all 12 monthly owner observations. Annual BTL
and spread means remain missing unless all 12 common-support months are present.

## Outcome-viewing disclosure

Before the manifest-bound implementation, feasibility work inspected the open
EHS endpoints and calculated the 2015–2019 HPI/PIPR relative-index endpoint.
The run therefore reproduces previously observed public accounting facts. It is
not an untouched directional test.

## Reproducibility and assurance

The command requires a clean committed worktree, hashes its configuration,
code, lockfile, protocol, claim ledger, and Stage 1 decision, then writes:

- `MANIFEST.json` for code and environment provenance;
- immutable raw source copies and `SOURCE_RECEIPTS.json`;
- derived CSVs with stable float/date serialization and table-level hashes;
- descriptive PDF/SVG figures;
- machine-readable and human-readable reports; and
- `ARTIFACT_MANIFEST.sha256` binding all preceding artifacts.

All scientific invariants use explicit exceptions rather than Python
`assert`, so they remain active under `python -O`. Hash agreement authenticates
bytes and replay scope; it does not establish the validity of the underlying
survey method, the truth of a causal claim, or independent replication.
