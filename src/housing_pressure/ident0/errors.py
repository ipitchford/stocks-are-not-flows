"""Typed failures used by scientific gates."""


class Ident0Error(RuntimeError):
    """Base class for IDENT-0 failures."""


class InvariantViolation(Ident0Error):
    """Raised when units, closure, accounting, or measurement is inconsistent."""


class GateFailure(Ident0Error):
    """Raised when a preregistered identification criterion fails."""
