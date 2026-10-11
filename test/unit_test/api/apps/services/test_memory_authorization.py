from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from test_memory_search_with_graph import _load_memory_api_service


def _configure_memory_access(mod, *, user_id="member-1", memberships=()):
    sys.modules["api.apps"].current_user.id = user_id
    sys.modules["api.db.services.user_service"].UserTenantService.get_user_tenant_relation_by_user_id = (
        lambda _user_id: list(memberships)
    )

    memory_service = sys.modules["api.db.services.memory_service"].MemoryService
    memory_service._items = {
        "owner-memory": SimpleNamespace(
            id="owner-memory", tenant_id="owner-1", permissions="team", memory_type=1
        ),
        "team-memory": SimpleNamespace(
            id="team-memory", tenant_id="tenant-1", permissions="team", memory_type=1
        ),
        "private-memory": SimpleNamespace(
            id="private-memory", tenant_id="owner-1", permissions="me", memory_type=1
        ),
        "other-memory": SimpleNamespace(
            id="other-memory", tenant_id="tenant-2", permissions="team", memory_type=1
        ),
    }
    return memory_service


def _valid_member(tenant_id="tenant-1"):
    return {"tenant_id": tenant_id, "role": "normal", "status": "1"}


def _invited_member(tenant_id="tenant-1"):
    return {"tenant_id": tenant_id, "role": "invite", "status": "1"}


def _revoked_member(tenant_id="tenant-1"):
    return {"tenant_id": tenant_id, "role": "normal", "status": "0"}


@pytest.mark.p1
def test_valid_team_member_can_read_team_memory_but_not_private_memory(monkeypatch):
    mod = _load_memory_api_service(monkeypatch, search_result={"messages": [], "graph_context": ""})
    _configure_memory_access(mod, memberships=[_valid_member()])

    team_memory = asyncio.run(mod.get_memory_config("team-memory"))
    assert team_memory.id == "team-memory"

    with pytest.raises(mod.NotFoundException):
        asyncio.run(mod.get_memory_config("private-memory"))


@pytest.mark.p1
@pytest.mark.parametrize("membership", [_invited_member(), _revoked_member(), {}])
def test_non_effective_team_members_cannot_read_team_memory(monkeypatch, membership):
    mod = _load_memory_api_service(monkeypatch, search_result={"messages": [], "graph_context": ""})
    _configure_memory_access(mod, memberships=[membership] if membership else [])

    with pytest.raises(mod.NotFoundException):
        asyncio.run(mod.get_memory_config("team-memory"))


@pytest.mark.p1
def test_team_member_can_search_and_append_only_authorized_memories(monkeypatch):
    mod = _load_memory_api_service(
        monkeypatch,
        search_result={"messages": [{"message_id": 1}], "graph_context": "graph"},
    )
    _configure_memory_access(mod, memberships=[_valid_member()])

    captured = {}

    async def save_to_memory(memory_ids, message):
        captured["memory_ids"] = memory_ids
        captured["message"] = message
        return True, "ok"

    mod.queue_save_to_memory_task = save_to_memory
    result = asyncio.run(
        mod.search_message(
            {"memory_id": ["team-memory", "other-memory"]},
            {"query": "hello"},
        )
    )
    assert result == [{"message_id": 1}]
    assert result.graph_context == "graph"

    success, message = asyncio.run(
        mod.add_message(
            ["team-memory", "other-memory"],
            {"session_id": "session-1", "user_input": "hello"},
        )
    )
    assert (success, message) == (True, "ok")
    assert captured["memory_ids"] == ["team-memory"]


@pytest.mark.p1
@pytest.mark.parametrize(
    "operation",
    [
        lambda mod: mod.update_memory("team-memory", {}),
        lambda mod: mod.delete_memory("team-memory"),
        lambda mod: mod.forget_message("team-memory", 1),
        lambda mod: mod.update_message_status("team-memory", 1, False),
    ],
)
def test_team_member_cannot_mutate_or_manage_team_memory(monkeypatch, operation):
    mod = _load_memory_api_service(monkeypatch, search_result={"messages": [], "graph_context": ""})
    _configure_memory_access(mod, memberships=[_valid_member()])

    with pytest.raises(mod.NotFoundException):
        asyncio.run(operation(mod))


@pytest.mark.p1
def test_owner_remains_authorized_for_owner_only_guard(monkeypatch):
    mod = _load_memory_api_service(monkeypatch, search_result={"messages": [], "graph_context": ""})
    _configure_memory_access(mod, user_id="owner-1")

    memory = mod._require_memory_owner("owner-memory")
    assert memory.id == "owner-memory"


@pytest.mark.p1
def test_normal_member_role_is_not_enough_when_membership_status_is_invalid(monkeypatch):
    mod = _load_memory_api_service(monkeypatch, search_result={"messages": [], "graph_context": ""})
    _configure_memory_access(mod, memberships=[_revoked_member("tenant-1"), _valid_member("tenant-2")])

    assert mod._joined_tenant_ids("member-1") == {"member-1", "tenant-2"}
