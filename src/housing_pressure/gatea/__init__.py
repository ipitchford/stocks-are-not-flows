"""Licence-safe public Gate A accounting pipeline."""

from .config import GateAConfig, SourceSpec, load_config
from .extract import GateAResult, extract_open_accounting

__all__ = [
    "GateAConfig",
    "GateAResult",
    "SourceSpec",
    "extract_open_accounting",
    "load_config",
]
