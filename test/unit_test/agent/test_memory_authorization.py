from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _identity_timeout(_seconds):
    return lambda function: function


def _package(name: str, path: Path | None = None) -> ModuleType:
    module = ModuleType(name)
    module.__path__ = [] if path is None else [str(path)]
    return module


def _load_retrieval(monkeypatch):
    agent_pkg = _package("agent", _REPO_ROOT / "agent")
    tools_pkg = _package("agent.tools", _REPO_ROOT / "agent" / "tools")
    monkeypatch.setitem(sys.modules, "agent", agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.tools", tools_pkg)

    tools_base = ModuleType("agent.tools.base")
    tools_base.ToolParamBase = type("ToolParamBase", (), {})
    tools_base.ToolBase = type("ToolBase", (), {})
    tools_base.ToolMeta = dict
    monkeypatch.setitem(sys.modules, "agent.tools.base", tools_base)

    common_pkg = _package("common")
    common_constants = ModuleType("common.constants")
    common_constants.LLMType = SimpleNamespace(EMBEDDING="embedding", CHAT="chat")
    common_connection_utils = ModuleType("common.connection_utils")
    common_connection_utils.timeout = _identity_timeout
    common_metadata_utils = ModuleType("common.metadata_utils")
    common_metadata_utils.apply_meta_data_filter = lambda *args, **kwargs: None
    common_settings = ModuleType("common.settings")
    common_pkg.settings = common_settings
    monkeypatch.setitem(sys.modules, "common", common_pkg)
    monkeypatch.setitem(sys.modules, "common.constants", common_constants)
    monkeypatch.setitem(sys.modules, "common.connection_utils", common_connection_utils)
    monkeypatch.setitem(sys.modules, "common.metadata_utils", common_metadata_utils)
    monkeypatch.setitem(sys.modules, "common.settings", common_settings)

    api_pkg = _package("api", _REPO_ROOT / "api")
    api_db_pkg = _package("api.db", _REPO_ROOT / "api" / "db")
    api_services_pkg = _package("api.db.services", _REPO_ROOT / "api" / "db" / "services")
    api_joint_pkg = _package("api.db.joint_services", _REPO_ROOT / "api" / "db" / "joint_services")
    monkeypatch.setitem(sys.modules, "api", api_pkg)
    monkeypatch.setitem(sys.modules, "api.db", api_db_pkg)
    monkeypatch.setitem(sys.modules, "api.db.services", api_services_pkg)
    monkeypatch.setitem(sys.modules, "api.db.joint_services", api_joint_pkg)

    for module_name, symbol_name in (
        ("api.db.services.doc_metadata_service", "DocMetadataService"),
        ("api.db.services.knowledgebase_service", "KnowledgebaseService"),
        ("api.db.services.llm_service", "LLMBundle"),
    ):
        dependency = ModuleType(module_name)
        setattr(dependency, symbol_name, object)
        monkeypatch.setitem(sys.modules, module_name, dependency)

    memory_service = ModuleType("api.db.services.memory_service")
    memory_service.MemoryService = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "api.db.services.memory_service", memory_service)

    memory_message_service = ModuleType("api.db.joint_services.memory_message_service")
    monkeypatch.setitem(sys.modules, "api.db.joint_services.memory_message_service", memory_message_service)
    api_joint_pkg.memory_message_service = memory_message_service

    tenant_model_service = ModuleType("api.db.joint_services.tenant_model_service")
    tenant_model_service.get_tenant_default_model_by_type = lambda *args, **kwargs: None
    tenant_model_service.resolve_model_config = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "api.db.joint_services.tenant_model_service", tenant_model_service)

    rag_pkg = _package("rag")
    rag_app_pkg = _package("rag.app")
    rag_tag = ModuleType("rag.app.tag")
    rag_tag.label_question = lambda *args, **kwargs: None
    rag_prompts_pkg = _package("rag.prompts")
    rag_generator = ModuleType("rag.prompts.generator")
    rag_generator.cross_languages = lambda *args, **kwargs: []
    rag_generator.kb_prompt = lambda *args, **kwargs: []
    rag_generator.memory_prompt = lambda messages, _limit: [message["content"] for message in messages]
    monkeypatch.setitem(sys.modules, "rag", rag_pkg)
    monkeypatch.setitem(sys.modules, "rag.app", rag_app_pkg)
    monkeypatch.setitem(sys.modules, "rag.app.tag", rag_tag)
    monkeypatch.setitem(sys.modules, "rag.prompts", rag_prompts_pkg)
    monkeypatch.setitem(sys.modules, "rag.prompts.generator", rag_generator)

    module_name = "test_agent_memory_retrieval_authorization_module"
    module_path = _REPO_ROOT / "agent" / "tools" / "retrieval.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _load_message(monkeypatch):
    agent_pkg = _package("agent", _REPO_ROOT / "agent")
    component_pkg = _package("agent.component", _REPO_ROOT / "agent" / "component")
    monkeypatch.setitem(sys.modules, "agent", agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.component", component_pkg)

    component_base = ModuleType("agent.component.base")
    component_base.ComponentBase = object
    component_base.ComponentParamBase = object
    monkeypatch.setitem(sys.modules, "agent.component.base", component_base)

    common_pkg = _package("common")
    common_connection_utils = ModuleType("common.connection_utils")
    common_connection_utils.timeout = _identity_timeout
    common_misc_utils = ModuleType("common.misc_utils")
    common_misc_utils.get_uuid = lambda: "uuid"
    common_settings = ModuleType("common.settings")
    common_pkg.settings = common_settings
    monkeypatch.setitem(sys.modules, "common", common_pkg)
    monkeypatch.setitem(sys.modules, "common.connection_utils", common_connection_utils)
    monkeypatch.setitem(sys.modules, "common.misc_utils", common_misc_utils)
    monkeypatch.setitem(sys.modules, "common.settings", common_settings)

    api_pkg = _package("api", _REPO_ROOT / "api")
    api_db_pkg = _package("api.db", _REPO_ROOT / "api" / "db")
    api_services_pkg = _package("api.db.services", _REPO_ROOT / "api" / "db" / "services")
    api_joint_pkg = _package("api.db.joint_services", _REPO_ROOT / "api" / "db" / "joint_services")
    monkeypatch.setitem(sys.modules, "api", api_pkg)
    monkeypatch.setitem(sys.modules, "api.db", api_db_pkg)
    monkeypatch.setitem(sys.modules, "api.db.services", api_services_pkg)
    monkeypatch.setitem(sys.modules, "api.db.joint_services", api_joint_pkg)

    memory_service = ModuleType("api.db.services.memory_service")
    memory_service.MemoryService = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "api.db.services.memory_service", memory_service)

    memory_message_service = ModuleType("api.db.joint_services.memory_message_service")

    async def _unused_queue(*_args, **_kwargs):
        raise AssertionError("queue_save_to_memory_task should be replaced by the test")

    memory_message_service.queue_save_to_memory_task = _unused_queue
    monkeypatch.setitem(sys.modules, "api.db.joint_services.memory_message_service", memory_message_service)

    module_name = "test_agent_message_memory_authorization_module"
    module_path = _REPO_ROOT / "agent" / "component" / "message.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


