from dataclasses import replace

import numpy as np
import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.incidence import ClosureClass
from housing_pressure.ident0.measurement_bridge import (
    LocalWealthBridgeConfig,
    LocalWealthMeasurementBridge,
)


def test_bridge_matches_registered_terminal_tangent_and_accumulates_the_ramp() -> None:
    bridge = LocalWealthMeasurementBridge()
    sensitivity = bridge.local_sensitivity_path()

    assert sensitivity.shape == (12, 2)
    np.testing.assert_allclose(sensitivity[0], (0.0, 0.0), atol=1e-14)
    np.testing.assert_allclose(sensitivity[-1], (1.70, -0.35), atol=1e-12)
    # A wealth stock accumulates prior flows, so its path is not the
    # contemporaneous common ramp used by the other local responses.
    normalized_top = sensitivity[:, 0] / sensitivity[-1, 0]
    assert not np.allclose(normalized_top, bridge.ramp)
    np.testing.assert_allclose(normalized_top, bridge.cumulative_ramp / bridge.cumulative_ramp[-1])


def test_d1_and_d2_directions_execute_incidence_and_stock_flow_ledgers() -> None:
    bridge = LocalWealthMeasurementBridge()
    d1 = bridge.audit_direction(ClosureClass.D1_RESOURCE_INJECTION, amplitude=0.1)
    d2 = bridge.audit_direction(ClosureClass.D2_RESOURCE_LOSS, amplitude=-0.1)

    assert len(d1.observations) == len(bridge.config.years)
    assert d1.observations[-1].closing_top_share > bridge.opening_top_share
    assert d2.observations[-1].closing_top_share > bridge.opening_top_share
    # A negative middle-resource amplitude raises the measured top share; the
    # derivative with respect to a positive middle flow is therefore negative.
    assert bridge.sensitivity(2019)[1] < 0.0
    bridge.verify()

    d1r = bridge.audit_direction(ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL, amplitude=-0.1)
    d2r = bridge.audit_direction(ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION, amplitude=0.1)
    assert d1r.observations[-1].closing_top_share < bridge.opening_top_share
    assert d2r.observations[-1].closing_top_share < bridge.opening_top_share


def test_bridge_rejects_wrong_direction_and_rank_semantics() -> None:
    bridge = LocalWealthMeasurementBridge()
    with pytest.raises(InvariantViolation, match="positive top"):
        bridge.audit_direction(ClosureClass.D1_RESOURCE_INJECTION, amplitude=-0.1)
    with pytest.raises(InvariantViolation, match="negative middle"):
        bridge.audit_direction(ClosureClass.D2_RESOURCE_LOSS, amplitude=0.1)
    with pytest.raises(InvariantViolation, match="load more heavily"):
        LocalWealthMeasurementBridge(
            replace(
                LocalWealthBridgeConfig(),
                top_type_top_rank_weight=0.05,
                middle_type_top_rank_weight=0.95,
            )
        )
