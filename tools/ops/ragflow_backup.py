#!/usr/bin/env python3
"""Create, verify, restore, and drill encrypted RAGFlow Docker-volume backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

_SCHEMA_VERSION = 1
_SUPPORTED_DOC_ENGINE = "elasticsearch"
_BACKUP_FILES = ("mysql_backup.tar.gz", "minio_backup.tar.gz", "redis_backup.tar.gz", "es_backup.tar.gz")
_VOLUME_SUFFIXES = ("mysql_data", "minio_data", "redis_data", "esdata01")
_BACKUP_NAME = re.compile(r"^ragflow-backup-(\d{8}T\d{6}Z)\.tar\.gz\.age$")
_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DRILL_RUN_LABEL = "io.ragflow.backup.drill-run"


class BackupError(RuntimeError):
    """A user-actionable backup or restore failure."""


def validate_project_name(project: str) -> None:
    if not _PROJECT_NAME.fullmatch(project):
        raise BackupError(
            "Compose project names must start with a lowercase letter or digit and contain only lowercase letters, digits, '-' or '_'"
        )


def require_positive(name: str, value: int) -> None:
    if value < 1:
        raise BackupError(f"{name} must be positive")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_manifest(project: str, doc_engine: str, volume_dir: Path, repo_root: Path, rpo_hours: int, rto_hours: int) -> dict[str, Any]:
    files = []
    for name in _BACKUP_FILES:
        path = volume_dir / name
        if not path.is_file():
            raise BackupError(f"migration backup is missing required file: {name}")
        files.append({"path": f"volumes/{name}", "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=False, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    return {
        "schema_version": _SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project": project,
        "doc_engine": doc_engine,
        "git_commit": git_commit or None,
        "rpo_hours": rpo_hours,
        "rto_hours": rto_hours,
        "restore_tool": "tools/ops/ragflow_backup.py",
        "files": files,
    }


def write_payload_metadata(payload_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_path = payload_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum_lines = [f"{item['sha256']}  {item['path']}" for item in manifest["files"]]
    (payload_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "ragflow-backup":
        raise BackupError(f"unsafe backup archive member: {name}")


def extract_payload(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            validate_member_name(member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise BackupError(f"unsupported backup archive member type: {member.name}")
        bundle.extractall(destination, filter="data")
    payload = destination / "ragflow-backup"
    if not payload.is_dir():
        raise BackupError("backup payload root is missing")
    return payload


def validate_payload(payload_dir: Path) -> dict[str, Any]:
    manifest_path = payload_dir / "manifest.json"
    if not manifest_path.is_file():
        raise BackupError("manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != _SCHEMA_VERSION:
        raise BackupError(f"unsupported backup schema version: {manifest.get('schema_version')}")
    if manifest.get("doc_engine") != _SUPPORTED_DOC_ENGINE:
        raise BackupError(f"unsupported backup document engine: {manifest.get('doc_engine')}")
    expected_paths = {f"volumes/{name}" for name in _BACKUP_FILES}
    entries = manifest.get("files")
    if (
        not isinstance(entries, list)
        or not all(isinstance(item, dict) for item in entries)
        or {item.get("path") for item in entries} != expected_paths
    ):
        raise BackupError("manifest does not contain the complete required volume archive set")
    for item in entries:
        relative = PurePosixPath(item["path"])
        validate_member_name(f"ragflow-backup/{relative.as_posix()}")
        path = payload_dir.joinpath(*relative.parts)
        if not path.is_file():
            raise BackupError(f"payload file is missing: {item['path']}")
        if path.stat().st_size != item.get("bytes"):
            raise BackupError(f"payload size mismatch: {item['path']}")
        if sha256_file(path) != item.get("sha256"):
            raise BackupError(f"payload checksum mismatch: {item['path']}")
    return manifest


def require_runtime(*commands: str) -> None:
    if platform.system() != "Linux":
        raise BackupError("backup and restore are supported only on Linux/WSL2")
    for command in commands:
        if shutil.which(command) is None:
            raise BackupError(f"required command is missing: {command}")


def run_age_encrypt(source: Path, destination: Path, recipient: str) -> None:
    subprocess.run(["age", "--recipient", recipient, "--output", str(destination), str(source)], check=True)


def run_age_decrypt(source: Path, destination: Path, identity: Path) -> None:
    subprocess.run(["age", "--decrypt", "--identity", str(identity), "--output", str(destination), str(source)], check=True)


def encrypt_atomic(source: Path, destination: Path, recipient: str) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(raw_temporary)
    temporary.unlink()
    try:
        run_age_encrypt(source, temporary, recipient)
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_private_atomic(path: Path, content: str) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def checksum_sidecar_path(archive: Path) -> Path:
    return archive.with_name(archive.name + ".sha256")


def verify_outer_checksum(archive: Path) -> None:
    sidecar = checksum_sidecar_path(archive)
    if not sidecar.is_file():
        raise BackupError(f"encrypted archive checksum is missing: {sidecar}")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != archive.name:
        raise BackupError("invalid encrypted archive checksum file")
    if fields[0] != sha256_file(archive):
        raise BackupError("encrypted archive checksum mismatch")


def decrypt_and_validate(archive: Path, identity: Path, work_dir: Path) -> tuple[Path, dict[str, Any]]:
    verify_outer_checksum(archive)
    decrypted = work_dir / "payload.tar.gz"
    run_age_decrypt(archive, decrypted, identity)
    payload = extract_payload(decrypted, work_dir / "extracted")
    return payload, validate_payload(payload)


def migration(repo_root: Path, operation: str, project: str, folder: Path) -> None:
    relative = folder.resolve().relative_to(repo_root.resolve())
    subprocess.run(
        ["bash", "docker/migration.sh", "-p", project, operation, relative.as_posix()],
        cwd=repo_root,
        check=True,
        input="yes\n" if operation == "restore" else None,
        text=True,
        encoding="utf-8",
    )


def compose(repo_root: Path, project: str, *arguments: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-p", project, "-f", "docker/docker-compose.yml", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
    )


def running_compose_services(repo_root: Path, project: str) -> list[str]:
    result = compose(repo_root, project, "ps", "--services", "--status", "running", capture_output=True)
    return [service for line in result.stdout.splitlines() if (service := line.strip())]


def run_with_compose_paused(
    repo_root: Path,
    project: str,
    startup_timeout: int,
    operation: Callable[[], None],
) -> None:
    require_positive("startup timeout", startup_timeout)
    services = running_compose_services(repo_root, project)
    if not services:
        operation()
        return

    operation_error: Exception | None = None
    try:
        compose(repo_root, project, "stop", *services)
        operation()
    except Exception as exc:
        operation_error = exc

    try:
        compose(
            repo_root,
            project,
            "up",
            "-d",
            "--no-deps",
            "--wait",
            "--wait-timeout",
            str(startup_timeout),
            *services,
        )
    except Exception as restart_error:
        if operation_error is not None:
            raise BackupError(
                f"backup/restore operation failed ({operation_error}); additionally failed to restart Compose services ({restart_error})"
            ) from restart_error
        raise

    if operation_error is not None:
        raise operation_error


def create_volume_backup(repo_root: Path, project: str, volume_dir: Path, manage_compose: bool, startup_timeout: int) -> None:
    operation = lambda: migration(repo_root, "backup", project, volume_dir)
    if manage_compose:
        run_with_compose_paused(repo_root, project, startup_timeout, operation)
    else:
        operation()


def prune_backups(output_dir: Path, retention_days: int, now: datetime | None = None) -> list[Path]:
    if retention_days < 1:
        raise BackupError("retention days must be positive")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    deleted: list[Path] = []
    for path in output_dir.iterdir():
        match = _BACKUP_NAME.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if created >= cutoff:
            continue
        path.unlink()
        sidecar = checksum_sidecar_path(path)
        if sidecar.is_file():
            sidecar.unlink()
        deleted.append(path)
    return deleted


def backup(args: argparse.Namespace, repo_root: Path) -> Path:
    validate_project_name(args.project)
    require_positive("retention days", args.retention_days)
    require_positive("RPO hours", args.rpo_hours)
    require_positive("RTO hours", args.rto_hours)
    if args.manage_compose:
        require_positive("startup timeout", args.startup_timeout)
    require_runtime("docker", "bash", "age")
    env = load_env(args.env_file)
    doc_engine = env.get("DOC_ENGINE", _SUPPORTED_DOC_ENGINE)
    if doc_engine != _SUPPORTED_DOC_ENGINE:
        raise BackupError(
            f"enterprise backup currently supports DOC_ENGINE={_SUPPORTED_DOC_ENGINE}; got {doc_engine}. "
            "Do not claim recoverability for an untested storage profile."
        )
    recipient = args.recipient or os.getenv("RAGFLOW_BACKUP_AGE_RECIPIENT")
    if not recipient:
        raise BackupError("set --recipient or RAGFLOW_BACKUP_AGE_RECIPIENT; unencrypted backups are forbidden")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_archive = args.output_dir / f"ragflow-backup-{stamp}.tar.gz.age"
    if final_archive.exists():
        raise BackupError(f"backup already exists: {final_archive}")

    with tempfile.TemporaryDirectory(prefix=".ragflow-backup-", dir=repo_root) as raw_work:
        work = Path(raw_work)
        payload = work / "ragflow-backup"
        volume_dir = payload / "volumes"
        create_volume_backup(repo_root, args.project, volume_dir, args.manage_compose, args.startup_timeout)
        manifest = build_manifest(args.project, doc_engine, volume_dir, repo_root, args.rpo_hours, args.rto_hours)
        write_payload_metadata(payload, manifest)
        plain_archive = work / "payload.tar.gz"
        with tarfile.open(plain_archive, "w:gz") as bundle:
            bundle.add(payload, arcname="ragflow-backup", recursive=True)
        encrypt_atomic(plain_archive, final_archive, recipient)

    digest = sha256_file(final_archive)
    sidecar = checksum_sidecar_path(final_archive)
    write_private_atomic(sidecar, f"{digest}  {final_archive.name}\n")
    prune_backups(args.output_dir, args.retention_days)
    return final_archive


def verify(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    del repo_root
    require_runtime("age")
    with tempfile.TemporaryDirectory(prefix="ragflow-verify-") as raw_work:
        _, manifest = decrypt_and_validate(args.archive, args.identity, Path(raw_work))
        return manifest


def restore(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    require_runtime("docker", "bash", "age")
    if not args.confirm_restore:
        raise BackupError("restore requires --confirm-restore")
    with tempfile.TemporaryDirectory(prefix=".ragflow-restore-", dir=repo_root) as raw_work:
        payload, manifest = decrypt_and_validate(args.archive, args.identity, Path(raw_work))
        target_project = args.target_project or manifest["source_project"]
        validate_project_name(target_project)
        operation = lambda: migration(repo_root, "restore", target_project, payload / "volumes")
        if args.manage_compose:
            run_with_compose_paused(repo_root, target_project, args.startup_timeout, operation)
        else:
            operation()
        return {**manifest, "target_project": target_project}


def drill(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    require_runtime("docker", "bash", "age")
    validate_project_name(args.target_project)
    if not args.target_project.startswith("ragflow-drill-"):
        raise BackupError("drill target project must start with 'ragflow-drill-'")

    volumes = [f"{args.target_project}_{suffix}" for suffix in _VOLUME_SUFFIXES]
    preexisting = [
        volume
        for volume in volumes
        if subprocess.run(
            ["docker", "volume", "inspect", volume],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    ]
    if preexisting:
        raise BackupError(f"refusing to overwrite pre-existing drill volumes: {', '.join(preexisting)}")

    run_id = uuid.uuid4().hex
    owned: list[str] = []
    operation_error: Exception | None = None
    restored: dict[str, Any] | None = None
    try:
        for volume in volumes:
            subprocess.run(
                ["docker", "volume", "create", "--label", f"{_DRILL_RUN_LABEL}={run_id}", volume],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            ownership = subprocess.run(
                ["docker", "volume", "inspect", "--format", f'{{{{ index .Labels "{_DRILL_RUN_LABEL}" }}}}', volume],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if ownership.stdout.strip() != run_id:
                raise BackupError(f"could not establish ownership of drill volume: {volume}")
            owned.append(volume)

        restored = restore(
            argparse.Namespace(
                **{
                    **vars(args),
                    "confirm_restore": True,
                    "manage_compose": False,
                    "startup_timeout": 300,
                }
            ),
            repo_root,
        )
        for volume in owned:
            result = subprocess.run(
                ["docker", "run", "--rm", "-v", f"{volume}:/data:ro", "alpine", "sh", "-c", "find /data -mindepth 1 -print -quit"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if not result.stdout.strip():
                raise BackupError(f"restored drill volume is empty: {volume}")
    except Exception as exc:
        operation_error = exc

    cleanup_error: Exception | None = None
    if owned:
        result = subprocess.run(
            ["docker", "volume", "rm", *owned],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            cleanup_error = BackupError(f"failed to remove owned drill volumes: {', '.join(owned)}")

    if operation_error is not None and cleanup_error is not None:
        raise BackupError(f"drill failed ({operation_error}); cleanup also failed ({cleanup_error})") from cleanup_error
    if cleanup_error is not None:
        raise cleanup_error
    if operation_error is not None:
        raise operation_error
    if restored is None:
        raise BackupError("drill completed without a restore result")
    return restored


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--output-dir", type=Path, required=True)
    backup_parser.add_argument("--project", default="docker")
    backup_parser.add_argument("--env-file", type=Path, default=root / "docker" / ".env")
    backup_parser.add_argument("--recipient")
    backup_parser.add_argument("--retention-days", type=int, default=14)
    backup_parser.add_argument("--rpo-hours", type=int, default=24)
    backup_parser.add_argument("--rto-hours", type=int, default=4)
    backup_parser.add_argument("--manage-compose", action="store_true", help="pause only currently running Compose services for a consistent snapshot, then restore their prior running state")
    backup_parser.add_argument("--startup-timeout", type=int, default=300)

    for name in ("verify", "restore", "drill"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("--archive", type=Path, required=True)
        command_parser.add_argument("--identity", type=Path, required=True)
        if name in {"restore", "drill"}:
            command_parser.add_argument("--target-project", default="" if name == "restore" else f"ragflow-drill-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        if name == "restore":
            command_parser.add_argument("--confirm-restore", action="store_true")
            command_parser.add_argument("--manage-compose", action="store_true", help="pause only currently running target services during restore, then restore their prior running state")
            command_parser.add_argument("--startup-timeout", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "backup":
            result = backup(args, repo_root)
            print(result)
        elif args.command == "verify":
            print(json.dumps(verify(args, repo_root), ensure_ascii=False, indent=2))
        elif args.command == "restore":
            print(json.dumps(restore(args, repo_root), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(drill(args, repo_root), ensure_ascii=False, indent=2))
    except (BackupError, subprocess.CalledProcessError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"backup tool failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