class _RetrievalCanvas:
    _id = "current-agent"
    task_id = "current-session"

    def get_tenant_id(self):
        return "member-1"

    def get_variable_value(self, token):
        assert token == "{actor}"
        return "scoped-user"


class _MessageCanvas(_RetrievalCanvas):
    def get_sys_query(self):
        return "current user question"


def _make_retrieval(module):
    retrieval = module.Retrieval.__new__(module.Retrieval)
    retrieval._param = SimpleNamespace(
        memory_ids=["team-memory", "foreign-memory"],
        user_id="{actor}",
        similarity_threshold=0.2,
        keywords_similarity_weight=0.5,
        top_n=8,
        empty_response="empty",
    )
    retrieval._canvas = _RetrievalCanvas()
    retrieval.get_input_elements_from_text = lambda _text: {}
    retrieval.string_format = lambda text, _variables: text
    retrieval.set_output = lambda *_args: None
    return retrieval


def _make_message(module):
    message = module.Message.__new__(module.Message)
    message._param = SimpleNamespace(
        memory_ids=["team-memory", "foreign-memory"],
        user_id="{actor}",
        agent_id="spoofed-agent",
        session_id="spoofed-session",
    )
    message._canvas = _MessageCanvas()
    return message


@pytest.mark.p1
def test_agent_memory_retrieval_filters_foreign_memory_and_preserves_user_scope(monkeypatch):
    module = _load_retrieval(monkeypatch)
    retrieval = _make_retrieval(module)
    captured = {}

    def get_accessible_by_ids(memory_ids, user_id):
        captured["authorization"] = (memory_ids, user_id)
        return [SimpleNamespace(id="team-memory", embd_id="embedding-1")]

    def search_memory_with_graph(filter_dict, query_params, **kwargs):
        captured["filter"] = filter_dict
        captured["query"] = query_params
        captured["search_options"] = kwargs
        return {"messages": [{"content": "authorized result"}], "graph_context": ""}

    module.MemoryService.get_accessible_by_ids = get_accessible_by_ids
    module.memory_message_service.search_memory_with_graph = search_memory_with_graph

    result = asyncio.run(retrieval._retrieve_memory("question"))

    assert result == "authorized result"
    assert captured["authorization"] == (["team-memory", "foreign-memory"], "member-1")
    assert captured["filter"] == {"memory_id": ["team-memory"], "user_id": "scoped-user"}
    assert captured["query"]["query"] == "question"
    assert captured["search_options"] == {"exclude_graph_message_types": True}


