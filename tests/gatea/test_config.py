from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from housing_pressure.gatea.config import GateAConfig, load_config
from housing_pressure.ident0.errors import InvariantViolation


REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG = REPOSITORY / "configs" / "gatea_public.json"


def _raw_config() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_registered_config_is_strict_and_complete() -> None:
    config = load_config(CONFIG)
    assert len(config.sources) == 7
    assert config.core_start_year == 2008
    assert config.core_end_year == 2019
    assert not any(source.max_bytes < 1_000_000 for source in config.sources)
    assert all(source.download_url.startswith("https://") for source in config.sources)


def test_unknown_root_key_fails_closed() -> None:
    raw = _raw_config()
    raw["unregistered_switch"] = True
    with pytest.raises(InvariantViolation, match="keys differ"):
        GateAConfig.from_mapping(raw)


def test_download_host_must_be_allowlisted() -> None:
    raw = copy.deepcopy(_raw_config())
    raw["sources"][0]["allowed_hosts"] = ["example.invalid"]
    with pytest.raises(InvariantViolation, match="outside its allowlist"):
        GateAConfig.from_mapping(raw)


def test_source_hash_and_host_types_are_not_coerced() -> None:
    raw = copy.deepcopy(_raw_config())
    raw["sources"][0]["allowed_hosts"] = [123]
    with pytest.raises(InvariantViolation, match="JSON strings"):
        GateAConfig.from_mapping(raw)

    raw = copy.deepcopy(_raw_config())
    raw["sources"][0]["sha256"] = "not-a-digest"
    with pytest.raises(InvariantViolation, match="invalid SHA-256"):
        GateAConfig.from_mapping(raw)


def test_core_window_and_provenance_seed_are_fixed() -> None:
    raw = copy.deepcopy(_raw_config())
    raw["core_end_year"] = 2020
    with pytest.raises(InvariantViolation, match="registered 2008-2019"):
        GateAConfig.from_mapping(raw)

    raw = copy.deepcopy(_raw_config())
    raw["seed"] = 1
    with pytest.raises(InvariantViolation, match="registered 20260801"):
        GateAConfig.from_mapping(raw)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    (
        (("sources", 0, "source_id"), None, "source_id"),
        (("sources", 0, "publisher"), 123, "publisher"),
        (("sources", 0, "licence"), False, "licence"),
        (("schema_version",), False, "schema_version"),
        (("user_agent",), 123, "user_agent"),
        (
            ("blocked_outputs", "AF03_FINE_TENURE"),
            {"reason": "blocked"},
            "JSON strings",
        ),
    ),
)
def test_semantic_strings_are_not_coerced(
    path: tuple[object, ...], value: object, message: str
) -> None:
    raw = copy.deepcopy(_raw_config())
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InvariantViolation, match=message):
        GateAConfig.from_mapping(raw)


def test_registered_source_ids_and_order_are_exact() -> None:
    raw = copy.deepcopy(_raw_config())
    raw["sources"][0]["source_id"] = "RENAMED_SOURCE"
    with pytest.raises(InvariantViolation, match="IDs/order"):
        GateAConfig.from_mapping(raw)


def test_versions_and_block_map_are_exact() -> None:
    raw = copy.deepcopy(_raw_config())
    raw["schema_version"] = "0.2"
    with pytest.raises(InvariantViolation, match="registered version 0.1"):
        GateAConfig.from_mapping(raw)

    raw = copy.deepcopy(_raw_config())
    del raw["blocked_outputs"]["AF13_FCA_MLAR"]
    with pytest.raises(InvariantViolation, match="registered block map"):
        GateAConfig.from_mapping(raw)
