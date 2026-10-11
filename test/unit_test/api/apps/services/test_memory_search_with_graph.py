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
"""Unit tests for REST memory search graph-context productization."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]


def _ensure_pkg(name: str, path: Path | None = None):
    if name in sys.modules and getattr(sys.modules[name], "__path__", None) is not None:
        return sys.modules[name]
    mod = ModuleType(name)
    if path is not None:
        mod.__path__ = [str(path)]
        mod.__file__ = str(path / "__init__.py")
    else:
        mod.__path__ = []
    sys.modules[name] = mod
    return mod


def _load_memory_api_service(monkeypatch, *, search_result):
    _ensure_pkg("api", _REPO_ROOT / "api")
    _ensure_pkg("api.apps", _REPO_ROOT / "api" / "apps")
    _ensure_pkg("api.apps.services", _REPO_ROOT / "api" / "apps" / "services")
    _ensure_pkg("api.db", _REPO_ROOT / "api" / "db")
    _ensure_pkg("api.db.services", _REPO_ROOT / "api" / "db" / "services")
    _ensure_pkg("api.db.joint_services", _REPO_ROOT / "api" / "db" / "joint_services")
    _ensure_pkg("api.utils", _REPO_ROOT / "api" / "utils")
    _ensure_pkg("memory", _REPO_ROOT / "memory")
    _ensure_pkg("memory.services", _REPO_ROOT / "memory" / "services")
    _ensure_pkg("memory.utils", _REPO_ROOT / "memory" / "utils")
    _ensure_pkg("common", _REPO_ROOT / "common")

    apps = ModuleType("api.apps")
    apps.current_user = SimpleNamespace(id="user-1")
    monkeypatch.setitem(sys.modules, "api.apps", apps)

    db_mod = ModuleType("api.db")
    db_mod.TenantPermission = SimpleNamespace(
        ME=SimpleNamespace(value="me"),
        TEAM=SimpleNamespace(value="team"),
    )
    db_mod.UserTenantRole = SimpleNamespace(
        NORMAL=SimpleNamespace(value="normal"),
        OWNER=SimpleNamespace(value="owner"),
        INVITE=SimpleNamespace(value="invite"),
    )
    monkeypatch.setitem(sys.modules, "api.db", db_mod)

    memory_service = ModuleType("api.db.services.memory_service")

    class MemoryService:
        _items = {
            "mem-1": SimpleNamespace(id="mem-1", tenant_id="user-1", permission="me", created_by="user-1"),
        }

        @classmethod
        def get_by_ids(cls, ids):
            return [cls._items[i] for i in ids if i in cls._items]

        @classmethod
        def get_by_memory_id(cls, memory_id):
            return cls._items.get(memory_id)

        @classmethod
        def get_accessible_by_ids(cls, ids, user_id):
            user_tenant_service = sys.modules["api.db.services.user_service"].UserTenantService
            joined_tenant_ids = {
                user_id,
                *[
                    tenant["tenant_id"]
                    for tenant in user_tenant_service.get_user_tenant_relation_by_user_id(user_id)
                    if tenant.get("status") == "1" and tenant.get("role") == "normal"
                ],
            }
            return [
                memory
                for memory in cls.get_by_ids(ids)
                if memory.tenant_id == user_id
                or (getattr(memory, "permissions", None) == "team" and memory.tenant_id in joined_tenant_ids)
            ]

        @classmethod
        def get_with_owner_name_by_id(cls, memory_id):
            return cls._items.get(memory_id)

    memory_service.MemoryService = MemoryService
    monkeypatch.setitem(sys.modules, "api.db.services.memory_service", memory_service)

    user_service = ModuleType("api.db.services.user_service")
    user_service.UserTenantService = SimpleNamespace(query=lambda **k: [], get_user_tenant_relation_by_user_id=lambda user_id: [])
    monkeypatch.setitem(sys.modules, "api.db.services.user_service", user_service)

    canvas_service = ModuleType("api.db.services.canvas_service")
    canvas_service.UserCanvasService = object
    monkeypatch.setitem(sys.modules, "api.db.services.canvas_service", canvas_service)

    task_service = ModuleType("api.db.services.task_service")
    task_service.TaskService = object
    monkeypatch.setitem(sys.modules, "api.db.services.task_service", task_service)

    joint = ModuleType("api.db.joint_services.memory_message_service")
    joint.get_memory_size_cache = lambda *a, **k: 0
    joint.judge_system_prompt_is_default = lambda *a, **k: True
    joint.queue_save_to_memory_task = lambda *a, **k: (True, "ok")
    joint.search_memory_with_graph = lambda filter_dict, params, exclude_graph_message_types=False: search_result
    monkeypatch.setitem(sys.modules, "api.db.joint_services.memory_message_service", joint)

    memory_utils = ModuleType("api.utils.memory_utils")
    memory_utils.format_ret_data_from_memory = lambda m: m
    memory_utils.get_memory_type_human = lambda x: ["raw"]
    monkeypatch.setitem(sys.modules, "api.utils.memory_utils", memory_utils)

    constants = ModuleType("api.constants")
    constants.MEMORY_NAME_LIMIT = 128
    constants.MEMORY_SIZE_LIMIT = 1024
    monkeypatch.setitem(sys.modules, "api.constants", constants)

    messages = ModuleType("memory.services.messages")
    messages.MessageService = object
    monkeypatch.setitem(sys.modules, "memory.services.messages", messages)

    prompt_util = ModuleType("memory.utils.prompt_util")
    prompt_util.PromptAssembler = object
    monkeypatch.setitem(sys.modules, "memory.utils.prompt_util", prompt_util)

    common_constants = ModuleType("common.constants")
    common_constants.MemoryType = SimpleNamespace(RAW=1)
    common_constants.ForgettingPolicy = SimpleNamespace(FIFO="FIFO")
    common_constants.StatusEnum = SimpleNamespace(VALID=SimpleNamespace(value="1"))
    monkeypatch.setitem(sys.modules, "common.constants", common_constants)

    exceptions = ModuleType("common.exceptions")
    exceptions.ArgumentException = type("ArgumentException", (Exception,), {})
    exceptions.NotFoundException = type("NotFoundException", (Exception,), {})
    monkeypatch.setitem(sys.modules, "common.exceptions", exceptions)

    time_utils = ModuleType("common.time_utils")
    time_utils.current_timestamp = lambda: 0
    time_utils.timestamp_to_date = lambda x: "2026-01-01"
    monkeypatch.setitem(sys.modules, "common.time_utils", time_utils)

    target = "api.apps.services.memory_api_service"
    if target in sys.modules:
        del sys.modules[target]
    spec = importlib.util.spec_from_file_location(target, _REPO_ROOT / "api" / "apps" / "services" / "memory_api_service.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[target] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.p1
def test_search_message_exposes_graph_context_on_list(monkeypatch):
    search_result = {
        "messages": [{"message_id": 1, "content": "hello", "message_type": "semantic"}],
        "graph_context": "[Memory Knowledge Graph]\n- (User) -[prefers]-> (NetworkX) confidence=0.95",
    }
    mod = _load_memory_api_service(monkeypatch, search_result=search_result)
    out = asyncio.run(mod.search_message({"memory_id": ["mem-1"]}, {"query": "prefer", "top_n": 5}))
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["content"] == "hello"
    assert getattr(out, "graph_context", "").startswith("[Memory Knowledge Graph]")
