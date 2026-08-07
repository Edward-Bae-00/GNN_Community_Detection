"""Hash, hydration, comparison, and extraction tests for V9 assets."""
import hashlib
import os
import re
import stat
import zipfile
from pathlib import Path

import pytest

from scripts.data import v9_assets
from scripts.data.v9_assets import (
    AssetError,
    assert_hydrated,
    compare_trees,
    extract_explanations,
    main,
    verify_explanation_archive,
)


def _write_zip(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_zip_entries(path: Path, entries) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for member, payload in entries:
            archive.writestr(member, payload)
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


def test_extraction_stays_bound_to_verified_handle_after_path_replacement(
    tmp_path, monkeypatch
):
    archive = tmp_path / "result.zip"
    replacement = tmp_path / "replacement.zip"
    original_digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"original",
            "v9_schema3_results/recovery/current.json": b"{}",
        },
    )
    _write_zip(
        replacement,
        {
            "v9_schema3_results/result.json": b"replacement",
            "v9_schema3_results/recovery/current.json": b"{}",
        },
    )
    original_sha256_file = v9_assets.sha256_file
    original_stream_hash = getattr(v9_assets, "_stream_hash", None)

    def replace_after_hash(hash_target):
        digest = (
            original_sha256_file(hash_target)
            if isinstance(hash_target, Path)
            else original_stream_hash(hash_target)
        )
        os.replace(replacement, archive)
        return digest

    monkeypatch.setattr(v9_assets, "sha256_file", replace_after_hash)
    monkeypatch.setattr(v9_assets, "_stream_hash", replace_after_hash, raising=False)

    destination = tmp_path / "published"
    try:
        extract_explanations(archive, destination, original_digest)
    except AssetError:
        pass

    if destination.exists():
        assert (destination / "result.json").read_bytes() == b"original"
    else:
        assert not list(tmp_path.glob(".v9-extract-*"))


def test_extraction_rejects_fstat_mutation_and_cleans_stage(tmp_path, monkeypatch):
    archive = tmp_path / "result.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/recovery/current.json": b"{}",
        },
    )
    original_stat = archive.stat()
    original_sha256_file = v9_assets.sha256_file
    original_stream_hash = getattr(v9_assets, "_stream_hash", None)

    def mutate_after_hash(hash_target):
        digest = (
            original_sha256_file(hash_target)
            if isinstance(hash_target, Path)
            else original_stream_hash(hash_target)
        )
        os.utime(
            archive,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1),
        )
        return digest

    monkeypatch.setattr(v9_assets, "sha256_file", mutate_after_hash)
    monkeypatch.setattr(v9_assets, "_stream_hash", mutate_after_hash, raising=False)

    destination = tmp_path / "published"
    with pytest.raises(AssetError, match="changed while being processed"):
        extract_explanations(archive, destination, digest)

    assert not destination.exists()
    assert not list(tmp_path.glob(".v9-extract-*"))


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


def test_required_members_must_be_regular_files(tmp_path):
    archive = tmp_path / "directories.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json/", b""),
            ("v9_schema3_results/recovery/current.json/", b""),
        ],
    )

    with pytest.raises(AssetError, match="regular file"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_duplicate_raw_member_names(tmp_path):
    archive = tmp_path / "duplicate.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/result.json", b"duplicate"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(AssetError, match="duplicate ZIP member"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_normalized_member_collisions(tmp_path):
    archive = tmp_path / "normalized-collision.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/./result.json", b"duplicate"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(AssetError, match="normalized ZIP member collision"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_casefolded_member_collisions(tmp_path):
    archive = tmp_path / "casefolded-collision.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/Result.json", b"duplicate"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(AssetError, match="filesystem ZIP member collision"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_unicode_normalized_member_collisions(tmp_path):
    archive = tmp_path / "unicode-collision.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
            ("v9_schema3_results/recovery/caf\u00e9.json", b"one"),
            ("v9_schema3_results/recovery/cafe\u0301.json", b"two"),
        ],
    )

    with pytest.raises(AssetError, match="filesystem ZIP member collision"):
        verify_explanation_archive(archive, digest)


def test_required_members_use_exact_archive_names(tmp_path):
    archive = tmp_path / "dotted-required-name.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/./result.json", b"{}"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(AssetError, match="missing.*result.json"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_file_directory_prefix_collisions(tmp_path):
    archive = tmp_path / "prefix-collision.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/recovery", b"file"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(AssetError, match="file/directory prefix collision"):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_casefolded_file_directory_prefix_collisions(tmp_path):
    archive = tmp_path / "casefolded-prefix-collision.zip"
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/Recovery", b"file"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
        ],
    )

    with pytest.raises(
        AssetError, match="filesystem file/directory prefix collision"
    ):
        verify_explanation_archive(archive, digest)


def test_archive_rejects_non_regular_special_member(tmp_path):
    archive = tmp_path / "special.zip"
    special = zipfile.ZipInfo("v9_schema3_results/recovery/socket")
    special.external_attr = (stat.S_IFSOCK | 0o644) << 16
    digest = _write_zip_entries(
        archive,
        [
            ("v9_schema3_results/result.json", b"{}"),
            ("v9_schema3_results/recovery/current.json", b"{}"),
            (special, b"special"),
        ],
    )

    with pytest.raises(AssetError, match="special ZIP member type"):
        verify_explanation_archive(archive, digest)


def test_malformed_archive_with_matching_digest_is_normalized(tmp_path):
    archive = tmp_path / "malformed.zip"
    archive.write_bytes(b"not a ZIP archive")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()

    with pytest.raises(AssetError, match="ZIP.*corrupt|malformed") as raised:
        verify_explanation_archive(archive, digest)

    assert "BadZipFile" not in str(raised.value)


def test_main_normalizes_asset_error_to_one_stderr_line(tmp_path, capsys):
    result = main(["verify-explanations", "--archive", str(tmp_path / "missing.zip")])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert len(captured.err.splitlines()) == 1


def test_injected_extraction_error_cleans_stage_and_destination(tmp_path, monkeypatch):
    archive = tmp_path / "corrupt-during-extract.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/recovery/current.json": b"{}",
        },
    )

    def fail_extractall(self, path):
        raise zipfile.BadZipFile("injected extraction corruption")

    monkeypatch.setattr(zipfile.ZipFile, "extractall", fail_extractall)
    destination = tmp_path / "published"

    with pytest.raises(AssetError, match="ZIP.*corrupt|extraction"):
        extract_explanations(archive, destination, digest)

    assert not destination.exists()
    assert not list(tmp_path.glob(".v9-extract-*"))


