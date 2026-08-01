"""Hash-pinned adapters from internal responses to frozen public-core units.

The local response panel stores deviations because it is a design harness, not
an empirical baseline model.  The frozen target schedule, however, contains
tenure levels and a nominal weekly-rent level.  This module is the only place
where those objects are joined.  Synthetic baseline levels are configuration
inputs used for recovery tests; they are not reported as English data.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .diagnostics import Ident0Config
from .errors import InvariantViolation
from .response_model import (
    TARGET_ROLE,
    LocalResponseModel,
    ObservationSpec,
    ResponsePanel,
)


FloatArray = NDArray[np.float64]


ADAPTER_SCALE_KEYS = {
    "owner_share_level": "owner_share_25_44_pp",
    "private_renter_share_level": "private_renter_share_25_44_pp",
    "nominal_rent_level_from_log_pct": "median_nominal_weekly_rent_gbp",
}


@dataclass(frozen=True, slots=True)
class AdaptedObservationVector:
    """Ordered public-unit vector and the metadata that fixes its semantics."""

    labels: tuple[str, ...]
    values: FloatArray
    scale_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=float).copy()
        if values.ndim != 1 or values.size != len(self.labels):
            raise InvariantViolation("adapted values and labels must be one-dimensional and align")
        if len(self.scale_keys) != len(self.labels):
            raise InvariantViolation("adapted scale keys and labels do not align")
        if len(set(self.labels)) != len(self.labels):
            raise InvariantViolation("adapted observation labels must be unique")
        if not np.all(np.isfinite(values)):
            raise InvariantViolation("adapted observation vector contains non-finite values")
        values.setflags(write=False)
        object.__setattr__(self, "values", values)


class PublicCoreObservationAdapter:
    """Apply the frozen unit transformations to a local response panel."""

    def __init__(self, config: Ident0Config) -> None:
        if not isinstance(config, Ident0Config):
            raise InvariantViolation("public-core adapter requires a validated Ident0Config")
        self.config = config
        self.baselines = dict(config.synthetic_baseline_levels)
        owner = self.baselines["owner_share_25_44_pct"]
        renter = self.baselines["private_renter_share_25_44_pct"]
        if owner + renter >= 100.0:
            raise InvariantViolation(
                "synthetic owner and private-renter baselines leave no other tenure share"
            )

    def vector_from_panel(
        self,
        model: LocalResponseModel,
        panel: ResponsePanel,
        role: str | None = TARGET_ROLE,
    ) -> AdaptedObservationVector:
        schedule = model.observation_schedule(role)
        values = np.asarray([self._adapt(panel, item) for item in schedule], dtype=float)
        keys = tuple(self._scale_key(item) for item in schedule)
        return AdaptedObservationVector(
            labels=tuple(item.observation_id for item in schedule),
            values=values,
            scale_keys=keys,
        )

    def vector(
        self,
        model: LocalResponseModel,
        amplitudes: NDArray[np.float64] | tuple[float, ...] | list[float],
        role: str | None = TARGET_ROLE,
    ) -> AdaptedObservationVector:
        return self.vector_from_panel(model, model.predict(amplitudes), role)

    def scales_for(self, adapted: AdaptedObservationVector) -> FloatArray:
        declared = dict(self.config.synthetic_moment_scales)
        missing = sorted(set(adapted.scale_keys) - set(declared))
        if missing:
            raise InvariantViolation(
                "synthetic moment scales are missing adapted keys: " + ", ".join(missing)
            )
        unused = sorted(set(declared) - set(adapted.scale_keys))
        if unused:
            raise InvariantViolation(
                "synthetic moment scales contain unused target keys: " + ", ".join(unused)
            )
        scales = np.asarray([declared[key] for key in adapted.scale_keys], dtype=float)
        if np.any(~np.isfinite(scales)) or np.any(scales <= 0.0):
            raise InvariantViolation("adapted target scales must be finite and positive")
        scales.setflags(write=False)
        return scales

    def _adapt(self, panel: ResponsePanel, item: ObservationSpec) -> float:
        response = panel.value(item.moment, item.anchor_year)
        if item.adapter == "identity_deviation":
            return response
        if item.adapter == "owner_share_level":
            value = self.baselines["owner_share_25_44_pct"] + response
            self._validate_share(item.observation_id, value)
            return value
        if item.adapter == "private_renter_share_level":
            value = self.baselines["private_renter_share_25_44_pct"] + response
            self._validate_share(item.observation_id, value)
            return value
        if item.adapter == "nominal_rent_level_from_log_pct":
            baseline = self.baselines["median_nominal_weekly_rent_gbp"]
            value = baseline * math.exp(response / 100.0)
            if not math.isfinite(value) or value <= 0.0:
                raise InvariantViolation(
                    f"adapted nominal rent is invalid at {item.observation_id}"
                )
            return value
        raise InvariantViolation(f"observation {item.observation_id!r} has no implemented adapter")

    @staticmethod
    def _scale_key(item: ObservationSpec) -> str:
        return ADAPTER_SCALE_KEYS.get(item.adapter, item.moment)

    @staticmethod
    def _validate_share(observation_id: str, value: float) -> None:
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise InvariantViolation(
                f"adapted tenure share is outside [0, 100] at {observation_id}"
            )


__all__ = [
    "ADAPTER_SCALE_KEYS",
    "AdaptedObservationVector",
    "PublicCoreObservationAdapter",
]
