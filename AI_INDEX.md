# AI index — stocks-are-not-flows

## Identity and version

Documentation addendum: 2026-09-24. Indexes [source commit cf313dd21d17](https://github.com/ipitchford/stocks-are-not-flows/tree/cf313dd21d17865a40f5973f2bb14efc57403bd9) and candidate tag `v1.0.0-preprint`. This index was added after that release: it is **not** part of the original tag, DOI archive or frozen manifest. Existing release files and checksums remain unchanged. For historical manifest/allow-list checks, use a clean checkout of that tag, not this documentation-enriched branch. The addendum is authenticated by Git history.

[Release identity and DOI](README.md) · [Evidence Press context](https://evidencepress.org/releases/stocks-are-not-flows/)

## Exact scope

An England 2008–2019 housing-tenure identification audit. The registered observation map cannot distinguish the focal resource channel from admitted rival mechanisms. IDENT-0 returned FAIL-IDENT-0; no causal coefficient, historical contribution share or empirical England partial-identification interval is reported.

The linked manuscript and claim register control all hypotheses and quantifiers; this index is a navigation aid, not a substitute proof.

## Claim and evidence map

- [paper/README.md](paper/README.md) — Paper entry point.
- [docs/model/CLAIM_LEDGER.md](docs/model/CLAIM_LEDGER.md) — Claim ledger.
- [ASSURANCE.md](ASSURANCE.md) — Trust boundaries.
- [configs/ident0.json](configs/ident0.json) — Registered design.
- [docs/identification/IDENT0_PROTOCOL.md](docs/identification/IDENT0_PROTOCOL.md) — Identification protocol.
- [docs/identification/PARTIAL_IDENTIFICATION_PROTOCOL.md](docs/identification/PARTIAL_IDENTIFICATION_PROTOCOL.md) — Conditional set protocol.
- [docs/publication/DECISIVE_SOURCE_LEDGER.md](docs/publication/DECISIVE_SOURCE_LEDGER.md) — Sources.
- [AUTHORSHIP_AND_DISCLOSURE.md](AUTHORSHIP_AND_DISCLOSURE.md) — Provenance.
- [THIRD_PARTY_DATA.md](THIRD_PARTY_DATA.md) — Third-party rights.
- [LICENSE](LICENSE) — Original-content licence.

## Reproduce

From the indexed release root, after inspecting the commands and installing the documented environment:

```sh
uv sync --extra dev --no-editable
PYTHONPATH=src uv run pytest
PYTHONPATH=src uv run python -O -m pytest
PYTHONPATH=src uv run python -O -m housing_pressure.ident0.selfcheck
```

Frozen public inputs and allow-listed outputs are committed. README gives regeneration commands and report hashes. Expected scientific decisions differ by gate: FAIL-IDENT-0, OPEN-SUBSET-REPRODUCED+FULL-GATE-A-HELD, and STOP-UNIQUE+GO-PARTIAL-ID-THEORY.

## Trust boundary and safe reuse

A design audit and public accounting layer, not an estimated housing model or evidence that wealthy investors had no effect. Synthetic geometry inputs are not empirical estimates. Deterministic self-replay is not independent replication.

No new mathematical validation, formalisation, independent reproduction or novelty audit was performed for this documentation repair. Preserve the anonymous attribution and existing citation metadata. Distinguish producer checks, finite formal results, universal written arguments and external review. Before downstream reuse, match the exact statement and dependency scope and check subsequent corrections; a DOI or successful command alone is not proof of correctness.

## Licence and provenance

Use the rights/provenance sources linked above and [README](README.md); cited and third-party material retains its own terms. This new index is dedicated under CC0-1.0, without changing any existing licence or attribution.

