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

"""Validate a fully resolved Docker Compose configuration for production use."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.security_config import SecurityConfigurationError, validate_production_environment


_DEFAULT_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose.yml"
_DEFAULT_PRODUCTION_OVERLAY = _REPO_ROOT / "docker" / "docker-compose.production.yml"
_DEFAULT_PUBLIC_SERVICES = frozenset({"ragflow-cpu", "ragflow-gpu"})


class ProductionConfigError(RuntimeError):
    """Raised when the resolved deployment configuration is unsafe."""


def _service_environment(service: Mapping[str, Any]) -> dict[str, str]:
    raw_environment = service.get("environment", {})
    if isinstance(raw_environment, Mapping):
        return {str(key): "" if value is None else str(value) for key, value in raw_environment.items()}
    if isinstance(raw_environment, Sequence) and not isinstance(raw_environment, (str, bytes)):
        result = {}
        for item in raw_environment:
            name, separator, value = str(item).partition("=")
            if separator:
                result[name] = value
        return result
    raise ProductionConfigError("service environment must be a mapping or a list")


def _has_published_ports(service: Mapping[str, Any]) -> bool:
    ports = service.get("ports")
    return isinstance(ports, Sequence) and not isinstance(ports, (str, bytes)) and bool(ports)


def validate_compose_config(config: Mapping[str, Any], allowed_published_services: set[str] | frozenset[str] = _DEFAULT_PUBLIC_SERVICES) -> None:
    """Reject internal published ports and validate each application container's secrets."""

    services = config.get("services")
    if not isinstance(services, Mapping) or not services:
        raise ProductionConfigError("resolved Compose configuration has no services")

    errors = []
    application_services = []
    for raw_name, raw_service in services.items():
        name = str(raw_name)
        if not isinstance(raw_service, Mapping):
            errors.append(f"service {name} is not an object")
            continue
        if _has_published_ports(raw_service) and name not in allowed_published_services:
            errors.append(f"internal service {name} publishes host ports")
        if name in allowed_published_services:
            application_services.append((name, raw_service))

    if not application_services:
        errors.append("no RAGFlow application service is present in the resolved configuration")

    for name, service in application_services:
        environment = _service_environment(service)
        if environment.get("RAGFLOW_DEPLOYMENT_MODE") != "production":
            errors.append(f"service {name} does not set RAGFLOW_DEPLOYMENT_MODE=production")
            continue
        try:
            validate_production_environment(environment)
        except SecurityConfigurationError as exc:
            errors.append(f"service {name}: {exc}")

    if errors:
        raise ProductionConfigError("; ".join(errors))


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionConfigError(f"could not read resolved Compose JSON from {path}") from exc
    if not isinstance(payload, Mapping):
        raise ProductionConfigError("resolved Compose JSON root must be an object")
    return payload


def resolve_compose_config(compose_files: Sequence[Path], env_file: Path | None = None) -> Mapping[str, Any]:
    command = ["docker", "compose"]
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    for compose_file in compose_files:
        command.extend(["-f", str(compose_file)])
    command.extend(["config", "--format", "json"])

    try:
        result = subprocess.run(command, cwd=_REPO_ROOT, check=True, capture_output=True, env=os.environ.copy())
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProductionConfigError("docker compose config failed; inspect the command locally without logging resolved secrets") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProductionConfigError("docker compose returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ProductionConfigError("resolved Compose JSON root must be an object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-json", type=Path, help="Validate previously resolved Compose JSON instead of invoking Docker")
    parser.add_argument("--compose-file", type=Path, action="append", dest="compose_files", help="Compose file; may be repeated")
    parser.add_argument("--env-file", type=Path, help="Environment file passed to docker compose")
    parser.add_argument(
        "--allow-published-service",
        action="append",
        default=[],
        help="Additional service allowed to publish host ports; may be repeated",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.config_json:
            config = _load_json(args.config_json)
        else:
            compose_files = args.compose_files or [_DEFAULT_COMPOSE_FILE, _DEFAULT_PRODUCTION_OVERLAY]
            config = resolve_compose_config(compose_files, args.env_file)
        allowed_services = set(_DEFAULT_PUBLIC_SERVICES)
        allowed_services.update(args.allow_published_service)
        validate_compose_config(config, allowed_services)
    except ProductionConfigError as exc:
        print(f"Production configuration validation failed: {exc}", file=sys.stderr)
        return 2

    print("Production configuration validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

