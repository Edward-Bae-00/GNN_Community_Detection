"""Behavioral tests for the comment-only Python comparator."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPARATOR = REPOSITORY_ROOT / "scripts" / "data" / "compare_comment_only.py"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    hooks = root / ".git" / "test-hooks"
    hooks.mkdir()
    _git(root, "config", "core.hooksPath", str(hooks))
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Comparator Tests")
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "baseline")
    return root


def _compare(root: Path, *paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMPARATOR), *paths],
        cwd=root,
        capture_output=True,
        text=True,
    )


def test_nested_docstring_only_edits_pass(tmp_path: Path):
    root = _repo(
        tmp_path,
        {
            "sample.py": (
                '"""module"""\n'
                "class Example:\n"
                '    """class"""\n'
                "    def method(self):\n"
                '        """method"""\n'
                "        return 1\n"
                "    async def run(self):\n"
                '        """async method"""\n'
                "        return 2\n"
            )
        },
    )
    path = root / "sample.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace('"""module"""', '"""expanded module"""')
        .replace('"""class"""', '"""expanded class"""')
        .replace('"""method"""', '"""expanded method"""')
        .replace('"""async method"""', '"""expanded async method"""'),
        encoding="utf-8",
    )

    result = _compare(root, "sample.py")

    assert result.returncode == 0, result.stderr + result.stdout


def test_nested_executable_change_fails(tmp_path: Path):
    root = _repo(
        tmp_path,
        {"sample.py": "def outer():\n    def inner():\n        return 1\n    return inner()\n"},
    )
    path = root / "sample.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace("return 1", "return 2"),
        encoding="utf-8",
    )

    result = _compare(root, "sample.py")

    assert result.returncode != 0
    assert "sample.py" in result.stderr


def test_new_python_file_fails_closed(tmp_path: Path):
    root = _repo(tmp_path, {"tracked.py": "VALUE = 1\n"})
    (root / "new.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = _compare(root, ".")

    assert result.returncode != 0
    assert "new.py" in result.stderr
    assert "no HEAD baseline" in result.stderr


def test_tracked_deletion_fails(tmp_path: Path):
    root = _repo(tmp_path, {"tracked.py": "VALUE = 1\n"})
    (root / "tracked.py").unlink()

    result = _compare(root, ".")

    assert result.returncode != 0
    assert "tracked.py" in result.stderr
    assert "missing" in result.stderr


def test_direct_requested_deleted_path_fails_cleanly(tmp_path: Path):
    root = _repo(tmp_path, {"tracked.py": "VALUE = 1\n"})
    (root / "tracked.py").unlink()

    result = _compare(root, "tracked.py")

    assert result.returncode != 0
    assert "does not exist" in result.stderr
    assert "Traceback" not in result.stderr


def test_syntax_error_fails(tmp_path: Path):
    root = _repo(tmp_path, {"tracked.py": "VALUE = 1\n"})
    (root / "tracked.py").write_text("def broken(:\n", encoding="utf-8")

    result = _compare(root, "tracked.py")

    assert result.returncode != 0
    assert "tracked.py" in result.stderr
    assert "syntax could not be parsed" in result.stderr


def test_path_outside_repository_is_rejected(tmp_path: Path):
    root = _repo(tmp_path, {"tracked.py": "VALUE = 1\n"})
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")

    result = _compare(root, str(outside))

    assert result.returncode != 0
    assert "outside the repository" in result.stderr
    assert "Traceback" not in result.stderr


def test_request_without_comparable_tracked_python_files_cannot_pass(tmp_path: Path):
    root = _repo(tmp_path, {"README.md": "documentation\n"})
    notes = root / "notes"
    notes.mkdir()
    (notes / "README.txt").write_text("notes\n", encoding="utf-8")

    result = _compare(root, "notes")

    assert result.returncode != 0
    assert "no Python files" in result.stderr
