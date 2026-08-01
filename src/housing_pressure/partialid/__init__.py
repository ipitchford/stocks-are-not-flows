"""Partial-identification and design-geometry certificates."""

from .errors import InvariantViolation, PartialIdentificationError, SolverFailure
from .design_audit import HousingDesignAudit, MatrixSummary, build_housing_design_audit
from .geometry import (
    AssuranceScope,
    DesignGeometryCertificate,
    DualDiscriminator,
    certify_focal_geometry,
)
from .intervals import (
    EndpointSolution,
    FocalIntervalResult,
    IntervalStatus,
    sharp_focal_interval,
)

__all__ = [
    "AssuranceScope",
    "DesignGeometryCertificate",
    "DualDiscriminator",
    "EndpointSolution",
    "FocalIntervalResult",
    "HousingDesignAudit",
    "IntervalStatus",
    "InvariantViolation",
    "MatrixSummary",
    "PartialIdentificationError",
    "SolverFailure",
    "build_housing_design_audit",
    "certify_focal_geometry",
    "sharp_focal_interval",
]
