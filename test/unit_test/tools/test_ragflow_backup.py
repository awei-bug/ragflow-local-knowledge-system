#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import importlib.util
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOL_PATH = _REPO_ROOT / "tools" / "ops" / "ragflow_backup.py"


def _load_tool():
    module_name = "enterprise_ragflow_backup"
    spec = importlib.util.spec_from_file_location(module_name, _TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _payload(tool, root: Path) -> Path:
    payload = root / "ragflow-backup"
    volumes = payload / "volumes"
    volumes.mkdir(parents=True)
    for index, name in enumerate(tool._BACKUP_FILES, 1):
        (volumes / name).write_bytes(f"volume-{index}".encode())
    manifest = tool.build_manifest("docker", "elasticsearch", volumes, _REPO_ROOT, 24, 4)
    tool.write_payload_metadata(payload, manifest)
    return payload


@pytest.mark.p1
def test_backup_payload_manifest_round_trip(tmp_path: Path):
    tool = _load_tool()
    payload = _payload(tool, tmp_path)

    manifest = tool.validate_payload(payload)

    assert manifest["source_project"] == "docker"
    assert manifest["doc_engine"] == "elasticsearch"
    assert manifest["rpo_hours"] == 24
    assert len(manifest["files"]) == 4


@pytest.mark.p1
def test_backup_payload_detects_archive_corruption(tmp_path: Path):
    tool = _load_tool()
    payload = _payload(tool, tmp_path)
    (payload / "volumes" / tool._BACKUP_FILES[0]).write_bytes(b"corrupt")

    with pytest.raises(tool.BackupError, match="mismatch"):
        tool.validate_payload(payload)


@pytest.mark.p1
def test_backup_extraction_rejects_path_traversal(tmp_path: Path):
    tool = _load_tool()
    source = tmp_path / "value.txt"
    source.write_text("secret", encoding="utf-8")
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="ragflow-backup/../../escaped.txt")

    with pytest.raises(tool.BackupError, match="unsafe"):
        tool.extract_payload(archive, tmp_path / "extract")


@pytest.mark.p1
def test_outer_checksum_detects_encrypted_archive_corruption(tmp_path: Path):
    tool = _load_tool()
    archive = tmp_path / "ragflow-backup-20260904T010203Z.tar.gz.age"
    archive.write_bytes(b"encrypted")
    tool.checksum_sidecar_path(archive).write_text(f"{tool.sha256_file(archive)}  {archive.name}\n", encoding="utf-8")
    tool.verify_outer_checksum(archive)

    archive.write_bytes(b"tampered")
    with pytest.raises(tool.BackupError, match="checksum mismatch"):
        tool.verify_outer_checksum(archive)


@pytest.mark.p1
def test_retention_only_deletes_owned_expired_backup_names(tmp_path: Path):
    tool = _load_tool()
    old = tmp_path / "ragflow-backup-20260801T000000Z.tar.gz.age"
    recent = tmp_path / "ragflow-backup-20260903T000000Z.tar.gz.age"
    unrelated = tmp_path / "customer-data.tar.gz.age"
    for path in (old, recent, unrelated):
        path.write_text("data", encoding="utf-8")
        tool.checksum_sidecar_path(path).write_text("checksum", encoding="utf-8")

    deleted = tool.prune_backups(tmp_path, retention_days=14, now=datetime(2026, 9, 4, tzinfo=timezone.utc))

    assert deleted == [old]
    assert not old.exists()
    assert not tool.checksum_sidecar_path(old).exists()
    assert recent.exists()
    assert unrelated.exists()
    assert tool.checksum_sidecar_path(unrelated).exists()


@pytest.mark.p1
def test_unsupported_doc_engine_is_rejected(tmp_path: Path):
    tool = _load_tool()
    payload = _payload(tool, tmp_path)
    manifest_path = payload / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["doc_engine"] = "infinity"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(tool.BackupError, match="unsupported backup document engine"):
        tool.validate_payload(payload)


@pytest.mark.p1
def test_restore_migration_confirms_existing_volume_overwrite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = _load_tool()
    volume_dir = tmp_path / "volumes"
    volume_dir.mkdir()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return tool.subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    tool.migration(tmp_path, "restore", "docker", volume_dir)

    command, kwargs = calls[0]
    assert command == ["bash", "docker/migration.sh", "-p", "docker", "restore", "volumes"]
    assert kwargs["input"] == "yes\n"
    assert kwargs["check"] is True


