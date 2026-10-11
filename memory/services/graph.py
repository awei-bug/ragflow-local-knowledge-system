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
"""Incremental memory knowledge-graph helpers.

Stores triples as normal memory messages (message_type=triple) so they reuse the
existing vector index / FIFO / forget machinery. Edges are append-only: corrections
expire old edges instead of overwriting them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

TRIPLE_MESSAGE_TYPE = "triple"
META_MARKER = "#meta:"
DEFAULT_SIMILARITY = 0.86


def is_blank_timestamp(value: Any) -> bool:
    """Treat store placeholders for 'no time' as empty."""
    if value is None:
        return True
    text = str(value).strip()
    return text in {"", "-", "None", "null", "0", "0.0"}


def message_is_active(status: Any) -> bool:
    """Memory store may expose status as bool/int/str."""
    if status is False or status is None:
        return False
    if isinstance(status, (int, float)):
        return int(status) != 0
    if isinstance(status, str):
        return status.strip().casefold() not in {"", "0", "false", "no", "off", "expired"}
    return bool(status)


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    text = str(name).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_entity_key(name: str | None) -> str:
    return normalize_entity_name(name).casefold()


def normalize_relation(relation: str | None) -> str:
    if not relation:
        return "related_to"
    text = str(relation).strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff\-]+", "", text)
    return text or "related_to"


def reverse_relation_name(relation: str | None) -> str:
    relation = normalize_relation(relation)
    defaults = {
        "is_a": "includes",
        "part_of": "has_part",
        "depends_on": "required_by",
        "uses": "used_by",
        "owns": "owned_by",
        "works_at": "employs",
        "located_in": "contains",
        "prefers": "preferred_by",
        "corrects": "corrected_by",
        "replaces": "replaced_by",
        "related_to": "related_to",
    }
    return defaults.get(relation.casefold(), f"reverse_of_{relation}")


@dataclass
class Triple:
    head: str
    relation: str
    tail: str
    reverse_relation: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)
    is_correction: bool = False
    supersedes: str | None = None
    confidence: float = 0.5
    entity_type_head: str = "concept"
    entity_type_tail: str = "concept"
    valid_at: str = ""
    invalid_at: str = ""
    status: str = "active"
    source_message_id: int | None = None
    message_id: int | None = None

    def __post_init__(self) -> None:
        self.head = normalize_entity_name(self.head)
        self.tail = normalize_entity_name(self.tail)
        self.relation = normalize_relation(self.relation)
        self.reverse_relation = normalize_relation(self.reverse_relation) if self.reverse_relation else reverse_relation_name(self.relation)
        try:
            self.confidence = float(self.confidence)
        except (TypeError, ValueError):
            self.confidence = 0.5
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.is_correction = bool(self.is_correction)
        if self.status not in {"active", "expired"}:
            self.status = "active"

    @property
    def edge_key(self) -> tuple[str, str, str]:
        return canonical_entity_key(self.head), self.relation.casefold(), canonical_entity_key(self.tail)

    def readable(self) -> str:
        marker = " [correction]" if self.is_correction else ""
        return f"{self.head} --{self.relation}--> {self.tail}{marker}"

    def to_meta(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "relation": self.relation,
            "tail": self.tail,
            "reverse_relation": self.reverse_relation,
            "attrs": self.attrs or {},
            "is_correction": self.is_correction,
            "supersedes": self.supersedes,
            "confidence": self.confidence,
            "entity_type_head": self.entity_type_head or "concept",
            "entity_type_tail": self.entity_type_tail or "concept",
            "status": self.status,
        }

    def to_content(self) -> str:
        return f"{self.readable()}\n{META_MARKER}{json.dumps(self.to_meta(), ensure_ascii=False)}"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Triple | None:
        if not isinstance(data, dict):
            return None
        head = normalize_entity_name(data.get("head") or data.get("source") or data.get("subject"))
        tail = normalize_entity_name(data.get("tail") or data.get("target") or data.get("object"))
        relation = normalize_relation(data.get("relation") or data.get("predicate"))
        if not head or not tail:
            return None
        return cls(
            head=head,
            relation=relation,
            tail=tail,
            reverse_relation=data.get("reverse_relation") or "",
            attrs=data.get("attrs") if isinstance(data.get("attrs"), dict) else {},
            is_correction=bool(data.get("is_correction") or data.get("is_update")),
            supersedes=data.get("supersedes"),
            confidence=data.get("confidence", 0.5),
            entity_type_head=str(data.get("entity_type_head") or data.get("head_type") or "concept"),
            entity_type_tail=str(data.get("entity_type_tail") or data.get("tail_type") or "concept"),
            valid_at=str(data.get("valid_at") or ""),
            invalid_at="" if is_blank_timestamp(data.get("invalid_at")) else str(data.get("invalid_at")),
            status=str(data.get("status") or "active"),
            source_message_id=data.get("source_message_id"),
            message_id=data.get("message_id"),
        )

    @classmethod
    def from_content(cls, content: str, message: dict[str, Any] | None = None) -> Triple | None:
        if not content:
            return None
        meta: dict[str, Any] = {}
        if META_MARKER in content:
            raw_meta = content.split(META_MARKER, 1)[1].strip()
            try:
                parsed = json.loads(raw_meta)
                if isinstance(parsed, dict):
                    meta = parsed
            except (TypeError, json.JSONDecodeError):
                meta = {}
        if not meta:
            # Fallback: "A --rel--> B"
            m = re.match(r"^(?P<head>.+?)\s*--(?P<rel>[^-]+?)-->\s*(?P<tail>.+?)(?:\s*\[correction\])?$", content.strip().splitlines()[0])
            if not m:
                return None
            meta = {"head": m.group("head"), "relation": m.group("rel"), "tail": m.group("tail")}
        if message:
            meta.setdefault("valid_at", "" if is_blank_timestamp(message.get("valid_at")) else str(message.get("valid_at")))
            meta.setdefault("invalid_at", "" if is_blank_timestamp(message.get("invalid_at")) else str(message.get("invalid_at")))
            meta.setdefault("source_message_id", message.get("source_id"))
            meta.setdefault("message_id", message.get("message_id"))
            # Prefer store-level validity over free-form meta status.
            if not message_is_active(message.get("status")) or not is_blank_timestamp(message.get("invalid_at")):
                meta["status"] = "expired"
            elif "status" not in meta:
                meta["status"] = "active"
        return cls.from_dict(meta)


def parse_triples_from_llm_payload(payload: dict[str, Any] | list | None) -> list[Triple]:
    if not payload:
        return []
    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("triples"), list):
            items = payload["triples"]
        else:
            # tolerate {"triple": [...]} or single triple dict
            if any(k in payload for k in ("head", "relation", "tail", "subject", "predicate", "object")):
                items = [payload]
            else:
                items = payload.get("triple") or []
                if not isinstance(items, list):
                    items = []
    else:
        return []

    triples: list[Triple] = []
    for item in items:
        triple = Triple.from_dict(item) if isinstance(item, dict) else None
        if triple:
            triples.append(triple)
    return triples


def entity_similarity(a: str, b: str) -> float:
    ka, kb = canonical_entity_key(a), canonical_entity_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    if ka in kb or kb in ka:
        shorter, longer = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
        if len(shorter) >= 2 and len(shorter) / max(len(longer), 1) >= 0.6:
            return 0.93
    return SequenceMatcher(None, ka, kb).ratio()


class EntityResolver:
    """String/fuzzy entity resolver over an existing name lexicon."""

    def __init__(self, existing_names: Iterable[str] | None = None, similarity_threshold: float = DEFAULT_SIMILARITY):
        self.similarity_threshold = similarity_threshold
        self._names: dict[str, str] = {}
        for name in existing_names or []:
            self.add(name)

    def add(self, name: str) -> str:
        normalized = normalize_entity_name(name)
        if not normalized:
            return ""
        key = canonical_entity_key(normalized)
        if key not in self._names:
            self._names[key] = normalized
        return self._names[key]

    @property
    def names(self) -> list[str]:
        return sorted(self._names.values(), key=lambda x: x.casefold())

    def resolve(self, name: str) -> str:
        normalized = normalize_entity_name(name)
        if not normalized:
            return ""
        key = canonical_entity_key(normalized)
        if key in self._names:
            return self._names[key]

        best_name = ""
        best_score = 0.0
        for existing_key, existing_name in self._names.items():
            score = entity_similarity(normalized, existing_name)
            if score > best_score:
                best_score = score
                best_name = existing_name
            # exact key already handled; keep loop simple
            _ = existing_key
        if best_name and best_score >= self.similarity_threshold:
            return best_name
        return self.add(normalized)


@dataclass
class GraphWriteResult:
    new_triples: list[Triple]
    expired_message_ids: list[int]
    entity_names: list[str]


def collect_entities_from_triples(triples: Iterable[Triple]) -> list[str]:
    names: dict[str, str] = {}
    for triple in triples:
        for name in (triple.head, triple.tail):
            key = canonical_entity_key(name)
            if key:
                names[key] = normalize_entity_name(name)
    return list(names.values())


def load_triples_from_messages(messages: Iterable[dict[str, Any]]) -> list[Triple]:
    triples: list[Triple] = []
    for message in messages or []:
        if message.get("message_type") not in {TRIPLE_MESSAGE_TYPE, "graph"}:
            # still try parse if content has meta marker
            content = message.get("content") or ""
            if META_MARKER not in content:
                continue
        triple = Triple.from_content(message.get("content") or "", message)
        if triple:
            triples.append(triple)
    return triples


def apply_triples(
    existing_messages: list[dict[str, Any]],
    incoming: list[Triple] | list[dict[str, Any]],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY,
    now: str = "",
) -> GraphWriteResult:
    """Resolve entities and decide which edges to append / expire.

    Rules:
    - Reuse existing entity names via fuzzy match.
    - Identical active edge is skipped (idempotent).
    - Correction / conflicting same-head+relation different tail expires old edge.
    - Never physically deletes; callers expire via invalid_at/status.
    """
    existing_triples = load_triples_from_messages(existing_messages)
    resolver = EntityResolver(collect_entities_from_triples(existing_triples), similarity_threshold=similarity_threshold)

    normalized_incoming: list[Triple] = []
    for item in incoming or []:
        triple = item if isinstance(item, Triple) else Triple.from_dict(item)
        if not triple:
            continue
        triple.head = resolver.resolve(triple.head)
        triple.tail = resolver.resolve(triple.tail)
        if not triple.reverse_relation:
            triple.reverse_relation = reverse_relation_name(triple.relation)
        if now and not triple.valid_at:
            triple.valid_at = now
        normalized_incoming.append(triple)

    active = [t for t in existing_triples if t.status == "active" and is_blank_timestamp(t.invalid_at)]
    expired_ids: list[int] = []
    to_add: list[Triple] = []

    def _expire(old: Triple) -> None:
        if old.message_id is None:
            return
        if old.message_id in expired_ids:
            return
        old.status = "expired"
        if now:
            old.invalid_at = now
        expired_ids.append(int(old.message_id))

    for new in normalized_incoming:
        same_edge = [t for t in active if t.edge_key == new.edge_key]
        if same_edge and not new.is_correction:
            # strengthen confidence only in returned meta; no duplicate insert
            continue

        # same head+relation, different tail => treat as correction/conflict
        conflicts = [t for t in active if canonical_entity_key(t.head) == canonical_entity_key(new.head) and t.relation.casefold() == new.relation.casefold() and canonical_entity_key(t.tail) != canonical_entity_key(new.tail)]
        if new.is_correction or conflicts:
            new.is_correction = True
            for old in conflicts:
                if new.supersedes is None and old.message_id is not None:
                    new.supersedes = str(old.message_id)
                _expire(old)
                active = [t for t in active if t is not old]

        if same_edge and new.is_correction:
            for old in same_edge:
                _expire(old)
                active = [t for t in active if t is not old]

        # skip pure duplicate after correction handling
        if any(t.edge_key == new.edge_key for t in active):
            continue

        to_add.append(new)
        active.append(new)
        resolver.add(new.head)
        resolver.add(new.tail)

    return GraphWriteResult(new_triples=to_add, expired_message_ids=expired_ids, entity_names=resolver.names)


_PROMPT_ATTR_KEYS = ("category", "scope", "source", "stability", "evidence", "sensitivity")
_PERSONAL_PROFILE_CATEGORIES = {
    "identity",
    "background",
    "experience",
    "skill",
    "project",
    "preference",
    "dislike",
    "goal",
    "constraint",
    "work_style",
    "decision",
    "workflow",
    "relationship",
    "correction",
}


def _format_prompt_attrs(attrs: dict[str, Any] | None) -> str:
    if not isinstance(attrs, dict):
        return ""
    selected: dict[str, str] = {}
    for key in _PROMPT_ATTR_KEYS:
        value = attrs.get(key)
        if value is None or value == "":
            continue
        compact = re.sub(r"\s+", " ", str(value)).strip()
        if compact:
            selected[key] = compact[:160]
    if not selected:
        return ""
    return f" attrs={json.dumps(selected, ensure_ascii=False, separators=(',', ':'))}"


def format_subgraph_for_prompt(triples: list[Triple], *, max_edges: int = 32) -> str:
    active = [t for t in triples if t.status == "active" and is_blank_timestamp(t.invalid_at)]
    if not active:
        return ""
    # higher confidence first
    active = sorted(active, key=lambda t: (-t.confidence, t.head.casefold(), t.relation.casefold(), t.tail.casefold()))
    lines = ["[Memory Knowledge Graph]"]
    for triple in active[:max_edges]:
        conf = f"{triple.confidence:.2f}"
        rev = f" (reverse: {triple.reverse_relation})" if triple.reverse_relation else ""
        corr = " [correction]" if triple.is_correction else ""
        attrs = _format_prompt_attrs(triple.attrs)
        lines.append(f"- ({triple.head}) -[{triple.relation}]-> ({triple.tail}){rev}{corr} confidence={conf}{attrs}")
    return "\n".join(lines)


def select_relevant_triples(
    triples: list[Triple],
    *,
    query: str = "",
    seed_entities: Iterable[str] | None = None,
    max_edges: int = 32,
) -> list[Triple]:
    active = [t for t in triples if t.status == "active" and is_blank_timestamp(t.invalid_at)]
    if not active:
        return []

    seeds = {canonical_entity_key(x) for x in (seed_entities or []) if canonical_entity_key(x)}
    q = (query or "").casefold()

    scored: list[tuple[float, Triple]] = []
    for triple in active:
        score = triple.confidence
        head_k = canonical_entity_key(triple.head)
        tail_k = canonical_entity_key(triple.tail)
        if head_k in seeds or tail_k in seeds:
            score += 2.0
        attrs = triple.attrs if isinstance(triple.attrs, dict) else {}
        category = str(attrs.get("category") or "").strip().casefold()
        source = str(attrs.get("source") or "").strip().casefold()
        stability = str(attrs.get("stability") or "").strip().casefold()
        if canonical_entity_key(triple.head) == canonical_entity_key("User") and category in _PERSONAL_PROFILE_CATEGORIES:
            score += 0.35
        if stability == "long_term":
            score += 0.2
        if source in {"explicit", "corrected"}:
            score += 0.15
        elif source == "observed":
            score -= 0.05

        if q:
            attr_blob = " ".join(str(attrs.get(key) or "") for key in _PROMPT_ATTR_KEYS)
            blob = f"{triple.head} {triple.relation} {triple.tail} {attr_blob}".casefold()
            if q in blob:
                score += 1.5
            else:
                # token overlap
                tokens = [t for t in re.split(r"\W+", q) if len(t) >= 2]
                hits = sum(1 for t in tokens if t in blob)
                score += min(1.2, hits * 0.3)
        scored.append((score, triple))

    scored.sort(key=lambda x: (-x[0], x[1].head.casefold()))
    return [t for _, t in scored[:max_edges]]


def extract_seed_entities_from_text(text: str, lexicon: Iterable[str]) -> list[str]:
    if not text:
        return []
    lowered = text.casefold()
    hits: list[str] = []
    for name in sorted({normalize_entity_name(n) for n in lexicon if normalize_entity_name(n)}, key=len, reverse=True):
        if name.casefold() and name.casefold() in lowered:
            hits.append(name)
    return hits


def normalize_llm_triple_dicts(items: Iterable[Any] | dict[str, Any] | None, *, conversation_time: str = "") -> list[dict[str, Any]]:
    """Normalize heterogeneous LLM triple payloads into graph-ready dicts."""
    if isinstance(items, dict) and not any(k in items for k in ("head", "relation", "tail", "subject", "predicate", "object")):
        # full LLM JSON payload, e.g. {"semantic": [...], "triples": [...]}
        candidate_items = items.get("triples") or items.get("triple") or []
        if not isinstance(candidate_items, list):
            candidate_items = []
        # keep payload for fallback parse
        payload_for_fallback: Any = items
    else:
        candidate_items = list(items or []) if not isinstance(items, dict) else [items]
        payload_for_fallback = items if isinstance(items, (dict, list)) else None

    normalized: list[dict[str, Any]] = []
    for item in candidate_items:
        if not isinstance(item, dict):
            continue
        triple = Triple.from_dict(item)
        if not triple:
            continue
        meta = triple.to_meta()
        valid_at = item.get("valid_at") or triple.valid_at or conversation_time
        invalid_at = item.get("invalid_at") or triple.invalid_at or ""
        meta["valid_at"] = "" if is_blank_timestamp(valid_at) else str(valid_at)
        meta["invalid_at"] = "" if is_blank_timestamp(invalid_at) else str(invalid_at)
        normalized.append(meta)
    if normalized:
        return normalized
    for triple in parse_triples_from_llm_payload(payload_for_fallback):
        meta = triple.to_meta()
        meta["valid_at"] = triple.valid_at or conversation_time
        meta["invalid_at"] = triple.invalid_at or ""
        normalized.append(meta)
    return normalized


def materialize_triple_messages(
    write_result: GraphWriteResult,
    *,
    memory_id: str,
    source_message_id: int,
    user_id: str,
    agent_id: str,
    session_id: str,
    now: str,
    id_factory,
) -> list[dict[str, Any]]:
    """Turn GraphWriteResult into memory message rows ready for embed/save."""
    rows: list[dict[str, Any]] = []
    for triple in write_result.new_triples:
        triple.source_message_id = source_message_id
        if not triple.valid_at:
            triple.valid_at = now
        rows.append(
            {
                "message_id": id_factory(),
                "message_type": TRIPLE_MESSAGE_TYPE,
                "source_id": source_message_id,
                "memory_id": memory_id,
                "user_id": user_id or "",
                "agent_id": agent_id,
                "session_id": session_id,
                "content": triple.to_content(),
                "valid_at": triple.valid_at or now,
                "invalid_at": triple.invalid_at or None,
                "forget_at": None,
                "status": True,
            }
        )
    return rows


def build_graph_context_from_messages(
    messages: Iterable[dict[str, Any]],
    *,
    query: str = "",
    top_n: int = 32,
) -> str:
    """Pure retrieval helper: messages -> ranked subgraph prompt block."""
    triples = load_triples_from_messages(messages)
    lexicon = collect_entities_from_triples(triples)
    seeds = extract_seed_entities_from_text(query or "", lexicon)
    selected = select_relevant_triples(triples, query=query or "", seed_entities=seeds, max_edges=int(top_n))
    return format_subgraph_for_prompt(selected, max_edges=int(top_n))


def simulate_memory_graph_turns(
    turns: list[list[dict[str, Any]] | list[Triple]],
    *,
    now_prefix: str = "2026-01-0",
) -> tuple[list[dict[str, Any]], list[str]]:
    """In-memory multi-turn write simulator for smoke/E2E without storage deps.

    Returns (active_and_expired_messages, context_blocks_after_each_turn).
    """
    store: list[dict[str, Any]] = []
    contexts: list[str] = []
    next_id = 1

    def _id() -> int:
        nonlocal next_id
        value = next_id
        next_id += 1
        return value

    for idx, incoming in enumerate(turns, start=1):
        now = f"{now_prefix}{idx} 00:00:00"
        result = apply_triples(store, incoming, now=now)
        if result.expired_message_ids:
            expired = set(result.expired_message_ids)
            for msg in store:
                if msg.get("message_id") in expired:
                    msg["status"] = False
                    msg["invalid_at"] = now
        rows = materialize_triple_messages(
            result,
            memory_id="mem-smoke",
            source_message_id=idx,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            now=now,
            id_factory=_id,
        )
        store.extend(rows)
        contexts.append(build_graph_context_from_messages(store, query="", top_n=32))
    return store, contexts
