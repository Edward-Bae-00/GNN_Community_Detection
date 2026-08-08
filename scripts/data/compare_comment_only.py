#!/usr/bin/env python3
"""Compare tracked Python syntax while ignoring recursively nested docstrings."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import sys


def _is_docstring(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


class _DocstringStripper(ast.NodeTransformer):
    """Remove only body-leading string expressions from every AST scope."""

    @staticmethod
    def _without_docstring(body):
        return body[1:] if body and _is_docstring(body[0]) else body

    def _visit_scope(self, node):
        node = self.generic_visit(node)
        node.body = self._without_docstring(node.body)
        return node

    def visit_Module(self, node):
        return self._visit_scope(node)

    def visit_ClassDef(self, node):
        return self._visit_scope(node)

    def visit_FunctionDef(self, node):
        return self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node):
        return self._visit_scope(node)


def _syntax_dump(source: str, path: str) -> str:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise ValueError(f"{path}: Python syntax could not be parsed: {exc}") from exc
    stripped = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(stripped)
    return ast.dump(stripped, annotate_fields=True, include_attributes=False)


def _run_git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.PIPE
    )


def _relative_path(root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path is outside the repository: {value}") from exc


def _working_python_paths(root: Path, requested: Path) -> set[Path]:
    absolute = root / requested
    if absolute.is_dir():
        return {
            path.relative_to(root)
            for path in absolute.rglob("*.py")
            if path.is_file()
        }
    if absolute.is_file() and absolute.suffix == ".py":
        return {requested}
    if absolute.exists():
        raise ValueError(f"requested path is not a Python file or directory: {requested}")
    raise ValueError(f"requested path does not exist: {requested}")


def _head_python_paths(root: Path, requested: Path) -> set[Path]:
    output = _run_git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", requested.as_posix())
    return {
        Path(line.strip())
        for line in output.splitlines()
        if line.strip().endswith(".py")
    }


def _head_source(root: Path, relative: Path) -> str:
    return _run_git(root, "show", f"HEAD:{relative.as_posix()}")


def compare(paths: list[str]) -> int:
    """Compare executable ASTs for the requested paths and return a process code."""
    root = Path(_run_git(Path.cwd(), "rev-parse", "--show-toplevel").strip()).resolve()
    requested = [_relative_path(root, value) for value in paths]
    working = set().union(*(_working_python_paths(root, path) for path in requested))
    head = set().union(*(_head_python_paths(root, path) for path in requested))
    if not working and not head:
        raise ValueError("no Python files found in requested paths")

    failures = 0
    for relative in sorted(working | head):
        current = root / relative
        if relative not in head:
            print(f"{relative}: skipped new/nontracked file (no HEAD baseline)")
            continue
        if relative not in working:
            print(f"{relative}: tracked HEAD file is missing from the working copy")
            failures += 1
            continue
        try:
            head_dump = _syntax_dump(_head_source(root, relative), f"HEAD:{relative}")
            work_dump = _syntax_dump(current.read_text(encoding="utf-8"), str(relative))
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            failures += 1
            continue
        if head_dump != work_dump:
            print(
                f"{relative}: executable syntax differs after docstring stripping",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"comparison failed for {failures} file(s)", file=sys.stderr)
        return 1
    print(f"comparison passed for {len(working & head)} tracked Python file(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse one or more repository paths and compare their HEAD syntax."""
    parser = argparse.ArgumentParser(
        description="Compare Python ASTs while ignoring recursive docstrings."
    )
    parser.add_argument("paths", nargs="+", help="Python files or directories to compare")
    args = parser.parse_args(argv)
    try:
        return compare(args.paths)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
