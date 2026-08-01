"""Hash-pinned run manifests for IDENT-0."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Iterable

from .errors import InvariantViolation


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of an existing regular file."""

    resolved = path.resolve()
    if not resolved.is_file():
        raise InvariantViolation(f"manifest input is not a regular file: {resolved}")
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _git_commit(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "uncommitted-repository"
    return result.stdout.strip()


def _git_status(repository: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise InvariantViolation(f"cannot inspect Git worktree: {result.stderr.strip()}")
    return result.stdout


@dataclass(frozen=True)
class ManifestFile:
    path: str
    sha256: str


@dataclass(frozen=True)
class RunManifest:
    schema_version: str
    created_utc: str
    git_commit: str
    git_worktree_clean: bool
    git_status_sha256: str
    python: str
    platform: str
    numpy: str
    scipy: str
    seed: int
    command: tuple[str, ...]
    inputs: tuple[ManifestFile, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_manifest(
    repository: Path,
    inputs: Iterable[Path],
    *,
    seed: int,
    command: Iterable[str],
    require_clean: bool = False,
) -> RunManifest:
    """Build a deterministic-content manifest with a timestamped receipt."""

    repo = repository.resolve()
    if not (repo / ".git").is_dir():
        raise InvariantViolation(f"not a Git repository: {repo}")
    if seed < 0:
        raise InvariantViolation("seed must be non-negative")
    status = _git_status(repo)
    commit = _git_commit(repo)
    if require_clean and status:
        preview = "; ".join(status.splitlines()[:5])
        raise InvariantViolation(
            "manifest-bound scientific run requires a clean Git worktree: " + preview
        )
    if require_clean and commit == "uncommitted-repository":
        raise InvariantViolation("manifest-bound scientific run requires a Git commit")

    files: list[ManifestFile] = []
    for item in sorted((Path(p).resolve() for p in inputs), key=str):
        try:
            relative = item.relative_to(repo)
        except ValueError as exc:
            raise InvariantViolation(f"manifest input is outside repository: {item}") from exc
        files.append(ManifestFile(path=relative.as_posix(), sha256=sha256_file(item)))

    return RunManifest(
        schema_version="0.1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        git_commit=commit,
        git_worktree_clean=not bool(status),
        git_status_sha256=hashlib.sha256(status.encode("utf-8")).hexdigest(),
        python=platform.python_version(),
        platform=platform.platform(),
        numpy=_package_version("numpy"),
        scipy=_package_version("scipy"),
        seed=seed,
        command=tuple(command),
        inputs=tuple(files),
    )


def write_manifest(manifest: RunManifest, destination: Path) -> None:
    """Write a manifest atomically and refuse to overwrite an existing receipt."""

    target = destination.resolve()
    if target.exists():
        raise InvariantViolation(f"manifest already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
