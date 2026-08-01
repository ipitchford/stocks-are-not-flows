import json

import numpy as np
import pytest

from housing_pressure.partialid import (
    AssuranceScope,
    IntervalStatus,
    InvariantViolation,
    sharp_focal_interval,
)


def test_box_bounded_nuisance_gives_attained_sharp_interval() -> None:
    result = sharp_focal_interval(
        response=(2.0,),
        focal_column=(1.0,),
        nuisance_columns=((1.0,),),
        nuisance_bounds=((-0.5, 0.5),),
        focal_name="top_resource",
        nuisance_names=("credit",),
    )

    assert result.status is IntervalStatus.BOUNDED
    assert result.assurance_scope is AssuranceScope.CONDITIONAL_RESPONSE_SET_ONLY
    assert result.lower == pytest.approx(1.5)
    assert result.upper == pytest.approx(2.5)
    assert result.width == pytest.approx(1.0)
    assert result.lower_solution is not None
    assert result.upper_solution is not None
    assert result.lower_solution.nuisance_coefficients == pytest.approx((0.5,))
    assert result.upper_solution.nuisance_coefficients == pytest.approx((-0.5,))
    assert not result.empirical_england_bound
    json.dumps(result.to_dict(), allow_nan=False)


def test_empty_conditional_response_set_is_explicitly_infeasible() -> None:
    result = sharp_focal_interval(
        response=(2.0,),
        focal_column=(0.0,),
        nuisance_columns=((1.0,),),
        nuisance_bounds=((0.0, 1.0),),
    )

    assert result.status is IntervalStatus.INFEASIBLE
    assert not result.feasible
    assert result.lower is None
    assert result.upper is None
    assert result.lower_solution is None
    assert result.upper_solution is None
    assert "empty response set" in result.interpretation


def test_unbounded_focal_axis_uses_null_endpoints_not_json_infinity() -> None:
    result = sharp_focal_interval(
        response=(0.0,),
        focal_column=(0.0,),
        nuisance_columns=np.empty((1, 0)),
        nuisance_bounds=(),
        nuisance_names=(),
    )

    assert result.status is IntervalStatus.UNBOUNDED
    assert result.lower is None
    assert result.upper is None
    json.dumps(result.to_dict(), allow_nan=False)


def test_invalid_box_raises_typed_invariant_violation() -> None:
    with pytest.raises(InvariantViolation, match="lower exceeds upper"):
        sharp_focal_interval(
            response=(1.0,),
            focal_column=(1.0,),
            nuisance_columns=((1.0,),),
            nuisance_bounds=((2.0, 1.0),),
        )


@pytest.mark.parametrize("bad_bound", [(False, 1.0), (float("nan"), 1.0), "01"])
def test_malformed_boxes_raise_typed_invariant_violation(bad_bound: object) -> None:
    with pytest.raises(InvariantViolation):
        sharp_focal_interval(
            response=(1.0,),
            focal_column=(1.0,),
            nuisance_columns=((1.0,),),
            nuisance_bounds=(bad_bound,),
        )


def test_scalar_name_metadata_raises_typed_invariant_violation() -> None:
    with pytest.raises(InvariantViolation, match="sequence of names"):
        sharp_focal_interval(
            response=(1.0,),
            focal_column=(1.0,),
            nuisance_columns=((1.0,),),
            nuisance_bounds=((0.0, 1.0),),
            nuisance_names=1,
        )
