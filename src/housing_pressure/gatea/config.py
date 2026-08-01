"""Strict configuration for the licence-safe public-data accounting run."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, Sequence
from urllib.parse import urlparse

from housing_pressure.ident0.errors import InvariantViolation


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_KINDS = frozenset({"csv", "ods", "xlsx"})
_ACCESS_TIERS = frozenset({"open_download", "open_publication", "open_statistical_series"})
_EXPECTED_SOURCE_IDS = (
    "EHS_FA1201_OPEN",
    "HMLR_UKHPI_INDICES_2026_05",
    "ONS_IPHRP_HIST_V25",
    "ONS_PIPR_2026_07_22",
    "MHCLG_DWELLING_STOCK_LT104_2026_05",
    "MHCLG_NET_SUPPLY_LT120_2025_11",
    "BOE_QUOTED_RATES_2008_2019",
)
_EXPECTED_BLOCKED_OUTPUT_IDS = frozenset(
    {
        "AF01_AF02_DESIGN_COVARIANCE",
        "AF03_FINE_TENURE",
        "AF04_AF06_NHW",
        "AF10_PPD_TURNOVER",
        "AF13_FCA_MLAR",
        "AF14_EPLS",
        "GROSS_TENURE_FLOWS",
    }
)


def _sequence(value: object, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvariantViolation(f"{label} must be a JSON array")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvariantViolation(f"{label} must be a positive JSON integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvariantViolation(f"{label} must be a non-empty JSON string")
    return value


def _https_url(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvariantViolation(f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise InvariantViolation(f"{label} must use HTTPS and include a host")
    if parsed.username or parsed.password:
        raise InvariantViolation(f"{label} must not contain credentials")
    return value


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One immutable official download and its reuse boundary."""

    source_id: str
    publisher: str
    landing_url: str
    download_url: str
    filename: str
    sha256: str
    allowed_hosts: tuple[str, ...]
    media_kind: str
    max_bytes: int
    access_tier: str
    licence: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "SourceSpec":
        required = {
            "source_id",
            "publisher",
            "landing_url",
            "download_url",
            "filename",
            "sha256",
            "allowed_hosts",
            "media_kind",
            "max_bytes",
            "access_tier",
            "licence",
        }
        missing = sorted(required - set(raw))
        unknown = sorted(set(raw) - required)
        if missing or unknown:
            raise InvariantViolation(
                f"source specification keys differ; missing={missing}, unknown={unknown}"
            )
        allowed_hosts_raw = _sequence(raw["allowed_hosts"], "allowed_hosts")
        if any(not isinstance(item, str) for item in allowed_hosts_raw):
            raise InvariantViolation("allowed_hosts entries must be JSON strings")
        allowed_hosts = tuple(item.lower() for item in allowed_hosts_raw)
        spec = cls(
            source_id=_string(raw["source_id"], "source_id"),
            publisher=_string(raw["publisher"], "publisher"),
            landing_url=_https_url(raw["landing_url"], "landing_url"),
            download_url=_https_url(raw["download_url"], "download_url"),
            filename=_string(raw["filename"], "filename"),
            sha256=_string(raw["sha256"], "sha256"),
            allowed_hosts=allowed_hosts,
            media_kind=_string(raw["media_kind"], "media_kind"),
            max_bytes=_positive_int(raw["max_bytes"], "max_bytes"),
            access_tier=_string(raw["access_tier"], "access_tier"),
            licence=_string(raw["licence"], "licence"),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if not self.source_id or not self.publisher or not self.licence:
            raise InvariantViolation("source ID, publisher, and licence must be non-empty")
        if not _SHA256.fullmatch(self.sha256):
            raise InvariantViolation(f"source {self.source_id} has an invalid SHA-256")
        if self.media_kind not in _MEDIA_KINDS:
            raise InvariantViolation(f"source {self.source_id} has unknown media kind")
        if self.access_tier not in _ACCESS_TIERS:
            raise InvariantViolation(f"source {self.source_id} is not an authorized open tier")
        if not self.allowed_hosts or any(not host or "/" in host for host in self.allowed_hosts):
            raise InvariantViolation(f"source {self.source_id} has invalid allowed hosts")
        download_host = (urlparse(self.download_url).hostname or "").lower()
        if download_host not in self.allowed_hosts:
            raise InvariantViolation(
                f"source {self.source_id} download host is outside its allowlist"
            )
        if Path(self.filename).name != self.filename or self.filename in {".", ".."}:
            raise InvariantViolation(f"source {self.source_id} has an unsafe filename")
        expected_suffix = {"csv": ".csv", "ods": ".ods", "xlsx": ".xlsx"}[self.media_kind]
        if Path(self.filename).suffix.lower() != expected_suffix:
            raise InvariantViolation(
                f"source {self.source_id} filename does not match {self.media_kind}"
            )


@dataclass(frozen=True, slots=True)
class GateAConfig:
    """Validated public-accounting contract."""

    schema_version: str
    protocol_version: str
    seed: int
    core_start_year: int
    core_end_year: int
    user_agent: str
    sources: tuple[SourceSpec, ...]
    blocked_outputs: Mapping[str, str]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "GateAConfig":
        required = {
            "schema_version",
            "protocol_version",
            "seed",
            "core_start_year",
            "core_end_year",
            "user_agent",
            "sources",
            "blocked_outputs",
        }
        missing = sorted(required - set(raw))
        unknown = sorted(set(raw) - required)
        if missing or unknown:
            raise InvariantViolation(
                f"Gate A config keys differ; missing={missing}, unknown={unknown}"
            )
        source_values = _sequence(raw["sources"], "sources")
        sources_list: list[SourceSpec] = []
        for item in source_values:
            if not isinstance(item, Mapping):
                raise InvariantViolation("every sources entry must be a JSON object")
            sources_list.append(SourceSpec.from_mapping(item))
        sources = tuple(sources_list)
        blocked_raw = raw["blocked_outputs"]
        if not isinstance(blocked_raw, Mapping):
            raise InvariantViolation("blocked_outputs must be a JSON object")
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in blocked_raw.items()
        ):
            raise InvariantViolation("blocked_outputs keys and reasons must be JSON strings")
        blocked = dict(blocked_raw)
        config = cls(
            schema_version=_string(raw["schema_version"], "schema_version"),
            protocol_version=_string(raw["protocol_version"], "protocol_version"),
            seed=_positive_int(raw["seed"], "seed"),
            core_start_year=_positive_int(raw["core_start_year"], "core_start_year"),
            core_end_year=_positive_int(raw["core_end_year"], "core_end_year"),
            user_agent=_string(raw["user_agent"], "user_agent"),
            sources=sources,
            blocked_outputs=MappingProxyType(blocked),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.schema_version != "0.1":
            raise InvariantViolation("Gate A schema_version must equal registered version 0.1")
        if self.protocol_version != "public-pilot-0.1+amendments-01-03":
            raise InvariantViolation("Gate A protocol_version differs from amendments 01-03")
        if (self.core_start_year, self.core_end_year) != (2008, 2019):
            raise InvariantViolation("Gate A core period must be the registered 2008-2019 window")
        if self.seed != 20260801:
            raise InvariantViolation("Gate A provenance seed must equal the registered 20260801")
        ids = [source.source_id for source in self.sources]
        filenames = [source.filename for source in self.sources]
        if tuple(ids) != _EXPECTED_SOURCE_IDS:
            raise InvariantViolation(
                "Gate A source IDs/order differ from the registered public subset"
            )
        if len(filenames) != len(set(filenames)):
            raise InvariantViolation("Gate A source filenames must be unique")
        if not self.blocked_outputs or any(
            not key or not value for key, value in self.blocked_outputs.items()
        ):
            raise InvariantViolation("blocked_outputs must contain non-empty reasons")
        if set(self.blocked_outputs) != _EXPECTED_BLOCKED_OUTPUT_IDS:
            raise InvariantViolation("blocked_outputs keys differ from the registered block map")

    def source(self, source_id: str) -> SourceSpec:
        try:
            return next(item for item in self.sources if item.source_id == source_id)
        except StopIteration as exc:
            raise InvariantViolation(f"Gate A config has no source {source_id!r}") from exc


def load_config(path: str | Path) -> GateAConfig:
    """Load a strict Gate A JSON configuration."""

    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise InvariantViolation(f"cannot read Gate A config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InvariantViolation(f"invalid Gate A JSON {config_path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise InvariantViolation("Gate A config root must be a JSON object")
    return GateAConfig.from_mapping(raw)


__all__ = ["GateAConfig", "SourceSpec", "load_config"]