@pytest.mark.parametrize("failure", ["malformed", "hash-mismatch"])
def test_extraction_verifies_before_creating_destination_parent(tmp_path, failure):
    archive = tmp_path / f"{failure}.zip"
    if failure == "malformed":
        archive.write_bytes(b"not a ZIP archive")
        expected_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    else:
        _write_zip(
            archive,
            {
                "v9_schema3_results/result.json": b"{}",
                "v9_schema3_results/recovery/current.json": b"{}",
            },
        )
        expected_digest = "0" * 64

    destination_parent = tmp_path / "absent" / "nested"
    destination = destination_parent / "published"

    with pytest.raises(AssetError):
        extract_explanations(archive, destination, expected_digest)

    assert not destination.exists()
    assert not destination_parent.exists()
    assert not list(tmp_path.rglob(".v9-extract-*"))


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


def test_main_compare_difference_returns_two(tmp_path, capsys):
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    (right / "data.csv").write_text("different")

    result = main(["compare-corpora", str(left), str(right)])

    assert result == 2
    assert capsys.readouterr().err == ""


def _populated_tree(path: Path) -> Path:
    path.mkdir()
    (path / "data.csv").write_text("data")
    return path


@pytest.mark.parametrize("invalid_side", ["left", "right"])
def test_tree_comparison_rejects_missing_root(tmp_path, invalid_side):
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    invalid = tmp_path / "missing"
    if invalid_side == "left":
        left = invalid
    else:
        right = invalid

    with pytest.raises(AssetError, match=re.escape(str(invalid))):
        compare_trees(left, right)


@pytest.mark.parametrize("invalid_side", ["left", "right"])
def test_tree_comparison_rejects_regular_file_root(tmp_path, invalid_side):
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    invalid = tmp_path / "not-a-directory"
    invalid.write_text("data")
    if invalid_side == "left":
        left = invalid
    else:
        right = invalid

    with pytest.raises(AssetError, match=re.escape(str(invalid))):
        compare_trees(left, right)


@pytest.mark.parametrize("cache_name", [None, "__pycache__", ".pytest_cache"])
def test_tree_comparison_rejects_empty_or_excluded_only_root(tmp_path, cache_name):
    left = tmp_path / "left"
    right = _populated_tree(tmp_path / "right")
    left.mkdir()
    if cache_name is not None:
        cache = left / cache_name
        cache.mkdir()
        (cache / "ignored.pyc").write_bytes(b"ignored")

    with pytest.raises(AssetError, match=re.escape(str(left))):
        compare_trees(left, right)


def _symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool):
    if not hasattr(os, "symlink"):
        pytest.skip("the platform does not support symlinks")
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"the platform cannot create symlinks: {error}")


def test_tree_comparison_rejects_symlink_root(tmp_path):
    target = _populated_tree(tmp_path / "target")
    link = tmp_path / "root-link"
    _symlink_or_skip(link, target, target_is_directory=True)
    right = _populated_tree(tmp_path / "right")

    with pytest.raises(AssetError, match=re.escape(str(link))):
        compare_trees(link, right)


def test_tree_comparison_rejects_symlink_file_descendant(tmp_path):
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    outside = tmp_path / "outside.csv"
    outside.write_text("outside")
    link = left / "linked.csv"
    _symlink_or_skip(link, outside, target_is_directory=False)

    with pytest.raises(AssetError, match=re.escape(str(link))):
        compare_trees(left, right)


def test_tree_comparison_rejects_symlink_directory_descendant(tmp_path):
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    outside = _populated_tree(tmp_path / "outside")
    link = left / "linked-directory"
    _symlink_or_skip(link, outside, target_is_directory=True)

    with pytest.raises(AssetError, match=re.escape(str(link))):
        compare_trees(left, right)


def test_tree_comparison_rejects_non_regular_special_entry(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("the platform does not support FIFOs")
    left = _populated_tree(tmp_path / "left")
    right = _populated_tree(tmp_path / "right")
    fifo = left / "events.fifo"
    try:
        os.mkfifo(fifo)
    except OSError as error:
        pytest.skip(f"the platform cannot create FIFOs: {error}")

    with pytest.raises(AssetError, match=re.escape(str(fifo))):
        compare_trees(left, right)
