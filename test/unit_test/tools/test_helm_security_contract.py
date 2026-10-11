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

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_HELM_ROOT = _REPO_ROOT / "helm"


def test_helm_values_do_not_ship_default_passwords():
    values = (_HELM_ROOT / "values.yaml").read_text(encoding="utf-8")

    assert "infini_rag_flow" not in values
    assert 'RAGFLOW_SECRET_KEY: ""' in values
    assert 'MYSQL_PASSWORD: ""' in values
    assert 'MINIO_PASSWORD: ""' in values
    assert 'REDIS_PASSWORD: ""' in values


def test_helm_separates_non_sensitive_config_from_credentials():
    template = (_HELM_ROOT / "templates" / "env.yaml").read_text(encoding="utf-8")

    assert "kind: ConfigMap" in template
    assert "kind: Secret" in template
    assert "if not .Values.secrets.existingSecret" in template
    assert 'include "ragflow.envConfigName"' in template
    assert 'include "ragflow.envSecretName"' in template


def test_every_helm_workload_reads_config_and_secret_sources():
    for path in (_HELM_ROOT / "templates").glob("*.yaml"):
        if path.name == "env.yaml":
            continue
        source = path.read_text(encoding="utf-8")
        if 'include "ragflow.envSecretName"' in source:
            assert 'include "ragflow.envConfigName"' in source, path.name


def test_security_guards_are_first_actions_in_runtime_entrypoints():
    expectations = {
        _REPO_ROOT / "common" / "settings.py": ("init_settings", "validate_runtime_security"),
        _REPO_ROOT / "api" / "db" / "init_data.py": ("init_superuser", "validate_superuser_password"),
    }
    for path, (function_name, guard_name) in expectations.items():
        module = ast.parse(path.read_text(encoding="utf-8"))
        function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
        first_statement = function.body[0]
        assert isinstance(first_statement, ast.Expr)
        assert isinstance(first_statement.value, ast.Call)
        assert isinstance(first_statement.value.func, ast.Name)
        assert first_statement.value.func.id == guard_name
