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
from pathlib import Path


def test_testcase_config_can_load_without_model_api_keys(monkeypatch):
    monkeypatch.delenv("ZHIPU_AI_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    config_path = Path(__file__).resolve().parents[3] / "test" / "testcases" / "configs.py"
    spec = importlib.util.spec_from_file_location("testcase_configs_without_api_keys", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.ZHIPU_AI_API_KEY is None
    assert module.SILICONFLOW_API_KEY is None
