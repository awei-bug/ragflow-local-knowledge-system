from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


_REPO_ROOT = Path(__file__).resolve().parents[5]


def _load_memory_service(monkeypatch):
    api_pkg = ModuleType("api")
    api_pkg.__path__ = [str(_REPO_ROOT / "api")]
    monkeypatch.setitem(sys.modules, "api", api_pkg)

    db_pkg = ModuleType("api.db")
    db_pkg.TenantPermission = SimpleNamespace(TEAM=SimpleNamespace(value="team"))
    db_pkg.UserTenantRole = SimpleNamespace(NORMAL=SimpleNamespace(value="normal"))
    monkeypatch.setitem(sys.modules, "api.db", db_pkg)

    class _FakeDB:
        @staticmethod
        def connection_context():
            return lambda function: function

    db_models = ModuleType("api.db.db_models")
    db_models.DB = _FakeDB()
    db_models.Memory = object
    db_models.User = object
    monkeypatch.setitem(sys.modules, "api.db.db_models", db_models)

    services_pkg = ModuleType("api.db.services")
    services_pkg.duplicate_name = lambda *args, **kwargs: kwargs.get("name", "")
    monkeypatch.setitem(sys.modules, "api.db.services", services_pkg)

    common_service = ModuleType("api.db.services.common_service")
    common_service.CommonService = object
    monkeypatch.setitem(sys.modules, "api.db.services.common_service", common_service)

    user_service = ModuleType("api.db.services.user_service")
    user_service.UserTenantService = SimpleNamespace(get_user_tenant_relation_by_user_id=lambda _user_id: [])
    monkeypatch.setitem(sys.modules, "api.db.services.user_service", user_service)

    utils_pkg = ModuleType("api.utils")
    utils_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "api.utils", utils_pkg)
    memory_utils = ModuleType("api.utils.memory_utils")
    memory_utils.calculate_memory_type = lambda value: value
    monkeypatch.setitem(sys.modules, "api.utils.memory_utils", memory_utils)

    common_pkg = ModuleType("common")
    common_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "common", common_pkg)
    misc_utils = ModuleType("common.misc_utils")
    misc_utils.get_uuid = lambda: "uuid"
    monkeypatch.setitem(sys.modules, "common.misc_utils", misc_utils)
    time_utils = ModuleType("common.time_utils")
    time_utils.get_format_time = lambda: "2026-01-01"
    time_utils.current_timestamp = lambda: 0
    monkeypatch.setitem(sys.modules, "common.time_utils", time_utils)
    constants = ModuleType("common.constants")
    constants.StatusEnum = SimpleNamespace(VALID=SimpleNamespace(value="1"))
    monkeypatch.setitem(sys.modules, "common.constants", constants)

    memory_pkg = ModuleType("memory")
    memory_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "memory", memory_pkg)
    memory_utils_pkg = ModuleType("memory.utils")
    memory_utils_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "memory.utils", memory_utils_pkg)
    prompt_util = ModuleType("memory.utils.prompt_util")
    prompt_util.PromptAssembler = object
    monkeypatch.setitem(sys.modules, "memory.utils.prompt_util", prompt_util)

    module_name = "test_memory_service_authorization_module"
    module_path = _REPO_ROOT / "api" / "db" / "services" / "memory_service.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def test_get_accessible_by_ids_filters_to_owner_and_effective_team_members(monkeypatch):
    module = _load_memory_service(monkeypatch)
    memories = [
        SimpleNamespace(id="own", tenant_id="user-1", permissions="me"),
        SimpleNamespace(id="team", tenant_id="tenant-1", permissions="team"),
        SimpleNamespace(id="private", tenant_id="tenant-1", permissions="me"),
        SimpleNamespace(id="other", tenant_id="tenant-2", permissions="team"),
    ]
    module.MemoryService.get_by_ids = classmethod(lambda _cls, memory_ids: [m for m in memories if m.id in memory_ids])
    module.UserTenantService = sys.modules["api.db.services.user_service"].UserTenantService
    module.UserTenantService.get_user_tenant_relation_by_user_id = lambda _user_id: [
        {"tenant_id": "tenant-1", "role": "normal", "status": "1"},
        {"tenant_id": "tenant-2", "role": "normal", "status": "0"},
        {"tenant_id": "tenant-3", "role": "invite", "status": "1"},
    ]

    implementation = inspect.unwrap(module.MemoryService.get_accessible_by_ids)
    result = implementation(["own", "team", "private", "other"], "user-1")

    assert [memory.id for memory in result] == ["own", "team"]

