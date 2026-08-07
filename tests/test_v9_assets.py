"""Hash, hydration, comparison, and extraction tests for V9 assets."""
import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.data.v9_assets import (
    AssetError,
    assert_hydrated,
    compare_trees,
    extract_explanations,
    verify_explanation_archive,
)


def _write_zip(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lfs_pointer_is_not_treated_as_hydrated_data(tmp_path):
    pointer = tmp_path / "payload.zip"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:" + "0" * 64 + "\nsize 10\n"
    )
    with pytest.raises(AssetError, match="git lfs pull"):
        assert_hydrated(pointer)


def test_archive_verification_and_atomic_extraction(tmp_path):
    archive = tmp_path / "result.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/recovery/current.json": b"{}",
            "v9_schema3_results/recovery/bundles/x/manifest.json": b"{}",
        },
    )
    assert verify_explanation_archive(archive, digest) == 3
    destination = tmp_path / "published"
    extract_explanations(archive, destination, digest)
    assert (destination / "result.json").read_bytes() == b"{}"
    assert (destination / "recovery/current.json").is_file()


def test_archive_rejects_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/../../escape.txt": b"bad",
        },
    )
    with pytest.raises(AssetError, match="unsafe ZIP member"):
        verify_explanation_archive(archive, digest)


def test_tree_comparison_reports_missing_and_changed_files(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "same.csv").write_text("same")
    (right / "same.csv").write_text("same")
    (left / "changed.csv").write_text("left")
    (right / "changed.csv").write_text("right")
    (left / "left-only.csv").write_text("left")
    report = compare_trees(left, right)
    assert report == {
        "changed": ["changed.csv"],
        "left_only": ["left-only.csv"],
        "right_only": [],
    }
