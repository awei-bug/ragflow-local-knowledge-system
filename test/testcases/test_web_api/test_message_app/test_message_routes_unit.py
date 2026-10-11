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

import asyncio
import importlib.util
import inspect
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class _DummyManager:
    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


class _AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


class _DummyArgs(dict):
    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


class _DummyMemoryApiService:
    async def add_message(self, *_args, **_kwargs):
        return True, "ok"

    async def get_messages(self, *_args, **_kwargs):
        return []

    async def search_message(self, *_args, **_kwargs):
        return []


def _run(coro):
    return asyncio.run(coro)


def _load_memory_routes_module(monkeypatch):
    repo_root = Path(__file__).resolve().parents[4]

    common_pkg = ModuleType("common")
    common_pkg.__path__ = [str(repo_root / "common")]
    monkeypatch.setitem(sys.modules, "common", common_pkg)

    apps_mod = ModuleType("api.apps")
    apps_mod.__path__ = [str(repo_root / "api" / "apps")]
    apps_mod.AUTH_API = "API"
    apps_mod.current_user = SimpleNamespace(id="user-1")
    apps_mod.login_required = lambda func: func
    monkeypatch.setitem(sys.modules, "api.apps", apps_mod)

    services_mod = ModuleType("api.apps.services")
    services_mod.memory_api_service = _DummyMemoryApiService()
    monkeypatch.setitem(sys.modules, "api.apps.services", services_mod)

    api_utils_mod = ModuleType("api.utils.api_utils")
    api_utils_mod.validate_request = lambda *_args, **_kwargs: (lambda func: func)
    api_utils_mod.get_request_json = lambda: _AwaitableValue({})
    api_utils_mod.get_error_argument_result = lambda message: {"code": 101, "message": message}
    api_utils_mod.get_json_result = lambda message=True, data=None, code=0, **kwargs: {
        "code": code,
        "message": message,
        "data": data,
        **kwargs,
    }
    monkeypatch.setitem(sys.modules, "api.utils.api_utils", api_utils_mod)

    tenant_model_mod = ModuleType("api.db.joint_services.tenant_model_service")
    tenant_model_mod.ensure_tenant_model_ids_for_params = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "api.db.joint_services.tenant_model_service", tenant_model_mod)

    pagination_mod = ModuleType("api.utils.pagination_utils")

    def _validate_page_size(page_size):
        if page_size > 100:
            raise ValueError("page_size must be less than or equal to 100")
        return page_size

    pagination_mod.validate_rest_api_page_size = _validate_page_size
    monkeypatch.setitem(sys.modules, "api.utils.pagination_utils", pagination_mod)

    module_name = "test_message_routes_unit_module"
    module_path = repo_root / "api" / "apps" / "restful_apis" / "memory_api.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    module.manager = _DummyManager()
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _set_request_json(monkeypatch, module, payload):
    monkeypatch.setattr(module, "get_request_json", lambda: _AwaitableValue(deepcopy(payload)))


@pytest.mark.p2
def test_add_message_partial_failure_branch(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)

    _set_request_json(
        monkeypatch,
        module,
        {
            "memory_id": ["memory-1"],
            "agent_id": "agent-1",
            "session_id": "session-1",
            "user_input": "hello",
            "agent_response": "world",
        },
    )

    async def _add_message(_memory_ids, _message_dict):
        return False, "cannot enqueue"

    monkeypatch.setattr(module.memory_api_service, "add_message", _add_message)

    res = _run(inspect.unwrap(module.add_message)())
    assert res["code"] == module.RetCode.SERVER_ERROR, res
    assert "Some messages failed to add" in res["message"], res


@pytest.mark.p2
def test_get_messages_csv_and_missing_memory_ids(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)

    monkeypatch.setattr(module, "request", SimpleNamespace(args=_DummyArgs({})))
    res = _run(inspect.unwrap(module.get_messages)())
    assert res["code"] == module.RetCode.ARGUMENT_ERROR, res
    assert "memory_ids is required." in res["message"], res

    monkeypatch.setattr(
        module,
        "request",
        SimpleNamespace(args=_DummyArgs({"memory_id": "m1,m2", "agent_id": "a1", "session_id": "s1", "limit": "5"})),
    )

    async def _get_messages(memory_ids, agent_id, session_id, limit):
        assert memory_ids == ["m1", "m2"]
        assert agent_id == "a1"
        assert session_id == "s1"
        assert limit == 5
        return [{"message_id": 1}]

    monkeypatch.setattr(module.memory_api_service, "get_messages", _get_messages)
    res = _run(inspect.unwrap(module.get_messages)())
    assert res["code"] == module.RetCode.SUCCESS, res
    assert isinstance(res["data"], list), res


