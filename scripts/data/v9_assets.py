#!/usr/bin/env python3
"""Verify, compare, and safely extract canonical V9 repository assets."""
from __future__ import annotations

import argparse
from bisect import bisect_left
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

from gnn.paths import V9_EXPLANATION_ARCHIVE


EXPLANATION_SHA256 = (
    "54064788c0cd92893296d1db926aaa902604e30db16fdc3151545413a30008fd"
)
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
ARCHIVE_PREFIX = "v9_schema3_results"
_EXCLUDED_TREE_PARTS = {"__pycache__", ".pytest_cache"}


class AssetError(RuntimeError):
    """Raised when a versioned V9 asset is absent, unsafe, or corrupted."""


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_hydrated(path: Path) -> Path:
    """Require a real file rather than a missing or unhydrated LFS pointer."""
    path = Path(path)
    if not path.is_file():
        raise AssetError(f"asset is missing: {path}; run git lfs pull")
    with path.open("rb") as handle:
        if handle.read(len(LFS_HEADER)) == LFS_HEADER:
            raise AssetError(f"asset is an LFS pointer: {path}; run git lfs pull")
    return path


def _stream_hash(handle) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _archive_metadata(handle, path: Path) -> tuple[int, int, int, int, int]:
    try:
        metadata = os.fstat(handle.fileno())
    except OSError as error:
        raise AssetError(f"cannot inspect explanation ZIP: {path}: {error}") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise AssetError(f"asset is missing: {path}; run git lfs pull")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@contextmanager
def _verified_explanation_archive(path: Path, expected_sha256: str):
    path = Path(path)
    try:
        handle = path.open("rb")
    except FileNotFoundError as error:
        raise AssetError(f"asset is missing: {path}; run git lfs pull") from error
    except OSError as error:
        raise AssetError(f"cannot open explanation ZIP: {path}: {error}") from error

    with handle:
        initial_metadata = _archive_metadata(handle, path)
        if handle.read(len(LFS_HEADER)) == LFS_HEADER:
            raise AssetError(f"asset is an LFS pointer: {path}; run git lfs pull")
        handle.seek(0)
        actual = _stream_hash(handle)
        if actual != expected_sha256:
            raise AssetError(
                f"explanation ZIP SHA-256 mismatch: expected {expected_sha256}, got {actual}"
            )
        handle.seek(0)
        try:
            with zipfile.ZipFile(handle) as archive:
                members = _safe_members(archive)
                yield archive, len(members)
        except AssetError:
            raise
        except Exception as error:
            raise AssetError(
                f"explanation ZIP is corrupt or extraction failed: {error}"
            ) from error
        if _archive_metadata(handle, path) != initial_metadata:
            raise AssetError(f"explanation ZIP changed while being processed: {path}")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members:
        raise AssetError("explanation ZIP is empty")

    raw_kinds: dict[str, str] = {}
    normalized_kinds: dict[str, str] = {}
    filesystem_kinds: dict[str, str] = {}
    for member in members:
        name = member.filename
        if name in raw_kinds:
            raise AssetError(f"duplicate ZIP member: {name!r}")

        relative = PurePosixPath(name)
        if not relative.parts:
            raise AssetError(f"unsafe ZIP member: {name!r}")
        mode = (member.external_attr >> 16) & 0o170000
        if (
            not name
            or "\\" in name
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != ARCHIVE_PREFIX
        ):
            raise AssetError(f"unsafe ZIP member: {name!r}")

        is_directory = name.endswith("/")
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise AssetError(f"special ZIP member type: {name!r}")
        if is_directory:
            if mode == stat.S_IFREG:
                raise AssetError(f"unsafe ZIP member type: {name!r}")
            kind = "directory"
        else:
            if mode == stat.S_IFDIR:
                raise AssetError(f"directory ZIP member must end with '/': {name!r}")
            kind = "file"

        normalized = relative.as_posix()
        if normalized in normalized_kinds:
            raise AssetError(f"normalized ZIP member collision: {name!r}")

        filesystem_key = unicodedata.normalize("NFC", normalized).casefold()
        if filesystem_key in filesystem_kinds:
            raise AssetError(f"filesystem ZIP member collision: {name!r}")

        raw_kinds[name] = kind
        normalized_kinds[normalized] = kind
        filesystem_kinds[filesystem_key] = kind

    for label, kinds in (
        ("", normalized_kinds),
        ("filesystem ", filesystem_kinds),
    ):
        names = sorted(kinds)
        for name, kind in kinds.items():
            if kind != "file":
                continue
            descendant_index = bisect_left(names, name + "/")
            if (
                descendant_index < len(names)
                and names[descendant_index].startswith(name + "/")
            ):
                raise AssetError(
                    f"{label}file/directory prefix collision: {name!r}"
                )

    required = (
        f"{ARCHIVE_PREFIX}/result.json",
        f"{ARCHIVE_PREFIX}/recovery/current.json",
    )
    missing = sorted(
        name
        for name in required
        if name not in raw_kinds and normalized_kinds.get(name) != "directory"
    )
    if missing:
        raise AssetError(f"explanation ZIP is missing: {', '.join(missing)}")
    non_files = [
        name for name in required if normalized_kinds.get(name) == "directory"
    ]
    if non_files:
        raise AssetError(
            f"explanation ZIP requires regular file: {', '.join(non_files)}"
        )
    return members


