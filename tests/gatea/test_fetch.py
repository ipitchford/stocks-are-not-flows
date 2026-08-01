from __future__ import annotations

import hashlib
import io
from pathlib import Path
import zipfile

import pytest

from housing_pressure.gatea.config import SourceSpec
from housing_pressure.gatea.fetch import retrieve_source
from housing_pressure.ident0.errors import InvariantViolation


def _spec(payload: bytes) -> SourceSpec:
    return SourceSpec(
        source_id="TEST_CSV",
        publisher="Test publisher",
        landing_url="https://example.org/landing",
        download_url="https://example.org/data.csv",
        filename="data.csv",
        sha256=hashlib.sha256(payload).hexdigest(),
        allowed_hosts=("example.org",),
        media_kind="csv",
        max_bytes=1024,
        access_tier="open_download",
        licence="test-only",
    )


def test_offline_replay_copies_only_hash_matching_bytes(tmp_path: Path) -> None:
    payload = b"date,value\n2020-01-01,1\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "data.csv").write_bytes(payload)
    raw = tmp_path / "raw"

    result = retrieve_source(
        _spec(payload),
        raw,
        user_agent="test",
        offline_source_directory=cache,
    )

    assert result.path.read_bytes() == payload
    assert result.receipt.retrieval_mode == "offline_hash_verified_copy"
    assert result.receipt.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.receipt.final_url == "https://example.org/data.csv"
    assert tmp_path.as_posix() not in str(result.receipt.to_dict())


def test_offline_hash_drift_and_overwrite_fail_closed(tmp_path: Path) -> None:
    registered = b"date,value\n2020-01-01,1\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "data.csv").write_bytes(b"drifted")
    with pytest.raises(InvariantViolation, match="hash drift"):
        retrieve_source(
            _spec(registered),
            tmp_path / "raw",
            user_agent="test",
            offline_source_directory=cache,
        )

    (cache / "data.csv").write_bytes(registered)
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "data.csv").write_bytes(b"existing")
    with pytest.raises(InvariantViolation, match="refusing to overwrite"):
        retrieve_source(
            _spec(registered),
            raw,
            user_agent="test",
            offline_source_directory=cache,
        )


def test_spreadsheet_media_identity_is_not_just_a_pk_prefix(tmp_path: Path) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", "<document/>")
    payload = output.getvalue()
    spec = SourceSpec(
        source_id="TEST_XLSX",
        publisher="Test",
        landing_url="https://example.org/landing",
        download_url="https://example.org/data.xlsx",
        filename="data.xlsx",
        sha256=hashlib.sha256(payload).hexdigest(),
        allowed_hosts=("example.org",),
        media_kind="xlsx",
        max_bytes=4096,
        access_tier="open_download",
        licence="test",
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "data.xlsx").write_bytes(payload)
    with pytest.raises(InvariantViolation, match="not an XLSX"):
        retrieve_source(
            spec,
            cache / "raw",
            user_agent="test",
            offline_source_directory=cache,
        )


def test_same_host_http_final_url_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"date,value\n2020-01-01,1\n"

    class FakeResponse:
        headers: dict[str, str] = {}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def geturl(self) -> str:
            return "http://example.org/data.csv"

        def read(self, _size: int) -> bytes:
            return payload

    monkeypatch.setattr(
        "housing_pressure.gatea.fetch.urlopen", lambda *args, **kwargs: FakeResponse()
    )
    with pytest.raises(InvariantViolation, match="credential-free HTTPS"):
        retrieve_source(_spec(payload), tmp_path / "raw", user_agent="test")
