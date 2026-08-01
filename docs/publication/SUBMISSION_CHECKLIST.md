# Submission checklist

## Scientific claims

- [ ] Title, abstract, introduction, conclusion, tables, and cover letter use the
  same `STOP-UNIQUE` and `STOP-CAUSE` ceiling.
- [ ] No sentence turns the four adversarial cases into a sampling frequency.
- [ ] No sentence treats tenure-stock changes as gross owner-to-landlord flows.
- [ ] No sentence calls the HPI/PIPR relative index a yield.
- [ ] Synthetic columns, scales, and rival signatures are labelled design inputs.
- [ ] The absence of an empirical England bound is stated in the abstract,
  results, discussion, appendix, and availability declaration.

## Source and data audit

- [ ] Re-open every cited primary source and verify title, author, version, date,
  DOI, page anchor, and claim support.
- [ ] Confirm that the 2026 EHS live-table update and 2022 IPHRP version date are
  rendered correctly despite legacy citation keys.
- [ ] Retain the 2019 Bank quoted-rate methodology-break disclosure.
- [ ] Confirm that every distributed raw public object is permitted under its
  recorded publisher terms.
- [x] Choose an explicit licence for original code and manuscript source; v1.0.0
  uses CC0 1.0, while official data retain their publisher OGL terms.
- [ ] Do not include supplied thesis PDFs, proprietary listing data, safeguarded
  microdata, or address-level records in a public archive without permission.

## Reproducibility

- [ ] Run all 135 tests under normal Python.
- [ ] Run all 135 tests under `python -O` and record the expected Pytest warning
  that test-module assertions are disabled; scientific guards use exceptions.
- [ ] Run Ruff and the optimized IDENT-0 selfcheck.
- [ ] Validate each authoritative report and artifact manifest by SHA-256.
- [ ] Re-run the release from a fresh extraction and check rejection controls.
- [ ] Have an independent reproducer run the package on a separate checkout.

## Manuscript and editorial fields

- [ ] Replace `Anonymous` only after the journal's anonymisation rule
  is known.
- [ ] Complete affiliations, corresponding author, funding, acknowledgements,
  competing interests, CRediT roles, and data/code DOI.
- [ ] Obtain every named author's approval of the exact submitted PDF.
- [ ] Apply target-journal class/style, line numbering, word limit, and reference
  style without changing the scientific claim ceiling.
- [ ] Review the AI/computational-assistance disclosure against the journal's
  current policy.
- [ ] Prepare a cover letter that leads with the identification result and does
  not market the project as a causal estimate.

## PDF quality

- [ ] Compile from the released source tree.
- [ ] Confirm all references and citations resolve.
- [ ] Run `qpdf --check` and inspect every page at readable zoom.
- [ ] Confirm tables 4–5 precede Reproducibility, tables 6–7 open that section,
  and References are the final section.
- [ ] Confirm all fonts are embedded and ask the target journal whether Type 3
  fonts inside the frozen Matplotlib figures require a publication-only export.
