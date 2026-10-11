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
"""Pure payload-shape test for memory search graph productization.

Avoids loading the full memory_api route module (heavy transitive imports).
"""

from __future__ import annotations

from types import SimpleNamespace


def _build_search_payload(res):
    """Mirror GET /messages/search response assembly."""
    graph_context = getattr(res, "graph_context", "") or ""
    return {
        "code": 0,
        "message": True,
        "data": res,
        "graph_context": graph_context,
    }


def test_search_payload_keeps_list_data_and_graph_context_sibling():
    class _Result(list):
        graph_context = "[Memory Knowledge Graph]\n- (User) -[prefers]-> (NetworkX) confidence=0.95"

    res = _Result([{"message_id": 1, "content": "prefers NetworkX"}])
    payload = _build_search_payload(res)
    assert isinstance(payload["data"], list)
    assert payload["data"][0]["content"] == "prefers NetworkX"
    assert "NetworkX" in payload["graph_context"]


def test_search_payload_empty_list_without_graph_attr():
    payload = _build_search_payload([])
    assert payload["data"] == []
    assert payload["graph_context"] == ""