def verify_explanation_archive(
    path: Path = V9_EXPLANATION_ARCHIVE,
    expected_sha256: str = EXPLANATION_SHA256,
) -> int:
    """Verify hydration, digest, safe member paths, and required evidence files."""
    with _verified_explanation_archive(path, expected_sha256) as (_, member_count):
        return member_count


def extract_explanations(
    archive_path: Path,
    destination: Path,
    expected_sha256: str = EXPLANATION_SHA256,
) -> Path:
    """Verify and atomically publish the archive's single canonical root."""
    archive_path = Path(archive_path)
    destination = Path(destination)
    if destination.exists():
        raise AssetError(f"extraction destination already exists: {destination}")
    stage: Path | None = None
    try:
        with _verified_explanation_archive(archive_path, expected_sha256) as (archive, _):
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(
                tempfile.mkdtemp(prefix=".v9-extract-", dir=destination.parent)
            )
            archive.extractall(stage)
            source = stage / ARCHIVE_PREFIX
            if not source.is_dir():
                raise AssetError("explanation ZIP canonical root is missing")
        os.replace(source, destination)
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
    return destination


def _file_map(root: Path) -> dict[str, Path]:
    root = Path(root)
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError as error:
        raise AssetError(f"comparison root is missing: {root}") from error
    except OSError as error:
        raise AssetError(f"cannot inspect comparison root {root}: {error}") from error
    if stat.S_ISLNK(root_mode):
        raise AssetError(f"comparison root must not be a symlink: {root}")
    if not stat.S_ISDIR(root_mode):
        raise AssetError(f"comparison root is not a directory: {root}")

    files: dict[str, Path] = {}

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as scanner:
                entries = sorted(scanner, key=lambda entry: entry.name)
        except OSError as error:
            raise AssetError(
                f"cannot traverse comparison path {directory}: {error}"
            ) from error
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root)
            if _EXCLUDED_TREE_PARTS.intersection(relative.parts):
                continue
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as error:
                raise AssetError(f"cannot inspect comparison path {path}: {error}") from error
            if stat.S_ISLNK(mode):
                raise AssetError(f"comparison path must not be a symlink: {path}")
            if stat.S_ISDIR(mode):
                visit(path)
            elif stat.S_ISREG(mode):
                files[relative.as_posix()] = path
            else:
                raise AssetError(
                    f"comparison path is not a regular file or directory: {path}"
                )

    visit(root)
    if not files:
        raise AssetError(f"comparison root contains no eligible regular files: {root}")
    return files


def compare_trees(left: Path, right: Path) -> dict[str, list[str]]:
    """Compare two trees by relative file set and SHA-256 content."""
    left_files, right_files = _file_map(left), _file_map(right)
    common = sorted(left_files.keys() & right_files.keys())
    return {
        "changed": [
            name
            for name in common
            if sha256_file(left_files[name]) != sha256_file(right_files[name])
        ],
        "left_only": sorted(left_files.keys() - right_files.keys()),
        "right_only": sorted(right_files.keys() - left_files.keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-explanations")
    verify.add_argument("--archive", type=Path, default=V9_EXPLANATION_ARCHIVE)
    extract = subparsers.add_parser("extract-explanations")
    extract.add_argument("destination", type=Path)
    extract.add_argument("--archive", type=Path, default=V9_EXPLANATION_ARCHIVE)
    compare = subparsers.add_parser("compare-corpora")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-explanations":
            print(json.dumps({"members": verify_explanation_archive(args.archive)}))
            return 0
        if args.command == "extract-explanations":
            print(extract_explanations(args.archive, args.destination))
            return 0
        report = compare_trees(args.left, args.right)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if not any(report.values()) else 2
    except AssetError as error:
        message = " ".join(str(error).splitlines())
        print(f"error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
