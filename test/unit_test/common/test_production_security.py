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

import pytest

from common.security_config import SecurityConfigurationError, validate_runtime_security, validate_superuser_password


def _production_environment(**overrides):
    environment = {
        "RAGFLOW_DEPLOYMENT_MODE": "production",
        "RAGFLOW_SECRET_KEY": "session-Key-2026-09-04-abcdefXYZ123456",
        "DB_TYPE": "mysql",
        "MYSQL_PASSWORD": "mysql-Strong-Secret-2026!",
        "REDIS_PASSWORD": "redis-Strong-Secret-2026!",
        "STORAGE_IMPL": "MINIO",
        "MINIO_PASSWORD": "minio-Strong-Secret-2026!",
        "DOC_ENGINE": "infinity",
    }
    environment.update(overrides)
    return environment


@pytest.mark.p1
def test_development_mode_preserves_local_defaults():
    assert validate_runtime_security({}) == "development"


@pytest.mark.p1
def test_unknown_deployment_mode_fails_closed():
    with pytest.raises(SecurityConfigurationError, match="RAGFLOW_DEPLOYMENT_MODE must be one of"):
        validate_runtime_security({"RAGFLOW_DEPLOYMENT_MODE": "prodution"})


@pytest.mark.p1
def test_production_requires_active_secrets_without_leaking_values():
    leaked_value = "do-not-log-this-secret"
    environment = _production_environment(RAGFLOW_SECRET_KEY=leaked_value, REDIS_PASSWORD="infini_rag_flow")

    with pytest.raises(SecurityConfigurationError) as exc_info:
        validate_runtime_security(environment)

    message = str(exc_info.value)
    assert "RAGFLOW_SECRET_KEY" in message
    assert "REDIS_PASSWORD" in message
    assert leaked_value not in message
    assert "infini_rag_flow" not in message


@pytest.mark.p1
@pytest.mark.parametrize(
    ("doc_engine", "password_name"),
    [
        ("elasticsearch", "ELASTIC_PASSWORD"),
        ("opensearch", "OPENSEARCH_PASSWORD"),
        ("oceanbase", "OCEANBASE_PASSWORD"),
        ("seekdb", "SEEKDB_PASSWORD"),
    ],
)
def test_production_requires_password_for_active_document_engine(doc_engine, password_name):
    environment = _production_environment(DOC_ENGINE=doc_engine)

    with pytest.raises(SecurityConfigurationError, match=password_name):
        validate_runtime_security(environment)

    environment[password_name] = f"{doc_engine}-Strong-Secret-2026!"
    assert validate_runtime_security(environment) == "production"


@pytest.mark.p1
def test_production_accepts_strong_active_secrets():
    assert validate_runtime_security(_production_environment()) == "production"


@pytest.mark.p1
def test_production_encryption_requires_a_strong_crypto_key():
    environment = _production_environment(RAGFLOW_CRYPTO_ENABLED="true")

    with pytest.raises(SecurityConfigurationError, match="RAGFLOW_CRYPTO_KEY"):
        validate_runtime_security(environment)

    environment["RAGFLOW_CRYPTO_KEY"] = "storage-Key-2026-09-04-abcdefXYZ123456"
    assert validate_runtime_security(environment) == "production"


@pytest.mark.p1
def test_production_superuser_rejects_default_password_without_leaking_it():
    with pytest.raises(SecurityConfigurationError) as exc_info:
        validate_superuser_password("admin", _production_environment())

    assert "DEFAULT_SUPERUSER_PASSWORD" in str(exc_info.value)
    assert "admin" not in str(exc_info.value)


@pytest.mark.p1
def test_development_superuser_remains_backward_compatible():
    validate_superuser_password("admin", {})
