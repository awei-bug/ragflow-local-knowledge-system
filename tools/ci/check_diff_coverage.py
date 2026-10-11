#!/usr/bin/env python3
"""Enforce coverage for executable Python lines added by a Git diff."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_DEFAULT_PREFIXES = ("agent/", "api/", "common/", "deepdoc/", "memory/", "rag/")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def is_in_scope(path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = normalize_path(path)
    return normalized.endswith(".py") and not normalized.startswith("test/") and normalized.startswith(prefixes)


def collect_changed_lines(diff_text: str, prefixes: tuple[str, ...] = _DEFAULT_PREFIXES) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = defaultdict(set)
    current_file: str | None = None
    new_line = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:]
            current_file = None if target == "/dev/null" else normalize_path(target.removeprefix("b/"))
            continue
        match = _HUNK.match(line)
        if match:
            new_line = int(match.group(1))
            continue
        if current_file is None or not is_in_scope(current_file, prefixes):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed[current_file].add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        elif not line.startswith("\\"):
            new_line += 1
    return dict(changed)


def load_coverage(path: Path) -> dict[str, tuple[set[int], set[int]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, dict):
        raise ValueError("coverage JSON has no files object")
    result: dict[str, tuple[set[int], set[int]]] = {}
    for file_path, details in files.items():
        executed = {int(line) for line in details.get("executed_lines", [])}
        missing = {int(line) for line in details.get("missing_lines", [])}
        result[normalize_path(file_path)] = (executed, missing)
    return result


def git_diff(base: str, head: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", f"{base}...{head}", "--", "*.py"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def evaluate(
    changed: dict[str, set[int]], coverage: dict[str, tuple[set[int], set[int]]]
) -> tuple[int, int, dict[str, list[int]], list[str]]:
    covered_count = 0
    statement_count = 0
    missing_by_file: dict[str, list[int]] = {}
    unmeasured_files: list[str] = []
    for file_path, line_numbers in sorted(changed.items()):
        measurement = coverage.get(file_path)
        if measurement is None:
            unmeasured_files.append(file_path)
            continue
        executed, missing = measurement
        statements = line_numbers & (executed | missing)
        missing_changed = sorted(statements & missing)
        covered_count += len(statements & executed)
        statement_count += len(statements)
        if missing_changed:
            missing_by_file[file_path] = missing_changed
    return covered_count, statement_count, missing_by_file, unmeasured_files


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", type=Path, default=Path("coverage.json"))
    parser.add_argument("--base", help="base Git revision; required unless --diff-file is used")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--diff-file", type=Path, help="read a unified diff from a file")
    parser.add_argument("--minimum", type=float, default=80.0)
    parser.add_argument("--include-prefix", action="append", dest="prefixes")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.minimum <= 100:
        raise ValueError("--minimum must be between 0 and 100")
    if args.diff_file:
        diff_text = args.diff_file.read_text(encoding="utf-8")
    elif args.base:
        diff_text = git_diff(args.base, args.head)
    else:
        raise ValueError("--base is required unless --diff-file is used")

    prefixes = tuple(normalize_path(prefix).rstrip("/") + "/" for prefix in (args.prefixes or _DEFAULT_PREFIXES))
    changed = collect_changed_lines(diff_text, prefixes)
    coverage = load_coverage(args.coverage_json)
    covered, statements, missing_by_file, unmeasured = evaluate(changed, coverage)

    if unmeasured:
        print("Changed in-scope Python files were absent from coverage data:", file=sys.stderr)
        for file_path in unmeasured:
            print(f"  - {file_path}", file=sys.stderr)
        return 1
    if statements == 0:
        print("No changed executable Python lines require diff coverage.")
        return 0

    percentage = covered * 100 / statements
    print(f"Diff coverage: {percentage:.2f}% ({covered}/{statements}); required: {args.minimum:.2f}%")
    for file_path, lines in missing_by_file.items():
        print(f"  missing {file_path}: {','.join(map(str, lines))}")
    return 0 if percentage >= args.minimum else 1


if __name__ == "__main__":
    raise SystemExit(main())
