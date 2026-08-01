# Manuscript build and assurance boundary

`main.tex` is the anonymous submission manuscript **Stocks Are Not Flows: An
Identification Audit of Investor Pressure and Tenure Change in England**.

## Build

The manuscript expects the repository layout to remain intact because it imports
the three authoritative Gate A PDF figures from
`results/gatea/20260801-open-subset-v2/figures`.

From this directory, compile with a current Tectonic distribution:

```bash
tectonic -X compile --outdir build main.tex
```

The verified project build used the bundled Tectonic 0.16.9 runtime through the
local LaTeX compilation workflow. A complete build resolves BibTeX automatically
and writes `build/main.pdf`. TeX Live with `latexmk -pdf` is also suitable when
the packages imported by `main.tex` are installed.

Validate the result with:

```bash
qpdf --check build/main.pdf
pdftotext -layout build/main.pdf build/main.txt
```

The release build is 30 US-letter pages. All references resolve. Compiler notices
are limited to underfull spacing in narrow evidence-table cells; no text or table
is clipped in the inspected PDF.

## Source map

- `main.tex`: article narrative, measurement ontology, two main propositions,
  minimum-data result, discussion, and declarations.
- `results_and_reproducibility.tex`: exact IDENT-0, Gate A, replay, and
  design-geometry results with immutable commit and SHA-256 identities.
- `appendix_theory.tex`: nine conditional linear-algebra, convex-analysis, and
  stock-flow results. The mathematics is explicitly described as standard; the
  housing-specific contribution is its disciplined application.
- `references.bib`: source-verified bibliography, including correct version and
  publisher dates for the public datasets.

## Claim ceiling

This is a publication candidate for an identification/measurement contribution.
It is not an empirical estimate of the effect of top wealth on English tenure.
In particular, it reports no causal coefficient, historical contribution share,
or empirical England partial-identification interval. The public facts are
accounting results; the span result is a deterministic certificate for synthetic
design inputs.

Before submission, named authors must complete funding, competing-interest,
affiliation, acknowledgements, and authorship declarations and approve every
sentence and source.
