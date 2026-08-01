# Stocks Are Not Flows

**Public discussion preprint v1.0.0 — anonymous, unrefereed, and not independently reproduced.**

This repository contains the reproducible identification audit and public
accounting layer for an England 2008–2019 housing-tenure research programme.

- Paper and archival record: <https://doi.org/10.5281/zenodo.21740339>
- Repository: <https://github.com/ipitchford/stocks-are-not-flows>
- Verification boundary: [`ASSURANCE.md`](ASSURANCE.md)
- Official-source attribution: [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md)

## Result in one paragraph

England's public tenure, price, rent, mortgage-rate, and housing-supply series
document a substantial shift from ownership to private renting. They do not,
however, identify how much—if any—was caused by rising resources at the top.
The registered observation map cannot distinguish that channel from admitted
credit, supply, demographic, tax, and other resource mechanisms. This is not a
finding that wealthy investors had no effect. It is a finding that the aggregate
data usually cited cannot determine the effect.

IDENT-0 is a design audit, not an estimated housing model. Its authoritative run
returned `FAIL-IDENT-0`, stopping the planned structural estimation and unique
historical attribution. The remaining work reproduces public accounting paths,
certifies the synthetic focal-versus-rival geometry, and supplies conditional
sharp-set tools. It reports no causal coefficient, historical contribution
share, or empirical England partial-identification interval.

## Assurance boundary

- `z_T` is an aggregate resource-flow primitive, not a wealth share or measured
  saving.
- Every experiment has explicit units and a closure class.
- Public-unit adapters keep tenure as percentage levels and rent as pounds per
  week; configured baselines and diagonal scales are synthetic design inputs.
- The unrestricted open core does not jointly observe gross property-use
  conversion, purchaser landlord identity, and purchaser top non-housing
  resources.
- The broad rich-investor housing mechanism is inherited prior art.
- Null, sign-reversing, partially identified, and near-zero results are valid.
- Deterministic replay is self-reproduction, not independent replication.

## Reproduce and test

The frozen public inputs and allow-listed results needed by the paper and tests
are committed in this release.

```bash
uv sync --extra dev --no-editable
PYTHONPATH=src uv run pytest
PYTHONPATH=src uv run python -O -m pytest
PYTHONPATH=src uv run python -O -m housing_pressure.ident0.selfcheck
```

To regenerate new result directories:

```bash
PYTHONPATH=src uv run housing-ident0 \
  --config configs/ident0.json \
  --output-dir results/ident0/<new-run-id>
PYTHONPATH=src uv run housing-gatea \
  --config configs/gatea_public.json \
  --output-dir results/gatea/<new-run-id>
PYTHONPATH=src uv run housing-partialid \
  --output-dir results/partialid/<new-run-id>
```

The IDENT-0 command can issue `FAIL-IDENT-0` or
`CONTINUE-TO-FULL-GATE`; it cannot issue `PASS-IDENT-0`. Gate A's bounded
success label is `OPEN-SUBSET-REPRODUCED+FULL-GATE-A-HELD`; it cannot authorise
structural estimation. The partial-ID command can emit only
`STOP-UNIQUE+GO-PARTIAL-ID-THEORY`, never an empirical England bound.
Scientific gates use explicit exceptions and return objects rather than Python
`assert` statements, so they remain active under `python -O`.

## Frozen evidence anchors

The report files and their sidecar hashes are committed. Development-commit
identities below refer to the private working history used to generate the
frozen runs; that history is intentionally not redistributed because it contains
personal metadata and local paths. The clean public history contains the exact
release payload without those fields.

| Layer | Authoritative run | Development commit | Decision | Report SHA-256 |
|---|---|---:|---|---|
| IDENT-0 | `results/ident0/20260801-ident0-failfast-v2` | `1e04a181` | `FAIL-IDENT-0` | `049ec5f8c3e290d1c0273c8630e3c8d1eeee8c2191427fcd9742803060bfca35` |
| public Gate A | `results/gatea/20260801-open-subset-v2` | `836e3391` | `OPEN-SUBSET-REPRODUCED+FULL-GATE-A-HELD` | `97925770879ca8f9e356c067c9d9c6b4b98d5d098113354485002bed8bcc2f08` |
| public Gate A replay | `results/gatea/20260801-open-subset-v2-replay` | `836e3391` | deterministic offline replay | `51aa01e7a0b2fe14aed73e3d3ff43b533637f1e43f91a0bc96598ef54f1cc530` |
| design geometry | `results/partialid/20260801-design-geometry-v1` | `836e3391` | `STOP-UNIQUE+GO-PARTIAL-ID-THEORY` | `421ce83b335bf610e2f7fa3cfb178b6a2ebc7620098d05b9f5601d164cb1d7fc` |

The Gate A replay has byte-identical raw, derived, and PDF/SVG figure
directories after excluding run-specific manifest fields. This establishes
deterministic replay of the registered transformations, not independent
reproduction or causal validity.

## Authorship, licence, and data

The public discussion preprint is cited as `Anonymous`. Automated research and
coding tools assisted discovery, implementation, testing, critique, and drafting;
they are not authors. See [`AUTHORSHIP_AND_DISCLOSURE.md`](AUTHORSHIP_AND_DISCLOSURE.md).

To the extent possible under law, the original manuscript, documentation, code,
and original figures are dedicated to the public domain under CC0 1.0. The seven
redistributed official-source files retain their publishers' Open Government
Licence terms and attribution. No supplied thesis, safeguarded or proprietary
microdata, address-level records, or cached literature PDFs are redistributed.