@pytest.mark.p2
def test_get_messages_rejects_limit_above_rest_api_max(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "request",
        SimpleNamespace(args=_DummyArgs({"memory_id": "m1", "limit": "1000"})),
    )
    res = _run(inspect.unwrap(module.get_messages)())
    assert res["code"] == module.RetCode.ARGUMENT_ERROR, res
    assert "page_size must be less than or equal to 100" in res["message"], res


@pytest.mark.p2
def test_search_message_rejects_top_n_above_rest_api_max(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "request",
        SimpleNamespace(
            args=_DummyArgs({"memory_id": "m1", "query": "hello", "top_n": "500"})
        ),
    )

    async def _search_message(_filter_dict, _params):
        return []

    monkeypatch.setattr(module.memory_api_service, "search_message", _search_message)
    res = _run(inspect.unwrap(module.search_message)())
    assert res["code"] == module.RetCode.ARGUMENT_ERROR, res
    assert "page_size must be less than or equal to 100" in res["message"], res


@pytest.mark.p2
def test_search_message_includes_graph_context_field(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "request",
        SimpleNamespace(args=_DummyArgs({"memory_id": "m1", "query": "prefer NetworkX", "top_n": "5"})),
    )

    class _Result(list):
        graph_context = "[Memory Knowledge Graph]\n- (User) -[prefers]-> (NetworkX) confidence=0.95"

    async def _search_message(_filter_dict, _params):
        return _Result([{"message_id": 1, "content": "prefers NetworkX"}])

    monkeypatch.setattr(module.memory_api_service, "search_message", _search_message)
    res = _run(inspect.unwrap(module.search_message)())
    assert res["code"] == module.RetCode.SUCCESS, res
    assert isinstance(res["data"], list), res
    assert res["data"][0]["content"] == "prefers NetworkX"
    assert "graph_context" in res
    assert "NetworkX" in res["graph_context"]

@pytest.mark.p1
def test_add_message_uses_authenticated_user_for_session_requests(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)
    _set_request_json(
        monkeypatch,
        module,
        {
            "memory_id": ["memory-1"],
            "agent_id": "agent-1",
            "session_id": "session-1",
            "user_input": "hello",
            "agent_response": "world",
            "user_id": "attacker-supplied-id",
        },
    )

    captured = {}

    async def _add_message(memory_ids, message_dict):
        captured["memory_ids"] = memory_ids
        captured["message_dict"] = message_dict
        return True, "ok"

    monkeypatch.setattr(module.memory_api_service, "add_message", _add_message)
    res = _run(inspect.unwrap(module.add_message)())

    assert res["code"] == module.RetCode.SUCCESS, res
    assert captured["message_dict"]["user_id"] == "user-1"

@pytest.mark.p1
def test_add_message_preserves_external_subject_for_api_token_requests(monkeypatch):
    module = _load_memory_routes_module(monkeypatch)
    monkeypatch.setattr(module, "g", SimpleNamespace(auth_type=module.AUTH_API))
    _set_request_json(
        monkeypatch,
        module,
        {
            "memory_id": ["memory-1"],
            "agent_id": "agent-1",
            "session_id": "session-1",
            "user_input": "hello",
            "agent_response": "world",
            "user_id": "external-subject-1",
        },
    )

    captured = {}

    async def _add_message(memory_ids, message_dict):
        captured["memory_ids"] = memory_ids
        captured["message_dict"] = message_dict
        return True, "ok"

    monkeypatch.setattr(module.memory_api_service, "add_message", _add_message)
    res = _run(inspect.unwrap(module.add_message)())

    assert res["code"] == module.RetCode.SUCCESS, res
    assert captured["message_dict"]["user_id"] == "external-subject-1"
