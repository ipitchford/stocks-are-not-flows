"""Adversarial rival data-generating processes for IDENT-0.

The rivals in this module are synthetic stress tests, not empirical estimates.
Each has zero truth for every fitted seven-block amplitude and generates an
annual response from a named omitted mechanism.  Several are intentionally
close to the model's top-resource column: a successful identification pipeline
must either distinguish them from observed discriminator moments or fail the
unique-attribution gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .errors import InvariantViolation
from .response_model import (
    BLOCK_NAMES,
    DIAGNOSTIC_ROLE,
    MOMENT_NAMES,
    TARGET_ROLE,
    LocalResponseModel,
    ResponsePanel,
)


SOCIAL_COMPARISON = "social_comparison"
INSTITUTIONAL_ENTRY = "institutional_entry"
RENTAL_SEGMENTATION = "rental_segmentation"
PLANNING_RESTRICTION = "planning_restriction"
EXACT_TOP_MIMIC = "exact_top_mimic_known_negative"

RIVAL_NAMES: tuple[str, ...] = (
    SOCIAL_COMPARISON,
    INSTITUTIONAL_ENTRY,
    RENTAL_SEGMENTATION,
    PLANNING_RESTRICTION,
)


def _residual(**values: float) -> NDArray[np.float64]:
    unknown = sorted(set(values) - set(MOMENT_NAMES))
    if unknown:
        raise InvariantViolation("unknown rival response moments: " + ", ".join(unknown))
    result = np.zeros(len(MOMENT_NAMES), dtype=float)
    for moment, value in values.items():
        result[MOMENT_NAMES.index(moment)] = float(value)
    if not np.all(np.isfinite(result)):
        raise InvariantViolation("rival response residuals must be finite")
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class RivalDGP:
    """A named omitted-mechanism response relative to one fitted block.

    ``reference_weight`` deliberately controls how strongly the rival mimics a
    fitted response column.  ``residual`` contains the economically motivated
    discriminator signature.  Referencing a column constructs a difficult
    synthetic DGP; it does not make that fitted block true.
    """

    name: str
    description: str
    reference_block: str
    reference_weight: float
    residual: NDArray[np.float64]
    distinguishing_moments: tuple[str, ...]
    zero_response_moments: tuple[str, ...] = ()
    known_negative: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.description:
            raise InvariantViolation("rival DGPs require a name and description")
        if self.reference_block not in BLOCK_NAMES:
            raise InvariantViolation(
                f"rival {self.name!r} references unknown block {self.reference_block!r}"
            )
        if not np.isfinite(self.reference_weight):
            raise InvariantViolation("rival reference weight must be finite")
        residual = np.asarray(self.residual, dtype=float).copy()
        if residual.shape != (len(MOMENT_NAMES),):
            raise InvariantViolation(
                f"rival residual shape {residual.shape} does not match {(len(MOMENT_NAMES),)}"
            )
        if not np.all(np.isfinite(residual)):
            raise InvariantViolation("rival residual contains non-finite values")
        unknown = sorted(set(self.distinguishing_moments) - set(MOMENT_NAMES))
        if unknown:
            raise InvariantViolation(
                f"rival {self.name!r} has unknown distinguishing moments: {', '.join(unknown)}"
            )
        if len(set(self.distinguishing_moments)) != len(self.distinguishing_moments):
            raise InvariantViolation(f"rival {self.name!r} repeats a distinguishing moment")
        unknown_zero = sorted(set(self.zero_response_moments) - set(MOMENT_NAMES))
        if unknown_zero:
            raise InvariantViolation(
                f"rival {self.name!r} has unknown zero-response moments: " + ", ".join(unknown_zero)
            )
        if len(set(self.zero_response_moments)) != len(self.zero_response_moments):
            raise InvariantViolation(f"rival {self.name!r} repeats a zero-response moment")
        residual.setflags(write=False)
        object.__setattr__(self, "residual", residual)

    def terminal_loadings(self, model: LocalResponseModel) -> NDArray[np.float64]:
        """Return the moment response at unit amplitude and ramp endpoint."""

        column = model.coefficients[:, BLOCK_NAMES.index(self.reference_block)]
        loadings = self.reference_weight * column + self.residual
        if not np.all(np.isfinite(loadings)):
            raise InvariantViolation(f"rival {self.name!r} generated non-finite loadings")
        loadings.setflags(write=False)
        return loadings

    def simulate(
        self,
        model: LocalResponseModel,
        *,
        amplitude: float = 1.0,
        noise_std: float = 0.0,
        seed: int | None = None,
    ) -> RivalSimulation:
        """Generate a rival-only annual panel on the common ramp.

        Noise, when requested, is independent in the modelled annual panel and
        exists only for estimator stress testing.  It is not a likelihood claim
        about the public data.
        """

        if not np.isfinite(amplitude):
            raise InvariantViolation("rival amplitude must be finite")
        if not np.isfinite(noise_std) or noise_std < 0:
            raise InvariantViolation("rival noise_std must be finite and non-negative")
        reference = model.zero_amplitudes()
        reference[self.reference_block] = self.reference_weight * float(amplitude)
        values = model.predict(reference).values.copy()
        values += model.ramp[:, np.newaxis] * (float(amplitude) * self.residual)[np.newaxis, :]
        for moment in self.zero_response_moments:
            values[:, MOMENT_NAMES.index(moment)] = 0.0
        if noise_std > 0:
            generator = np.random.default_rng(seed)
            values = values + generator.normal(0.0, noise_std, size=values.shape)
        panel = ResponsePanel(
            model.years,
            MOMENT_NAMES,
            values,
            source=f"rival:{self.name}",
        )
        return RivalSimulation(
            dgp_name=self.name,
            amplitude=float(amplitude),
            panel=panel,
            base_truth=tuple(0.0 for _ in BLOCK_NAMES),
            known_negative=self.known_negative,
        )


@dataclass(frozen=True, slots=True)
class RivalSimulation:
    """A generated panel whose fitted-model shock truth is explicitly zero."""

    dgp_name: str
    amplitude: float
    panel: ResponsePanel
    base_truth: tuple[float, ...]
    known_negative: bool = False

    def __post_init__(self) -> None:
        if not self.dgp_name:
            raise InvariantViolation("rival simulation must name its DGP")
        if not np.isfinite(self.amplitude):
            raise InvariantViolation("rival simulation amplitude must be finite")
        if len(self.base_truth) != len(BLOCK_NAMES):
            raise InvariantViolation("rival base truth has the wrong number of blocks")
        if any(not np.isfinite(value) for value in self.base_truth):
            raise InvariantViolation("rival base truth contains non-finite values")
        if any(value != 0.0 for value in self.base_truth):
            raise InvariantViolation("a rival-only DGP must have zero truth for all fitted blocks")

    @property
    def true_top_amplitude(self) -> float:
        return self.base_truth[BLOCK_NAMES.index("z_top")]

    def observation_vector(
        self,
        model: LocalResponseModel,
        role: str | None = TARGET_ROLE,
    ) -> NDArray[np.float64]:
        return model.vector_from_panel(self.panel, role)

    def public_core_value(
        self,
        model: LocalResponseModel,
        moment: str,
        year: int,
    ) -> float | None:
        return model.public_core_value(self.panel, moment, year)


@dataclass(frozen=True, slots=True)
class RivalProjection:
    """Least-squares projection of an omitted DGP onto the fitted response model."""

    dgp_name: str
    role: str | None
    fitted_amplitudes: tuple[float, ...]
    residual_rmse: float
    rank: int

    def __post_init__(self) -> None:
        if len(self.fitted_amplitudes) != len(BLOCK_NAMES):
            raise InvariantViolation("rival projection has the wrong amplitude dimension")
        if not np.isfinite(self.residual_rmse) or self.residual_rmse < 0:
            raise InvariantViolation("rival projection RMSE must be finite and non-negative")
        if self.rank < 0 or self.rank > len(BLOCK_NAMES):
            raise InvariantViolation("rival projection rank is outside the admissible range")

    def amplitude(self, block: str) -> float:
        canonical = LocalResponseModel.canonical_block_name(block)
        return self.fitted_amplitudes[BLOCK_NAMES.index(canonical)]


def _catalogue_items() -> tuple[RivalDGP, ...]:
    # Each residual identifies the moments that are supposed to discipline the
    # near-mimic.  In particular, omitted mechanisms do not mechanically change
    # the measured top non-housing-wealth share merely because their housing
    # outcomes resemble the top-resource response.
    return (
        RivalDGP(
            name=SOCIAL_COMPARISON,
            description=(
                "Non-rich housing and mortgage demand responds to richer comparison groups; "
                "housing outcomes mimic pressure without household top-resource investment."
            ),
            reference_block="z_top",
            reference_weight=0.92,
            residual=_residual(
                owner_share_25_44_pp=0.55,
                private_renter_share_25_44_pp=-0.40,
                nhw_top10_share_pp=-1.564,
                owner_mortgage_rate_pp=-0.30,
                turnover_pct=0.75,
            ),
            distinguishing_moments=(
                "nhw_top10_share_pp",
                "owner_mortgage_rate_pp",
                "turnover_pct",
            ),
            zero_response_moments=("nhw_top10_share_pp",),
        ),
        RivalDGP(
            name=INSTITUTIONAL_ENTRY,
            description=(
                "Deep-pocketed institutions expand rental supply and crowd out household "
                "landlords while reproducing aggregate ownership and price-rent signs."
            ),
            reference_block="z_top",
            reference_weight=0.96,
            residual=_residual(
                nhw_top10_share_pp=-1.632,
                private_rent_pct=-0.65,
                net_additions_rate_pp=0.70,
                btl_owner_spread_pp=-0.25,
                prs_dwelling_share_pp=0.55,
            ),
            distinguishing_moments=(
                "nhw_top10_share_pp",
                "net_additions_rate_pp",
                "private_rent_pct",
            ),
            zero_response_moments=("nhw_top10_share_pp",),
        ),
        RivalDGP(
            name=RENTAL_SEGMENTATION,
            description=(
                "Owner and rental markets become more segmented, changing landlord absorption "
                "and credit-price transmission without a top-resource shock."
            ),
            reference_block="z_top",
            reference_weight=0.90,
            residual=_residual(
                nhw_top10_share_pp=-1.530,
                private_rent_pct=0.85,
                net_additions_rate_pp=-0.35,
                owner_mortgage_rate_pp=0.35,
                btl_owner_spread_pp=0.55,
                turnover_pct=-0.80,
            ),
            distinguishing_moments=(
                "nhw_top10_share_pp",
                "btl_owner_spread_pp",
                "turnover_pct",
            ),
            zero_response_moments=("nhw_top10_share_pp",),
        ),
        RivalDGP(
            name=PLANNING_RESTRICTION,
            description=(
                "Primitive permit/land capacity tightens; the negative supply shock is not an "
                "endogenous dwelling-stock change and has zero top-resource truth."
            ),
            reference_block="planning_supply",
            reference_weight=-1.00,
            residual=_residual(
                owner_share_25_44_pp=-0.15,
                log_hpi_pct=0.40,
                turnover_pct=-0.35,
            ),
            distinguishing_moments=(
                "net_additions_rate_pp",
                "log_hpi_pct",
                "turnover_pct",
            ),
        ),
    )


RIVAL_CATALOGUE: Mapping[str, RivalDGP] = MappingProxyType(
    {item.name: item for item in _catalogue_items()}
)


def exact_top_mimic(model: LocalResponseModel) -> RivalDGP:
    """Return the mandatory impossible-identification known-negative DGP.

    Its observed responses are exactly the fitted top-resource column while the
    declared top-resource truth is zero.  No procedure using only this response
    vector can distinguish the labels; a gate that reports unique recovery is
    therefore unsound.
    """

    # ``model`` is accepted so the call site makes the adversarial target
    # explicit.  The DGP references the model column at simulation time.
    if not isinstance(model, LocalResponseModel):
        raise InvariantViolation("exact_top_mimic requires a LocalResponseModel")
    return RivalDGP(
        name=EXACT_TOP_MIMIC,
        description="Exact observational clone of the fitted z_top response with zero z_top truth.",
        reference_block="z_top",
        reference_weight=1.0,
        residual=np.zeros(len(MOMENT_NAMES), dtype=float),
        distinguishing_moments=(),
        known_negative=True,
    )


def get_rival(name: str) -> RivalDGP:
    """Retrieve a registered adversarial DGP by exact name."""

    if name not in RIVAL_CATALOGUE:
        available = ", ".join(RIVAL_CATALOGUE)
        raise InvariantViolation(f"unknown rival DGP {name!r}; available: {available}")
    return RIVAL_CATALOGUE[name]


def simulate_rival(
    model: LocalResponseModel,
    name: str,
    *,
    amplitude: float = 1.0,
    noise_std: float = 0.0,
    seed: int | None = None,
) -> RivalSimulation:
    return get_rival(name).simulate(
        model,
        amplitude=amplitude,
        noise_std=noise_std,
        seed=seed,
    )


def project_rival_onto_model(
    model: LocalResponseModel,
    simulation: RivalSimulation,
    *,
    role: str | None = TARGET_ROLE,
) -> RivalProjection:
    """Quantify how a misspecified fitted model would label a rival-only panel."""

    if role not in (TARGET_ROLE, DIAGNOSTIC_ROLE, None):
        raise InvariantViolation(f"unknown observation role: {role!r}")
    design = model.analytic_jacobian(role)
    observed = simulation.observation_vector(model, role)
    if design.shape[0] != observed.size:
        raise InvariantViolation("rival observation vector and design matrix are misaligned")
    rank = int(np.linalg.matrix_rank(design))
    fitted, _, _, _ = np.linalg.lstsq(design, observed, rcond=None)
    residual = observed - design @ fitted
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    return RivalProjection(
        dgp_name=simulation.dgp_name,
        role=role,
        fitted_amplitudes=tuple(float(value) for value in fitted),
        residual_rmse=rmse,
        rank=rank,
    )


def simulate_all_rivals(
    model: LocalResponseModel,
    *,
    amplitude: float = 1.0,
) -> tuple[RivalSimulation, ...]:
    """Generate all registered rival-only panels in stable preregistered order."""

    return tuple(RIVAL_CATALOGUE[name].simulate(model, amplitude=amplitude) for name in RIVAL_NAMES)


__all__ = [
    "EXACT_TOP_MIMIC",
    "INSTITUTIONAL_ENTRY",
    "PLANNING_RESTRICTION",
    "RENTAL_SEGMENTATION",
    "RIVAL_CATALOGUE",
    "RIVAL_NAMES",
    "SOCIAL_COMPARISON",
    "RivalDGP",
    "RivalProjection",
    "RivalSimulation",
    "exact_top_mimic",
    "get_rival",
    "project_rival_onto_model",
    "simulate_all_rivals",
    "simulate_rival",
]
