#!/usr/bin/env python3
"""Reject unapproved deletion of tracked automated tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("test/") or name.endswith("_test.go") or name.startswith("test_") and name.endswith(".py")


def parse_deleted_paths(raw: bytes) -> list[str]:
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    deleted: list[str] = []
    for index in range(0, len(fields) - 1, 2):
        status, path = fields[index], fields[index + 1]
        if status == "D" and is_test_path(path):
            deleted.append(path.replace("\\", "/"))
    return deleted


def load_allowlist(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        file_path, separator, reason = line.partition("|")
        if not separator or not file_path.strip() or not reason.strip():
            raise ValueError(f"{path}:{line_number}: expected 'path | reason'")
        entries[file_path.strip().replace("\\", "/")] = reason.strip()
    return entries


def deleted_test_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "-z", "--diff-filter=D", f"{base}...{head}"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return parse_deleted_paths(result.stdout)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base Git revision")
    parser.add_argument("--head", default="HEAD", help="head Git revision")
    parser.add_argument("--allowlist", type=Path, help="optional reviewed deletion list using 'path | reason'")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    allowlist = load_allowlist(args.allowlist)
    deleted = deleted_test_paths(args.base, args.head)
    unapproved = [path for path in deleted if path not in allowlist]
    stale = [path for path in allowlist if path not in deleted]

    if stale:
        print("Stale test-deletion allowlist entries must be removed:", file=sys.stderr)
        for path in stale:
            print(f"  - {path}", file=sys.stderr)
        return 1
    if unapproved:
        print("Tracked tests were deleted without an explicit reviewed reason:", file=sys.stderr)
        for path in unapproved:
            print(f"  - {path}", file=sys.stderr)
        print("Restore/replace the tests, or add a narrowly reviewed 'path | reason' entry.", file=sys.stderr)
        return 1

    if deleted:
        print(f"Approved test deletions: {len(deleted)}")
        for path in deleted:
            print(f"  - {path}: {allowlist[path]}")
    else:
        print("No tracked automated tests were deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
