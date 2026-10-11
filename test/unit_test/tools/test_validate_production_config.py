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
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOL_PATH = _REPO_ROOT / "tools" / "ops" / "validate_production_config.py"


def _load_tool():
    module_name = "enterprise_production_config_validator"
    spec = importlib.util.spec_from_file_location(module_name, _TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _application_environment():
    return {
        "RAGFLOW_DEPLOYMENT_MODE": "production",
        "RAGFLOW_SECRET_KEY": "session-Key-2026-09-04-abcdefXYZ123456",
        "MYSQL_PASSWORD": "mysql-Strong-Secret-2026!",
        "REDIS_PASSWORD": "redis-Strong-Secret-2026!",
        "MINIO_PASSWORD": "minio-Strong-Secret-2026!",
        "DOC_ENGINE": "infinity",
    }


def _config():
    return {
        "services": {
            "ragflow-cpu": {
                "environment": _application_environment(),
                "ports": [{"target": 80, "published": "8080"}],
            },
            "mysql": {"environment": {}, "ports": []},
            "redis": {"environment": {}, "ports": []},
        }
    }


@pytest.mark.p1
def test_resolved_production_config_accepts_only_public_application_ports():
    tool = _load_tool()

    tool.validate_compose_config(_config())


@pytest.mark.p1
def test_resolved_production_config_rejects_internal_published_ports():
    tool = _load_tool()
    config = _config()
    config["services"]["mysql"]["ports"] = [{"target": 3306, "published": "3306"}]

    with pytest.raises(tool.ProductionConfigError, match="internal service mysql publishes host ports"):
        tool.validate_compose_config(config)


@pytest.mark.p1
def test_resolved_production_config_requires_explicit_production_mode():
    tool = _load_tool()
    config = _config()
    del config["services"]["ragflow-cpu"]["environment"]["RAGFLOW_DEPLOYMENT_MODE"]

    with pytest.raises(tool.ProductionConfigError, match="RAGFLOW_DEPLOYMENT_MODE=production"):
        tool.validate_compose_config(config)


@pytest.mark.p1
def test_validator_cli_never_prints_secret_values(tmp_path: Path, capsys):
    tool = _load_tool()
    config = _config()
    leaked_value = "never-print-this-value"
    config["services"]["ragflow-cpu"]["environment"]["RAGFLOW_SECRET_KEY"] = leaked_value
    config_path = tmp_path / "compose.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    assert tool.main(["--config-json", str(config_path)]) == 2

    output = capsys.readouterr()
    assert "RAGFLOW_SECRET_KEY" in output.err
    assert leaked_value not in output.err


@pytest.mark.p1
def test_validator_cli_accepts_resolved_safe_config(tmp_path: Path, capsys):
    tool = _load_tool()
    config_path = tmp_path / "compose.json"
    config_path.write_text(json.dumps(_config()), encoding="utf-8")

    assert tool.main(["--config-json", str(config_path)]) == 0
    assert "validation passed" in capsys.readouterr().out