@pytest.mark.p1
def test_agent_memory_retrieval_does_not_search_when_no_memory_is_authorized(monkeypatch):
    module = _load_retrieval(monkeypatch)
    retrieval = _make_retrieval(module)
    module.MemoryService.get_accessible_by_ids = lambda _memory_ids, _user_id: []
    module.memory_message_service.search_memory_with_graph = lambda *_args, **_kwargs: pytest.fail(
        "unauthorized memory must not reach search"
    )

    with pytest.raises(Exception, match="No authorized memory is selected"):
        asyncio.run(retrieval._retrieve_memory("question"))


@pytest.mark.p1
def test_agent_message_writes_only_authorized_memory_with_canvas_agent_and_session(monkeypatch):
    module = _load_message(monkeypatch)
    message = _make_message(module)
    captured = {}

    def get_accessible_by_ids(memory_ids, user_id):
        captured["authorization"] = (memory_ids, user_id)
        return [SimpleNamespace(id="team-memory")]

    async def queue_save_to_memory_task(memory_ids, message_dict):
        captured["memory_ids"] = memory_ids
        captured["message"] = message_dict
        return True, "queued"

    module.MemoryService.get_accessible_by_ids = get_accessible_by_ids
    module.queue_save_to_memory_task = queue_save_to_memory_task

    result = asyncio.run(message._save_to_memory("agent answer"))

    assert result == (True, "queued")
    assert captured["authorization"] == (["team-memory", "foreign-memory"], "member-1")
    assert captured["memory_ids"] == ["team-memory"]
    assert captured["message"] == {
        "user_id": "scoped-user",
        "agent_id": "current-agent",
        "session_id": "current-session",
        "user_input": "current user question",
        "agent_response": "agent answer",
    }


@pytest.mark.p1
def test_agent_message_does_not_queue_when_no_memory_is_authorized(monkeypatch):
    module = _load_message(monkeypatch)
    message = _make_message(module)
    module.MemoryService.get_accessible_by_ids = lambda _memory_ids, _user_id: []

    async def queue_save_to_memory_task(*_args, **_kwargs):
        pytest.fail("unauthorized memory must not reach the queue")

    module.queue_save_to_memory_task = queue_save_to_memory_task

    result = asyncio.run(message._save_to_memory("agent answer"))

    assert result == (False, "No authorized memory selected.")