@pytest.mark.p1
def test_compose_pause_restores_only_previously_running_services(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = _load_tool()
    calls = []

    monkeypatch.setattr(tool, "running_compose_services", lambda *_: ["mysql", "redis"])

    def fake_compose(_repo_root, _project, *arguments, **_kwargs):
        calls.append(arguments)
        return tool.subprocess.CompletedProcess(arguments, 0, stdout="")

    monkeypatch.setattr(tool, "compose", fake_compose)

    tool.run_with_compose_paused(tmp_path, "docker", 120, lambda: calls.append(("operation",)))

    assert calls == [
        ("stop", "mysql", "redis"),
        ("operation",),
        ("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "mysql", "redis"),
    ]


@pytest.mark.p1
def test_compose_pause_restarts_services_after_operation_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = _load_tool()
    calls = []

    monkeypatch.setattr(tool, "running_compose_services", lambda *_: ["mysql"])

    def fake_compose(_repo_root, _project, *arguments, **_kwargs):
        calls.append(arguments)
        return tool.subprocess.CompletedProcess(arguments, 0, stdout="")

    def fail_operation():
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr(tool, "compose", fake_compose)

    with pytest.raises(RuntimeError, match="snapshot failed"):
        tool.run_with_compose_paused(tmp_path, "docker", 90, fail_operation)

    assert calls == [
        ("stop", "mysql"),
        ("up", "-d", "--no-deps", "--wait", "--wait-timeout", "90", "mysql"),
    ]


@pytest.mark.p1
def test_drill_removes_owned_volumes_after_restore_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = _load_tool()
    project = "ragflow-drill-partial"
    volumes = [f"{project}_{suffix}" for suffix in tool._VOLUME_SUFFIXES]
    existing = set()
    labels = {}
    removed = []

    monkeypatch.setattr(tool, "require_runtime", lambda *_: None)

    def fake_restore(*_args, **_kwargs):
        raise RuntimeError("restore interrupted")

    def fake_run(command, **_kwargs):
        if command[:3] == ["docker", "volume", "create"]:
            label = command[4].split("=", 1)[1]
            volume = command[5]
            existing.add(volume)
            labels[volume] = label
            return tool.subprocess.CompletedProcess(command, 0)
        if command[:4] == ["docker", "volume", "inspect", "--format"]:
            volume = command[5]
            return tool.subprocess.CompletedProcess(command, 0, stdout=labels.get(volume, "") + "\n")
        if command[:3] == ["docker", "volume", "inspect"]:
            return tool.subprocess.CompletedProcess(command, 0 if command[3] in existing else 1)
        if command[:3] == ["docker", "volume", "rm"]:
            removed.extend(command[3:])
            existing.difference_update(command[3:])
            return tool.subprocess.CompletedProcess(command, 0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tool, "restore", fake_restore)
    monkeypatch.setattr(tool.subprocess, "run", fake_run)
    args = tool.argparse.Namespace(
        archive=tmp_path / "backup.age",
        identity=tmp_path / "identity",
        target_project=project,
    )

    with pytest.raises(RuntimeError, match="restore interrupted"):
        tool.drill(args, tmp_path)

    assert removed == volumes
    assert not existing


@pytest.mark.p1
def test_encrypt_atomic_uses_destination_filesystem_and_leaves_no_temporary_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    tool = _load_tool()
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"
    source_dir.mkdir()
    destination_dir.mkdir()
    source = source_dir / "payload.tar.gz"
    destination = destination_dir / "backup.age"
    source.write_bytes(b"plain")
    observed = {}

    def fake_encrypt(_source: Path, temporary: Path, recipient: str):
        observed["temporary"] = temporary
        observed["recipient"] = recipient
        temporary.write_bytes(b"encrypted")

    monkeypatch.setattr(tool, "run_age_encrypt", fake_encrypt)

    tool.encrypt_atomic(source, destination, "age1recipient")

    assert destination.read_bytes() == b"encrypted"
    assert observed["temporary"].parent == destination_dir
    assert observed["recipient"] == "age1recipient"
    assert not observed["temporary"].exists()


@pytest.mark.p1
@pytest.mark.parametrize("project", ["", "Uppercase", "../escape", "project name", "-leading"])
def test_invalid_compose_project_names_are_rejected(project: str):
    tool = _load_tool()

    with pytest.raises(tool.BackupError, match="Compose project names"):
        tool.validate_project_name(project)
