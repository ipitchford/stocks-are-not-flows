from pathlib import Path

import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.manifest import build_manifest, sha256_file, write_manifest


def _init_repository(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_sha256_file_known_value(tmp_path: Path) -> None:
    item = tmp_path / "x.txt"
    item.write_text("abc", encoding="utf-8")
    assert sha256_file(item) == ("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_build_and_write_manifest(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}\n", encoding="utf-8")

    manifest = build_manifest(
        tmp_path,
        [config],
        seed=7,
        command=["housing-ident0", "--smoke"],
    )
    target = tmp_path / "results" / "manifest.json"
    write_manifest(manifest, target)

    text = target.read_text(encoding="utf-8")
    assert "config.json" in text
    assert '"seed": 7' in text
    assert '"git_worktree_clean": false' in text
    with pytest.raises(InvariantViolation, match="already exists"):
        write_manifest(manifest, target)


def test_manifest_rejects_outside_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repository(repo)
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(InvariantViolation, match="outside repository"):
        build_manifest(repo, [outside], seed=1, command=[])


def test_manifest_can_require_a_clean_committed_worktree(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    untracked = tmp_path / "untracked.txt"
    untracked.write_text("x", encoding="utf-8")

    with pytest.raises(InvariantViolation, match="clean Git worktree"):
        build_manifest(
            tmp_path,
            [untracked],
            seed=1,
            command=[],
            require_clean=True,
        )
