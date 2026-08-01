from pathlib import Path

import numpy as np
import pytest

from housing_pressure.ident0.diagnostics import load_config
from housing_pressure.ident0.observation_adapter import PublicCoreObservationAdapter
from housing_pressure.ident0.response_model import BLOCK_NAMES, LocalResponseModel


CONFIG_PATH = Path(__file__).parents[2] / "configs" / "ident0.json"


def _amplitudes(**updates: float) -> dict[str, float]:
    values = {name: 0.0 for name in BLOCK_NAMES}
    values.update(updates)
    return values


def test_adapter_preserves_frozen_level_units_and_ordered_scales() -> None:
    config = load_config(CONFIG_PATH)
    model = LocalResponseModel.baseline()
    adapter = PublicCoreObservationAdapter(config)
    zero = adapter.vector(model, list(_amplitudes().values()))
    labels = dict(zip(zero.labels, zero.values))

    assert labels["T01_O_BASE"] == pytest.approx(65.0)
    assert labels["T02_O_END"] == pytest.approx(65.0)
    assert labels["T03_PRS_BASE"] == pytest.approx(15.0)
    assert labels["T04_PRS_END"] == pytest.approx(15.0)
    assert labels["T07_RENT_END"] == pytest.approx(200.0)
    scales = adapter.scales_for(zero)
    assert scales.shape == zero.values.shape
    assert np.all(scales > 0.0)


def test_rent_adapter_is_positive_and_uses_the_log_percent_transform() -> None:
    config = load_config(CONFIG_PATH)
    model = LocalResponseModel.baseline()
    adapter = PublicCoreObservationAdapter(config)
    top = adapter.vector(model, list(_amplitudes(z_top=1.0).values()))
    values = dict(zip(top.labels, top.values))
    internal = model.predict(_amplitudes(z_top=1.0)).value("private_rent_pct", 2018)

    assert values["T07_RENT_END"] == pytest.approx(200.0 * np.exp(internal / 100.0))
    assert values["T07_RENT_END"] > 0.0
