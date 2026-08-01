"""Fail-closed retrieval of hash-pinned official public files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

from housing_pressure.ident0.errors import InvariantViolation

from .config import SourceSpec


_CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    source_id: str
    publisher: str
    landing_url: str
    requested_url: str
    final_url: str
    filename: str
    sha256: str
    bytes: int
    media_kind: str
    access_tier: str
    licence: str
    retrieval_mode: str
    retrieved_utc: str
    content_type: str
    etag: str
    last_modified: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    spec: SourceSpec
    path: Path
    receipt: SourceReceipt


def _read_limited(handle: BinaryIO, maximum: int) -> bytes:
    blocks: list[bytes] = []
    total = 0
    while True:
        block = handle.read(_CHUNK)
        if not block:
            break
        total += len(block)
        if total > maximum:
            raise InvariantViolation(f"download exceeded declared maximum of {maximum} bytes")
        blocks.append(block)
    return b"".join(blocks)


def validate_source_payload(spec: SourceSpec, payload: bytes) -> str:
    """Verify size, digest, and coarse media identity independent of retrieval mode."""

    if not payload:
        raise InvariantViolation(f"source {spec.source_id} returned an empty payload")
    if len(payload) > spec.max_bytes:
        raise InvariantViolation(
            f"source {spec.source_id} exceeds declared maximum of {spec.max_bytes} bytes"
        )
    digest = hashlib.sha256(payload).hexdigest()
    if digest != spec.sha256:
        raise InvariantViolation(
            f"source {spec.source_id} hash drift: expected {spec.sha256}, received {digest}"
        )
    if spec.media_kind in {"ods", "xlsx"}:
        if not payload.startswith(b"PK"):
            raise InvariantViolation(f"source {spec.source_id} is not a ZIP-based spreadsheet")
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = set(archive.namelist())
                if spec.media_kind == "ods":
                    if {"mimetype", "content.xml"} - names:
                        raise InvariantViolation(
                            f"source {spec.source_id} is not an ODS spreadsheet"
                        )
                    if archive.read("mimetype") != (
                        b"application/vnd.oasis.opendocument.spreadsheet"
                    ):
                        raise InvariantViolation(
                            f"source {spec.source_id} has the wrong ODS mimetype"
                        )
                elif {"[Content_Types].xml", "xl/workbook.xml"} - names:
                    raise InvariantViolation(f"source {spec.source_id} is not an XLSX workbook")
        except zipfile.BadZipFile as exc:
            raise InvariantViolation(
                f"source {spec.source_id} is not a valid spreadsheet ZIP"
            ) from exc
    if spec.media_kind == "csv" and b"\x00" in payload[:4096]:
        raise InvariantViolation(f"source {spec.source_id} does not look like text CSV")
    return digest


def _write_new(path: Path, payload: bytes) -> None:
    if path.exists():
        raise InvariantViolation(f"refusing to overwrite raw source: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise InvariantViolation(f"refusing to overwrite temporary raw source: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _validate_final_url(spec: SourceSpec, final_url: str) -> None:
    parsed = urlparse(final_url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise InvariantViolation(f"source {spec.source_id} returned an invalid final URL") from exc
    final_host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not final_host
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        raise InvariantViolation(f"source {spec.source_id} final URL is not credential-free HTTPS")
    if final_host not in spec.allowed_hosts:
        raise InvariantViolation(
            f"source {spec.source_id} redirected outside its host allowlist: {final_host}"
        )


def retrieve_source(
    spec: SourceSpec,
    raw_directory: Path,
    *,
    user_agent: str,
    offline_source_directory: Path | None = None,
    timeout_seconds: float = 120.0,
) -> RetrievedSource:
    """Retrieve one source from its official URL or a hash-verified offline cache."""

    destination = raw_directory.resolve() / spec.filename
    now = datetime.now(timezone.utc).isoformat()
    if offline_source_directory is not None:
        origin = offline_source_directory.resolve() / spec.filename
        if not origin.is_file():
            raise InvariantViolation(f"offline source is missing: {origin}")
        if origin.stat().st_size > spec.max_bytes:
            raise InvariantViolation(f"offline source exceeds maximum size: {origin}")
        payload = origin.read_bytes()
        digest = validate_source_payload(spec, payload)
        _write_new(destination, payload)
        receipt = SourceReceipt(
            source_id=spec.source_id,
            publisher=spec.publisher,
            landing_url=spec.landing_url,
            requested_url=spec.download_url,
            final_url=spec.download_url,
            filename=spec.filename,
            sha256=digest,
            bytes=len(payload),
            media_kind=spec.media_kind,
            access_tier=spec.access_tier,
            licence=spec.licence,
            retrieval_mode="offline_hash_verified_copy",
            retrieved_utc=now,
            content_type="offline/local-file",
            etag="",
            last_modified="",
        )
        return RetrievedSource(spec=spec, path=destination, receipt=receipt)

    request = Request(
        spec.download_url,
        headers={"User-Agent": user_agent, "Accept": "*/*"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            _validate_final_url(spec, final_url)
            content_length = response.headers.get("Content-Length", "")
            if content_length:
                try:
                    if int(content_length) > spec.max_bytes:
                        raise InvariantViolation(
                            f"source {spec.source_id} declares an oversized payload"
                        )
                except ValueError as exc:
                    raise InvariantViolation(
                        f"source {spec.source_id} returned invalid Content-Length"
                    ) from exc
            payload = _read_limited(response, spec.max_bytes)
            headers = response.headers
    except InvariantViolation:
        raise
    except OSError as exc:
        raise InvariantViolation(f"cannot retrieve source {spec.source_id}: {exc}") from exc

    digest = validate_source_payload(spec, payload)
    _write_new(destination, payload)
    receipt = SourceReceipt(
        source_id=spec.source_id,
        publisher=spec.publisher,
        landing_url=spec.landing_url,
        requested_url=spec.download_url,
        final_url=final_url,
        filename=spec.filename,
        sha256=digest,
        bytes=len(payload),
        media_kind=spec.media_kind,
        access_tier=spec.access_tier,
        licence=spec.licence,
        retrieval_mode="official_https",
        retrieved_utc=now,
        content_type=headers.get("Content-Type", ""),
        etag=headers.get("ETag", ""),
        last_modified=headers.get("Last-Modified", ""),
    )
    return RetrievedSource(spec=spec, path=destination, receipt=receipt)


__all__ = [
    "RetrievedSource",
    "SourceReceipt",
    "retrieve_source",
    "validate_source_payload",
]
