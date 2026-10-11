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

from memory.services.graph import (
    EntityResolver,
    Triple,
    apply_triples,
    format_subgraph_for_prompt,
    load_triples_from_messages,
    parse_triples_from_llm_payload,
    select_relevant_triples,
)


class TestEntityResolver:
    def test_exact_and_fuzzy_merge(self):
        resolver = EntityResolver(["Neo4j"])
        assert resolver.resolve("neo4j") == "Neo4j"
        assert resolver.resolve("Neo 4j") in {"Neo4j", "Neo 4j"}  # high similarity or new
        # near identical should merge
        assert resolver.resolve("NEO4J") == "Neo4j"


class TestTripleParsing:
    def test_parse_payload(self):
        payload = {
            "triples": [
                {"head": "User", "relation": "prefers", "tail": "Neo4j", "is_correction": False, "confidence": 0.8},
                {"subject": "RAGFlow", "predicate": "stores", "object": "Memory"},
            ]
        }
        triples = parse_triples_from_llm_payload(payload)
        assert len(triples) == 2
        assert triples[0].head == "User"
        assert triples[0].relation == "prefers"
        assert triples[1].head == "RAGFlow"

    def test_roundtrip_content(self):
        t = Triple(head="A", relation="uses", tail="B", confidence=0.9, is_correction=True)
        parsed = Triple.from_content(t.to_content())
        assert parsed is not None
        assert parsed.head == "A"
        assert parsed.tail == "B"
        assert parsed.is_correction is True

    def test_prompt_context_preserves_personal_scope_and_provenance(self):
        triple = Triple(
            head="User",
            relation="prefers",
            tail="official framework patterns",
            confidence=0.95,
            attrs={
                "category": "work_style",
                "scope": "RAGFlow project",
                "source": "explicit",
                "stability": "long_term",
            },
        )
        context = format_subgraph_for_prompt([triple])
        assert '"category":"work_style"' in context
        assert '"scope":"RAGFlow project"' in context
        assert '"source":"explicit"' in context

    def test_load_expires_on_status_and_placeholder(self):
        active = {
            "message_id": 1,
            "message_type": "triple",
            "content": Triple(head="User", relation="prefers", tail="Neo4j").to_content(),
            "status": True,
            "invalid_at": "-",
        }
        inactive = {
            "message_id": 2,
            "message_type": "triple",
            "content": Triple(head="User", relation="prefers", tail="NetworkX").to_content(),
            "status": 0,
            "invalid_at": None,
        }
        triples = load_triples_from_messages([active, inactive])
        assert triples[0].status == "active"
        assert triples[0].invalid_at == ""
        assert triples[1].status == "expired"


class TestPersonalProfileRanking:
    def test_durable_explicit_user_profile_outranks_unrelated_fact(self):
        personal = Triple(
            head="User",
            relation="targets",
            tail="RAG engineering roles",
            confidence=0.75,
            attrs={"category": "goal", "source": "explicit", "stability": "long_term"},
        )
        generic = Triple(head="Python", relation="is", tail="a programming language", confidence=0.95)

        selected = select_relevant_triples([generic, personal], query="help me plan", max_edges=1)

        assert selected == [personal]


class TestApplyTriples:
    def _msg(self, message_id: int, triple: Triple):
        triple.message_id = message_id
        return {
            "message_id": message_id,
            "message_type": "triple",
            "content": triple.to_content(),
            "status": True,
            "valid_at": "2026-01-01 00:00:00",
            "invalid_at": None,
            "source_id": 1,
        }

    def test_idempotent_same_edge(self):
        existing = [self._msg(1, Triple(head="User", relation="prefers", tail="Neo4j"))]
        result = apply_triples(existing, [{"head": "user", "relation": "prefers", "tail": "neo4j"}], now="2026-01-02 00:00:00")
        assert result.new_triples == []
        assert result.expired_message_ids == []

    def test_correction_expires_old_edge(self):
        existing = [self._msg(1, Triple(head="User", relation="prefers", tail="Neo4j"))]
        result = apply_triples(
            existing,
            [{"head": "User", "relation": "prefers", "tail": "NetworkX", "is_correction": True, "confidence": 0.9}],
            now="2026-01-02 00:00:00",
        )
        assert len(result.new_triples) == 1
        assert result.new_triples[0].tail == "NetworkX"
        assert result.new_triples[0].is_correction is True
        assert result.expired_message_ids == [1]
        assert result.new_triples[0].supersedes == "1"

    def test_entity_not_split_on_alias(self):
        existing = [self._msg(1, Triple(head="Knowledge Graph", relation="supports", tail="Multi-hop QA"))]
        result = apply_triples(
            existing,
            [{"head": "knowledge graph", "relation": "uses", "tail": "Entity Resolution"}],
            now="2026-01-02 00:00:00",
        )
        assert len(result.new_triples) == 1
        assert result.new_triples[0].head == "Knowledge Graph"


