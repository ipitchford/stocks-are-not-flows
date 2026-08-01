# Public discussion preprint integrity report

**Version:** 1.0.0

**Date:** 2026-08-01

**Classification:** anonymous, unrefereed public discussion preprint

## Release checks completed

| Check | Result |
|---|---|
| Normal Python test suite | 135/135 passed |
| `python -O` test suite | 135/135 passed; expected Pytest assertion warning recorded |
| Optimized IDENT-0 selfcheck | PASS: 57 adapted targets, 6,573 planned fits, 313 truth cases |
| Ruff | PASS |
| Public result manifest | all 37 listed report, receipt, table, figure, and raw-input files passed SHA-256 |
| JSON and CFF syntax | PASS |
| LaTeX/BibTeX build | PASS; 30 pages; no missing characters, overfull boxes, or unresolved citations/references |
| PDF structural check | `qpdf --check` PASS |
| PDF metadata | title, Anonymous author, subject, and keywords present |
| PDF fonts | all embedded; frozen Matplotlib figures retain embedded Type 3 DejaVu Sans glyphs |
| Deterministic PDF rebuild | byte-identical across two builds with fixed `SOURCE_DATE_EPOCH` |
| Privacy/secret scan | no personal email, local home-directory path, API-key pattern, or internal token-budget text found |

The frozen PDF SHA-256 is:

`750707b4924daf9a6504ed5c3b5dbee7d6b7d6c885d1c3d74688081a313c2523`

## Scientific integrity boundary

The title, abstract, results, conclusion, README, assurance record, and planned
press wording preserve `STOP-UNIQUE` and `STOP-CAUSE`. The package does not turn
adversarial design cases into sampling frequencies, tenure stocks into gross
property flows, the price-to-stock-rent index into a yield, or synthetic response
columns into empirical elasticities.

Tectonic/BibTeX resolution establishes that citation keys and bibliography entries
are mechanically complete. The earlier novelty/source audit and decisive-source
ledger are included, but this release has not received an independent expert
line-by-line source/claim-context audit. It has also not received independent
reproduction, formal verification, editorial acceptance, or peer review.

## Privacy-preserving provenance

The internal run manifests and development Git bundle were excluded because they
contained local executable paths and personal commit metadata. Their SHA-256
identities are recorded in `results/PROVENANCE_REDACTION.md`. The public reports,
raw official inputs, derived tables, and figures remain byte-identical and are
bound by `results/PUBLIC_RESULT_MANIFEST.sha256`.

## Release decision

The package is fit for release as an **anonymous public discussion preprint**
whose central result is structural non-identification. It is not represented as
journal-ready, independently reproduced, or evidence that wealthy saving either
caused or did not cause England's tenure shift.
