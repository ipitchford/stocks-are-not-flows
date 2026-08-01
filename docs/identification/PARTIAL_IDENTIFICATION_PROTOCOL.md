# Partial-identification and design-geometry protocol

## Status and claim ceiling

This protocol implements a deterministic mathematical layer for the post-IDENT-0
pivot. It answers two conditional questions:

1. Does a supplied focal response column have any direction outside the span of
   supplied nuisance and rival columns?
2. Given an observed response equation and box restrictions on nuisance
   coefficients, what is the sharp interval for the focal coefficient?

Neither calculation validates that a response column is an empirical response
for England. Geometry results are labelled **DESIGN_INPUT_GEOMETRY_ONLY**;
interval results are labelled **CONDITIONAL_RESPONSE_SET_ONLY** and carry
**empirical_england_bound = false**. A source/provenance and transport review is
a separate gate.

The module therefore supports **GO-PIVOT-THEORY** and conditional bounds work. It
does not reverse the authoritative **FAIL-IDENT0**, authorize unique attribution,
or supply a causal estimate of wealth-driven tenure change.

## 1. Focal-versus-rival geometry

Let $f\in\mathbb{R}^m$ be the focal response column and let
$N\in\mathbb{R}^{m\times k}$ collect all admitted nuisance and rival response
columns. The module first normalizes every nonzero column of $N$ to unit
Euclidean norm, then computes the truncated-SVD projection

\[
  \hat f = P_N f, \qquad r=(I-P_N)f.
\]

The focal coefficient is point-identified against this admitted linear span if
and only if $r\neq0$. Numerically, the span decision is made on the relative
residual (the residual of a unit-norm focal column):

\[
  \frac{\lVert r\rVert_2}{\lVert f\rVert_2}
  \leq a_{\mathrm{tol}}+r_{\mathrm{tol}}.
\]

Individual nuisance-column normalization and the relative focal residual make
the span decision invariant to harmless changes of units. The certificate
records the original column norms, both tolerances, the effective threshold,
normalized-design singular values and projection coefficients, ranks, and
residual norms. The tolerance is part of the scientific contract and must not be
selected after observing the desired classification.

### Dual discriminator

When $r\neq0$, define

\[
  d = \frac{r}{r^\top r}.
\]

Because $r$ is orthogonal to the retained column space of $N$,
$d^\top N=0$, while $d^\top f=1$. Thus $d$ is a constructive discriminator:
it combines moments so that every admitted nuisance response cancels while the
focal response remains. If $f\in\operatorname{col}(N)$, no such linear
discriminator exists and the certificate returns no discriminator.

These statements concern the supplied matrix. Adding repeated time ramps or
rescaled copies cannot create a new identifying direction because those columns
remain in the same span.

## 2. Sharp interval under box-bounded nuisance

For a supplied response vector $y$, the conditional response set is

\[
 \mathcal{C}=\{(\beta,\gamma):
 y=f\beta+N\gamma,\; \ell\leq\gamma\leq u\}.
\]

Optional bounds may also be imposed on $\beta$. The lower and upper endpoints
are the linear programs

\[
 \underline\beta=\min_{(\beta,\gamma)\in\mathcal C}\beta,
 \qquad
 \overline\beta=\max_{(\beta,\gamma)\in\mathcal C}\beta.
\]

The implementation uses SciPy's HiGHS backend. Since $\mathcal C$ is convex and
the projection of a convex set onto one coordinate is an interval, finite
attained optima are sharp conditional on the supplied equalities and boxes. Each
endpoint includes its coefficient witness, equality residual, and box-violation
audit.

**INFEASIBLE** is a substantive outcome: the response, design, and restrictions
cannot all hold. **UNBOUNDED** means at least one endpoint is infinite; JSON
output uses null, never non-standard infinity values. Solver termination that is
neither an optimum, certified infeasibility, nor certified unboundedness raises
a typed **SolverFailure** rather than silently producing a bound.

## 3. Housing design-audit certificate

The manifest-bound housing certificate constructs the 57-by-7 maintained
public-unit derivative at the neutral design point. It independently checks the
analytic adapter derivative by central differences, then appends the four
registered deliberately adversarial rival signatures. The same calculation is
repeated after the preregistered synthetic diagonal moment scaling.

The command requires the authoritative `FAIL-IDENT-0` report and a clean Git
worktree. It records maintained and augmented singular values, ranks, condition
numbers, focal-span residuals, input hashes, and the interpretation ceiling.
Its only successful decision is `STOP-UNIQUE+GO-PARTIAL-ID-THEORY`; it has no
path that authorizes an empirical England interval.

## 4. Invariants and optimized Python

The library uses explicit **InvariantViolation** checks, not Python assert
statements. It rejects:

- empty, non-finite, or dimensionally inconsistent response arrays;
- non-finite or reversed nuisance boxes;
- malformed names and tolerances; and
- endpoint witnesses that exceed the declared feasibility tolerance.

The test suite launches a separate **python -O** process and verifies that an
invalid matrix still raises **InvariantViolation**. Optimized execution therefore
cannot remove scientific input checks.

## 5. Promotion to an empirical England bound

A numerical interval from this module is not, by itself, an England estimate.
Promotion would require a separately reviewed response-set package containing at
least:

1. exact source identities, versions, licences, hashes, and extraction receipts;
2. a declared mapping from each source estimand to every model moment;
3. source-backed response or elasticity sets for each admitted mechanism;
4. explicit time, geography, population, unit, and scale transport sets;
5. sensitivity to rival-set enlargement and nuisance-box relaxation; and
6. independent reproduction showing that the response set was not tuned to the
   focal design column or observed residual.

Until that package exists, the appropriate report is a design-geometry
certificate or a conditional illustrative interval. No synthetic IDENT-0
loading, adversarial rival, or fitted residual may be relabelled as a
source-backed response set.

## 6. Reproduction

Run the focused suite from the repository root:

    python -m pytest tests/partialid
    python -O -m pytest tests/partialid
    ruff check src/housing_pressure/partialid tests/partialid

The frozen housing-specific certificate is generated with:

    housing-partialid --output-dir results/partialid/<new-run-id>

All public result objects are frozen dataclasses with to_dict() methods that emit
JSON-serializable values and the machine-readable interpretation ceiling.