class TestPromptFormatting:
    def test_format_and_select(self):
        triples = [
            Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.5),
            Triple(head="User", relation="uses", tail="RAGFlow", confidence=0.9),
            Triple(head="Doc", relation="about", tail="Cats", confidence=0.8, status="expired"),
        ]
        selected = select_relevant_triples(triples, query="What does user use?", seed_entities=["User"], max_edges=5)
        assert all(t.status == "active" for t in selected)
        assert selected[0].tail in {"RAGFlow", "Neo4j"}
        text = format_subgraph_for_prompt(selected)
        assert "[Memory Knowledge Graph]" in text
        assert "User" in text


class TestPipelineHelpers:
    def test_normalize_and_materialize(self):
        from memory.services.graph import (
            GraphWriteResult,
            Triple,
            materialize_triple_messages,
            normalize_llm_triple_dicts,
        )

        rows = normalize_llm_triple_dicts(
            [
                {"subject": "User", "predicate": "prefers", "object": "Neo4j", "confidence": 0.8},
                {"head": "", "relation": "x", "tail": ""},
            ],
            conversation_time="2026-01-01 00:00:00",
        )
        assert len(rows) == 1
        assert rows[0]["head"] == "User"
        assert rows[0]["valid_at"] == "2026-01-01 00:00:00"

        write = GraphWriteResult(
            new_triples=[Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.8)],
            expired_message_ids=[],
            entity_names=["Neo4j", "User"],
        )
        messages = materialize_triple_messages(
            write,
            memory_id="m1",
            source_message_id=9,
            user_id="u",
            agent_id="a",
            session_id="s",
            now="2026-01-02 00:00:00",
            id_factory=lambda: 101,
        )
        assert len(messages) == 1
        assert messages[0]["message_type"] == "triple"
        assert messages[0]["message_id"] == 101
        assert "User --prefers--> Neo4j" in messages[0]["content"]

    def test_build_context_from_messages(self):
        from memory.services.graph import Triple, build_graph_context_from_messages

        msgs = [
            {
                "message_id": 1,
                "message_type": "triple",
                "content": Triple(head="User", relation="uses", tail="RAGFlow", confidence=0.9).to_content(),
                "status": True,
                "invalid_at": "-",
            },
            {
                "message_id": 2,
                "message_type": "triple",
                "content": Triple(head="User", relation="prefers", tail="Neo4j", confidence=0.4).to_content(),
                "status": 0,
                "invalid_at": None,
            },
        ]
        text = build_graph_context_from_messages(msgs, query="What does User use?", top_n=5)
        assert "[Memory Knowledge Graph]" in text
        assert "RAGFlow" in text
        assert "Neo4j" not in text

    def test_multi_turn_correction_and_recall(self):
        from memory.services.graph import simulate_memory_graph_turns

        store, contexts = simulate_memory_graph_turns(
            [
                [{"head": "User", "relation": "prefers", "tail": "Neo4j", "confidence": 0.7}],
                [{"head": "User", "relation": "prefers", "tail": "NetworkX", "is_correction": True, "confidence": 0.95}],
                [{"head": "User", "relation": "uses", "tail": "RAGFlow", "confidence": 0.8}],
            ]
        )
        active = [m for m in store if m.get("status") is True]
        expired = [m for m in store if m.get("status") is False]
        assert len(expired) == 1
        assert any("NetworkX" in m["content"] for m in active)
        assert any("RAGFlow" in m["content"] for m in active)
        assert not any("Neo4j" in m["content"] and m.get("status") is True for m in store)
        assert "NetworkX" in contexts[-1]
        assert "RAGFlow" in contexts[-1]

