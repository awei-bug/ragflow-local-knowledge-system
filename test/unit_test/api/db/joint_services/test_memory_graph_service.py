#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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
"""Isolated wiring tests for memory knowledge-graph save/recall helpers.

The full api/common stack needs Python 3.13 + heavy deps. These tests load
``memory_message_service`` with stubs so the triple append/query path can be
verified without elasticsearch/peewee/quart.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]


class _FakeMsgStore:
    def __init__(self):
        self.docs: dict[int, dict] = {}
        self.search_calls: list[dict] = []
        self.update_calls: list[tuple[dict, dict]] = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        condition = kwargs.get("condition") or {}
        rows = []
        for doc in self.docs.values():
            matches = True
            for field, expected in condition.items():
                if field == "status":
                    actual = 1 if doc.get("status") in (True, 1, "1") else 0
                    if actual != int(expected):
                        matches = False
                        break
                elif isinstance(expected, (list, tuple, set)):
                    if doc.get(field) not in expected:
                        matches = False
                        break
                elif doc.get(field) != expected:
                    matches = False
                    break
            if matches:
                rows.append(doc)
        # mimic ES-like opaque result handle + total
        return rows, len(rows)

    def get_fields(self, res, fields):
        out = {}
        for doc in res or []:
            mid = doc.get("message_id")
            out[str(mid)] = {k: doc.get(k) for k in fields}
        return out

    def update(self, condition, update_dict, index_name, memory_id):
        self.update_calls.append((dict(condition), dict(update_dict)))
        ids = condition.get("message_id")
        if not isinstance(ids, list):
            ids = [ids]
        for mid in ids:
            if mid in self.docs:
                self.docs[mid].update(update_dict)
                if "status" in update_dict:
                    self.docs[mid]["status"] = bool(update_dict["status"]) if not isinstance(update_dict["status"], bool) else update_dict["status"]
                    # MessageService converts bool->int before store; accept either
                    if update_dict["status"] in (False, 0):
                        self.docs[mid]["status"] = False
        return True


def _ensure_pkg(name: str, path: Path | None = None):
    if name in sys.modules and getattr(sys.modules[name], "__path__", None) is not None:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if path is not None:
        mod.__path__ = [str(path)]  # type: ignore[attr-defined]
        mod.__file__ = str(path / "__init__.py")
    else:
        mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = mod
    return mod


def _install_stub_modules(fake_store: _FakeMsgStore):
    # Prefer real lightweight packages first so nested imports keep working.
    import common.constants as real_constants
    import common.time_utils as real_time_utils
    import common.misc_utils as real_misc
    import memory.services.graph as graph
    import memory.utils.prompt_util as prompt_util
    import memory.utils.msg_util as msg_util

    sys.modules["common.constants"] = real_constants
    sys.modules["common.time_utils"] = real_time_utils
    sys.modules["common.misc_utils"] = real_misc
    sys.modules["memory.services.graph"] = graph
    sys.modules["memory.utils.prompt_util"] = prompt_util
    sys.modules["memory.utils.msg_util"] = msg_util

    # package shells for heavy/unavailable deps
    _ensure_pkg("common", _REPO_ROOT / "common")
    _ensure_pkg("common.doc_store", _REPO_ROOT / "common" / "doc_store")
    _ensure_pkg("api", _REPO_ROOT / "api")
    _ensure_pkg("api.db", _REPO_ROOT / "api" / "db")
    _ensure_pkg("api.db.services", _REPO_ROOT / "api" / "db" / "services")
    _ensure_pkg("api.db.joint_services", _REPO_ROOT / "api" / "db" / "joint_services")
    _ensure_pkg("api.utils", _REPO_ROOT / "api" / "utils")
    _ensure_pkg("memory", _REPO_ROOT / "memory")
    _ensure_pkg("memory.services", _REPO_ROOT / "memory" / "services")
    _ensure_pkg("memory.utils", _REPO_ROOT / "memory" / "utils")
    _ensure_pkg("rag", _REPO_ROOT / "rag")
    _ensure_pkg("rag.utils", _REPO_ROOT / "rag" / "utils")

    # settings
    settings = types.ModuleType("common.settings")
    settings.msgStoreConn = fake_store
    sys.modules["common.settings"] = settings

    # OrderByExpr
    doc_store_base = types.ModuleType("common.doc_store.doc_store_base")

    class OrderByExpr:
        def __init__(self):
            self.fields = []

        def desc(self, field):
            self.fields.append(("desc", field))
            return self

        def asc(self, field):
            self.fields.append(("asc", field))
            return self

    class FusionExpr:
        def __init__(self, *a, **k):
            pass

    doc_store_base.OrderByExpr = OrderByExpr
    doc_store_base.FusionExpr = FusionExpr
    sys.modules["common.doc_store.doc_store_base"] = doc_store_base

    # db models / utils
    sys.modules["api.db.db_models"] = types.ModuleType("api.db.db_models")
    sys.modules["api.db.db_models"].Task = object
    sys.modules["api.db.db_utils"] = types.ModuleType("api.db.db_utils")
    sys.modules["api.db.db_utils"].bulk_insert_into_db = lambda *a, **k: None

    # TaskService
    task_service = types.ModuleType("api.db.services.task_service")

    class TaskService:
        @staticmethod
        def update_progress(task_id, payload):
            return True

        @staticmethod
        def update_by_id(task_id, payload):
            return True

        @staticmethod
        def get_by_id(task_id):
            return True, SimpleNamespace(id=task_id)

    task_service.TaskService = TaskService
    sys.modules["api.db.services.task_service"] = task_service

    # MemoryService
    memory_service = types.ModuleType("api.db.services.memory_service")

    class MemoryService:
        _items = {}

        @classmethod
        def get_by_memory_id(cls, memory_id: str):
            return cls._items.get(memory_id)

        @classmethod
        def get_by_ids(cls, pids, cols=None):
            return [cls._items[i] for i in pids if i in cls._items]

        @classmethod
        def get_all_memory(cls):
            return list(cls._items.values())

    memory_service.MemoryService = MemoryService
    sys.modules["api.db.services.memory_service"] = memory_service

    # LLM stubs
    llm_service = types.ModuleType("api.db.services.llm_service")

    class LLMBundle:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        async def async_chat(self, *a, **k):
            return "{}"

        def encode(self, texts):
            return [[0.1] * 8 for _ in texts], 8

    llm_service.LLMBundle = LLMBundle
    sys.modules["api.db.services.llm_service"] = llm_service

    tenant_model = types.ModuleType("api.db.joint_services.tenant_model_service")
    tenant_model.resolve_model_config = lambda *a, **k: {}
    tenant_model.get_model_config_by_id = lambda *a, **k: {}
    sys.modules["api.db.joint_services.tenant_model_service"] = tenant_model

    memory_utils = types.ModuleType("api.utils.memory_utils")
    memory_utils.get_memory_type_human = lambda x: ["semantic"] if not isinstance(x, list) else x
    sys.modules["api.utils.memory_utils"] = memory_utils

    # MessageService thin wrapper over fake store via settings
    messages = types.ModuleType("memory.services.messages")

    def index_name(uid: str):
        return f"mem_{uid}"

    class MessageService:
        @classmethod
        def update_message(cls, condition, update_dict, uid, memory_id):
            # mirror production bool->int conversion
            payload = dict(update_dict)
            if "status" in payload:
                payload["status"] = 1 if payload["status"] else 0
            return fake_store.update(condition, payload, index_name(uid), memory_id)

        @classmethod
        def insert_message(cls, messages_list, uid, memory_id):
            for m in messages_list:
                fake_store.docs[m["message_id"]] = dict(m)
            return []

        @classmethod
        def has_index(cls, uid, memory_id):
            return True

        @classmethod
        def create_index(cls, uid, memory_id, vector_size):
            return True

        @classmethod
        def calculate_message_size(cls, message):
            return len(str(message.get("content", "")))

        @classmethod
        def search_message(cls, *a, **k):
            return []

    messages.index_name = index_name
    messages.MessageService = MessageService
    sys.modules["memory.services.messages"] = messages

    # query helpers
    query = types.ModuleType("memory.services.query")
    query.MsgTextQuery = type("MsgTextQuery", (), {"question": lambda self, q, min_match=0.1: (None, None)})
    query.get_vector = lambda *a, **k: None
    sys.modules["memory.services.query"] = query

    redis_mod = types.ModuleType("rag.utils.redis_conn")

    class _Redis:
        def __init__(self):
            self._n = 1000

        def generate_auto_increment_id(self, namespace="memory"):
            self._n += 1
            return self._n

        def exist(self, key):
            return False

        def get(self, key):
            return "0"

        def set(self, key, val):
            return True

        def incrby(self, key, val):
            return True

        def decrby(self, key, val):
            return True

    redis_mod.REDIS_CONN = _Redis()
    sys.modules["rag.utils.redis_conn"] = redis_mod
    return memory_service.MemoryService


def _load_memory_message_service(fake_store: _FakeMsgStore):
    MemoryService = _install_stub_modules(fake_store)
    # force reload target module
    target = "api.db.joint_services.memory_message_service"
    if target in sys.modules:
        del sys.modules[target]
    spec = importlib.util.spec_from_file_location(
        target,
        _REPO_ROOT / "api" / "db" / "joint_services" / "memory_message_service.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[target] = mod
    spec.loader.exec_module(mod)
    return mod, MemoryService


@pytest.fixture
def graph_service_env():
    store = _FakeMsgStore()
    mod, MemoryService = _load_memory_message_service(store)
    memory = SimpleNamespace(
        id="mem-1",
        tenant_id="tenant-1",
        memory_type=1,
        temperature=0.1,
        tenant_llm_id=None,
        llm_id="chat-1",
        tenant_embd_id=None,
        embd_id="embd-1",
        memory_size=10_000_000,
        forgetting_policy="FIFO",
        name="demo",
    )
    MemoryService._items[memory.id] = memory
    return mod, store, memory


@pytest.mark.p1
def test_append_triples_writes_and_expires(graph_service_env):
    mod, store, memory = graph_service_env
    from memory.services.graph import Triple

    # seed one active edge in store
    existing = {
        "message_id": 11,
        "message_type": "triple",
        "source_id": 1,
        "memory_id": memory.id,
        "user_id": "u",
        "agent_id": "a",
        "session_id": "s",
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": None,
        "forget_at": None,
        "status": True,
        "content": Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.6).to_content(),
    }
    store.docs[11] = existing

    message_dict = {"user_id": "u", "agent_id": "a", "session_id": "s"}
    triples = [{"head": "User", "relation": "prefers", "tail": "NetworkX", "is_correction": True, "confidence": 0.95}]
    out = asyncio.run(mod._append_triples_to_message_list(memory, message_dict, source_message_id=2, triples=triples, message_list=[]))

    assert len(out) == 1
    assert out[0]["message_type"] == "triple"
    assert "NetworkX" in out[0]["content"]
    assert store.update_calls, "expected expire update"
    cond, payload = store.update_calls[0]
    assert cond["message_id"] == [11]
    assert payload["status"] in (0, False)
    assert payload.get("invalid_at")


@pytest.mark.p1
def test_append_triples_does_not_expire_another_identity_scope(graph_service_env):
    mod, store, memory = graph_service_env
    from memory.services.graph import Triple

    other_scope = {
        "message_id": 12,
        "message_type": "triple",
        "source_id": 1,
        "memory_id": memory.id,
        "user_id": "u2",
        "agent_id": "a1",
        "session_id": "s1",
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": None,
        "forget_at": None,
        "status": True,
        "content": Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.6).to_content(),
    }
    store.docs[12] = other_scope

    message_dict = {"user_id": "u1", "agent_id": "a1", "session_id": "s1"}
    triples = [{"head": "User", "relation": "prefers", "tail": "NetworkX", "is_correction": True, "confidence": 0.95}]
    out = asyncio.run(mod._append_triples_to_message_list(memory, message_dict, source_message_id=2, triples=triples, message_list=[]))

    assert len(out) == 1
    assert "NetworkX" in out[0]["content"]
    assert store.update_calls == []
    assert store.docs[12]["status"] is True
    assert store.docs[12]["invalid_at"] is None
    assert store.search_calls[-1]["condition"] == {
        "memory_id": memory.id,
        "message_type": "triple",
        "status": 1,
        "user_id": "u1",
        "agent_id": "a1",
        "session_id": "s1",
    }


@pytest.mark.p1
def test_query_memory_graph_context_isolated_by_identity_scope(graph_service_env):
    mod, store, memory = graph_service_env
    from memory.services.graph import Triple

    scoped_tails = [
        (21, "u1", "a1", "s1", "RAGFlow"),
        (22, "u2", "a1", "s1", "Neo4j"),
        (23, "u1", "a2", "s1", "NetworkX"),
        (24, "u1", "a1", "s2", "LangChain"),
    ]
    for message_id, user_id, agent_id, session_id, tail in scoped_tails:
        store.docs[message_id] = {
            "message_id": message_id,
            "message_type": "triple",
            "source_id": 1,
            "memory_id": memory.id,
            "user_id": user_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "valid_at": "2026-01-01 00:00:00",
            "invalid_at": None,
            "status": True,
            "content": Triple(head="User", relation="uses", tail=tail, confidence=0.9).to_content(),
        }

    text = mod.query_memory_graph_context(
        {"memory_id": [memory.id], "user_id": "u1", "agent_id": "a1", "session_id": "s1"},
        {"query": "What does User use?", "top_n": 10},
    )

    assert "RAGFlow" in text
    assert "Neo4j" not in text
    assert "NetworkX" not in text
    assert "LangChain" not in text
    assert store.search_calls[-1]["condition"] == {
        "memory_id": memory.id,
        "message_type": "triple",
        "status": 1,
        "user_id": "u1",
        "agent_id": "a1",
        "session_id": "s1",
    }


@pytest.mark.p1
def test_query_memory_graph_context_from_store(graph_service_env):
    mod, store, memory = graph_service_env
    from memory.services.graph import Triple

    store.docs[21] = {
        "message_id": 21,
        "message_type": "triple",
        "source_id": 1,
        "memory_id": memory.id,
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": "-",
        "status": True,
        "content": Triple(head="User", relation="uses", tail="RAGFlow", confidence=0.9).to_content(),
    }
    store.docs[22] = {
        "message_id": 22,
        "message_type": "triple",
        "source_id": 1,
        "memory_id": memory.id,
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": None,
        "status": False,
        "content": Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.4).to_content(),
    }

    text = mod.query_memory_graph_context({"memory_id": [memory.id]}, {"query": "What does User use?", "top_n": 5})
    assert "[Memory Knowledge Graph]" in text
    assert "RAGFlow" in text
    assert "Neo4j" not in text


@pytest.mark.p1
def test_extract_by_llm_returns_typed_and_triples(graph_service_env, monkeypatch):
    mod, store, memory = graph_service_env

    class _LLM:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        async def async_chat(self, *a, **k):
            return (
                '{"semantic":[{"content":"User prefers NetworkX for local graph work","valid_at":"2026-01-02T00:00:00","invalid_at":""}],'
                '"triples":[{"head":"User","relation":"prefers","tail":"NetworkX","confidence":0.9,"is_correction":true,'
                '"valid_at":"2026-01-02T00:00:00","invalid_at":""}]}'
            )

    monkeypatch.setattr(mod, "LLMBundle", lambda *a, **k: _LLM())
    monkeypatch.setattr(mod, "resolve_model_config", lambda *a, **k: {})

    typed, triples = asyncio.run(
        mod.extract_by_llm(
            tenant_id="tenant-1",
            tenant_llm_id=None,
            extract_conf={"temperature": 0.1},
            memory_type=["semantic"],
            user_input="I prefer NetworkX now",
            agent_response="Noted",
            entity_lexicon=["User", "Neo4j"],
        )
    )
    assert typed and typed[0]["message_type"] == "semantic"
    assert triples and triples[0]["tail"] == "NetworkX"
    assert triples[0]["is_correction"] is True


@pytest.mark.p1
def test_search_memory_with_graph_combines_messages_and_context(graph_service_env, monkeypatch):
    mod, store, memory = graph_service_env
    from memory.services.graph import Triple

    free_text = {
        "message_id": 31,
        "message_type": "semantic",
        "source_id": 1,
        "memory_id": memory.id,
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": None,
        "status": True,
        "content": "User prefers NetworkX for local graph work",
        "agent_id": "a1",
    }
    triple_msg = {
        "message_id": 32,
        "message_type": "triple",
        "source_id": 1,
        "memory_id": memory.id,
        "valid_at": "2026-01-01 00:00:00",
        "invalid_at": "-",
        "status": True,
        "content": Triple(head="User", relation="prefers", tail="NetworkX", confidence=0.95).to_content(),
    }
    store.docs[31] = free_text
    store.docs[32] = triple_msg

    monkeypatch.setattr(mod, "query_message", lambda filter_dict, params: [free_text, triple_msg])
    result = mod.search_memory_with_graph(
        {"memory_id": [memory.id]},
        {"query": "What graph library does User prefer?", "top_n": 5},
        exclude_graph_message_types=True,
    )
    assert isinstance(result, dict)
    assert result["messages"] == [free_text]
    assert "[Memory Knowledge Graph]" in result["graph_context"]
    assert "NetworkX" in result["graph_context"]

