"""Typed failures for partial-identification calculations."""


class PartialIdentificationError(RuntimeError):
    """Base class for partial-identification failures."""


class InvariantViolation(PartialIdentificationError):
    """Raised when an input violates a declared mathematical invariant."""


class SolverFailure(PartialIdentificationError):
    """Raised when the numerical solver cannot certify a scientific outcome."""
