"""Cheap production self-check retained under optimized Python."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .design import build_full_preregistered_plan, validate_neutral_maps_to_zero
from .diagnostics import load_config
from .gate_runner import bounds_from_config
from .observation_adapter import PublicCoreObservationAdapter
from .response_model import LocalResponseModel


def main() -> int:
    repository = Path(__file__).resolve().parents[3]
    config = load_config(repository / "configs" / "ident0.json")
    bounds = bounds_from_config(config)
    validate_neutral_maps_to_zero(bounds)
    model = LocalResponseModel.baseline()
    model.verify_measurement_bridge()
    adapted = PublicCoreObservationAdapter(config).vector(
        model, np.zeros(bounds.dimension, dtype=float)
    )
    plan = build_full_preregistered_plan(model.zero_amplitudes().keys(), seed=config.seed)
    if len(adapted.labels) != 57:
        raise RuntimeError(f"expected 57 adapted targets, got {len(adapted.labels)}")
    if plan.truth_cases != 313 or plan.total_fits != 6573:
        raise RuntimeError("full IDENT-0 design arithmetic drifted")
    print(
        json.dumps(
            {
                "adapted_targets": len(adapted.labels),
                "full_fits": plan.total_fits,
                "truth_cases": plan.truth_cases,
                "wealth_bridge": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
