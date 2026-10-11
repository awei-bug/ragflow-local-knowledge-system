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

"""Fail-closed security validation for production deployments."""

from __future__ import annotations

import os
from collections.abc import Mapping


DEPLOYMENT_MODE_ENV = "RAGFLOW_DEPLOYMENT_MODE"
DEVELOPMENT_MODE = "development"
PRODUCTION_MODE = "production"
_ALLOWED_MODES = frozenset({DEVELOPMENT_MODE, PRODUCTION_MODE})

_DEFAULT_SECRET_VALUES = frozenset(
    {
        "admin",
        "changeme",
        "change-me",
        "default",
        "infini_rag_flow",
        "infini_rag_flow_helm",
        "infini_rag_flow_os_01",
        "password",
        "ragflow",
        "replace-me",
        "root",
        "secret",
        "test",
    }
)


class SecurityConfigurationError(RuntimeError):
    """Raised when a deployment would start with an unsafe security configuration."""


def get_deployment_mode(environ: Mapping[str, str] | None = None) -> str:
    """Return the explicit deployment mode and reject misspellings."""

    values = os.environ if environ is None else environ
    raw_mode = values.get(DEPLOYMENT_MODE_ENV, DEVELOPMENT_MODE)
    mode = str(raw_mode).strip().lower()
    if mode not in _ALLOWED_MODES:
        allowed = ", ".join(sorted(_ALLOWED_MODES))
        raise SecurityConfigurationError(f"{DEPLOYMENT_MODE_ENV} must be one of: {allowed}")
    return mode


def _is_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return (
        (value.startswith("<") and value.endswith(">"))
        or "${" in value
        or lowered.startswith("your-")
        or lowered.startswith("your_")
        or lowered.startswith("example-")
    )


def _secret_issue(name: str, value: str | None, minimum_length: int) -> str | None:
    if value is None or not str(value).strip():
        return f"{name} is required"

    secret = str(value)
    normalized = secret.strip().casefold()
    if secret != secret.strip():
        return f"{name} must not have leading or trailing whitespace"
    if normalized in _DEFAULT_SECRET_VALUES or normalized.startswith("infini_rag_flow") or _is_placeholder(secret):
        return f"{name} uses a default or placeholder value"
    if len(secret) < minimum_length:
        return f"{name} must contain at least {minimum_length} characters"
    if len(set(secret)) < 8:
        return f"{name} has insufficient character diversity"
    return None


def _required_production_secrets(environ: Mapping[str, str]) -> dict[str, int]:
    required = {
        "RAGFLOW_SECRET_KEY": 32,
        "REDIS_PASSWORD": 16,
    }

    database_type = str(environ.get("DB_TYPE", "mysql")).strip().lower()
    if database_type in {"mysql", "mariadb"}:
        required["MYSQL_PASSWORD"] = 16
    elif database_type in {"postgres", "postgresql"}:
        required["POSTGRES_PASSWORD"] = 16

    storage_type = str(environ.get("STORAGE_IMPL", "MINIO")).strip().upper()
    if storage_type == "MINIO":
        required["MINIO_PASSWORD"] = 16

    doc_engine = str(environ.get("DOC_ENGINE", "elasticsearch")).strip().lower()
    engine_passwords = {
        "elasticsearch": "ELASTIC_PASSWORD",
        "opensearch": "OPENSEARCH_PASSWORD",
        "oceanbase": "OCEANBASE_PASSWORD",
        "seekdb": "SEEKDB_PASSWORD",
    }
    if password_name := engine_passwords.get(doc_engine):
        required[password_name] = 16

    if str(environ.get("RAGFLOW_CRYPTO_ENABLED", "false")).strip().lower() in {"1", "true", "yes"}:
        required["RAGFLOW_CRYPTO_KEY"] = 32

    return required


def validate_production_environment(environ: Mapping[str, str] | None = None) -> None:
    """Validate active production secrets without including their values in errors."""

    values = os.environ if environ is None else environ
    issues = []
    for name, minimum_length in _required_production_secrets(values).items():
        if issue := _secret_issue(name, values.get(name), minimum_length):
            issues.append(issue)

    configured_superuser_password = values.get("DEFAULT_SUPERUSER_PASSWORD")
    if configured_superuser_password is not None:
        if issue := _secret_issue("DEFAULT_SUPERUSER_PASSWORD", configured_superuser_password, 16):
            issues.append(issue)

    if issues:
        details = "; ".join(sorted(set(issues)))
        raise SecurityConfigurationError(f"Production security validation failed: {details}")


def validate_runtime_security(environ: Mapping[str, str] | None = None) -> str:
    """Validate deployment mode and production-only runtime requirements."""

    values = os.environ if environ is None else environ
    mode = get_deployment_mode(values)
    if mode == PRODUCTION_MODE:
        validate_production_environment(values)
    return mode


def validate_superuser_password(password: str | None, environ: Mapping[str, str] | None = None) -> None:
    """Reject unsafe bootstrap credentials when creating a production superuser."""

    values = os.environ if environ is None else environ
    if get_deployment_mode(values) != PRODUCTION_MODE:
        return
    if issue := _secret_issue("DEFAULT_SUPERUSER_PASSWORD", password, 16):
        raise SecurityConfigurationError(f"Production superuser initialization refused: {issue}")
