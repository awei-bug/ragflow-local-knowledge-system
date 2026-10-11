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

from typing import ClassVar

from common.constants import MemoryType
from common.time_utils import current_timestamp


class PromptAssembler:
    SYSTEM_BASE_TEMPLATE = """**Durable Personal Memory Extraction Specialist**
You analyze conversations to build an accurate, correctable, long-term memory of the user.
The goal is not to save everything. Save only information that will materially improve future assistance.

**PERSONAL MEMORY CONTRACT:**
1. Treat the human speaker in `User Input` as the canonical entity `User`.
2. The agent response is context, not evidence about the user. Never turn an agent suggestion, guess, drafted text, or compliment into a user fact unless the user explicitly confirmed it.
3. Separate explicit facts from observations and inferences. Store explicit statements and unambiguous completed actions. Do not store speculative personality judgments, diagnoses, or inferred private attributes.
4. Prioritize durable knowledge: identity, background, abilities, projects, preferences, dislikes, goals, constraints, work style, decision criteria, recurring problems, validated workflows, and corrections.
5. Ignore greetings, one-off formatting requests, temporary task state, tool logs, chain-of-thought, copied third-party text that does not describe the user, and information already contradicted in the same conversation.
6. Never store passwords, API keys, authentication tokens, recovery codes, private keys, or other secrets.
7. Preserve uncertainty and scope. A preference for one project must not become a global preference. Lower confidence for indirect observations.
8. When the user corrects prior information, emit the corrected edge with `is_correction=true`; do not preserve both claims as simultaneously active.
9. Personal learning is passive and gradual. Do not treat missing profile fields as information that must be completed; extract only what naturally appears while the user is pursuing real tasks.

{type_specific_instructions}

**OUTPUT REQUIREMENTS:**
1. Output MUST be valid JSON
2. Follow the specified output format exactly
3. Each extracted item MUST have: content, valid_at, invalid_at
4. Timestamps in {timestamp_format} format
5. Only extract memory types specified above
6. Maximum {max_items} items per type
7. ALWAYS include a "triples" array for structured knowledge graph edges, even when empty
8. Prefer reusing names from the provided entity lexicon when they refer to the same concept
9. Do not fabricate missing details or make a statement stronger than the conversation supports
"""

    TYPE_INSTRUCTIONS: ClassVar[dict[str, str]] = {
        MemoryType.SEMANTIC.name.lower(): """
        **EXTRACT SEMANTIC KNOWLEDGE:**
        - Durable facts and relationships, including stable user profile knowledge
        - User background, demonstrated abilities, owned projects, explicit preferences, goals, constraints, and decision criteria
        - General facts are allowed when they are likely to matter in future conversations
        - Phrase personal facts with explicit scope, for example: "For the RAGFlow project, User prefers official framework patterns over shortcuts"

        **Timestamp Rules for Semantic Knowledge:**
        - valid_at: When the fact became true or was explicitly confirmed
        - invalid_at: When it becomes false, is superseded, or empty if still current
        - Default: valid_at = conversation time, invalid_at = "" for current durable facts
        """,
        MemoryType.EPISODIC.name.lower(): """
        **EXTRACT EPISODIC KNOWLEDGE:**
        - Specific experiences, events, personal stories
        - Time-bound, person-specific, contextual
        - Examples: "Yesterday I fixed the bug", "User reported issue last week"

        **Timestamp Rules for Episodic Knowledge:**
        - valid_at: Event start/occurrence time
        - invalid_at: Event end time or empty if instantaneous
        - Extract explicit times: "at 3 PM", "last Monday", "from X to Y"
        """,
        MemoryType.PROCEDURAL.name.lower(): """
        **EXTRACT PROCEDURAL KNOWLEDGE:**
        - Processes, methods, step-by-step instructions
        - Goal-oriented, actionable, often includes conditions
        - Examples: "To reset password, click...", "Debugging steps: 1)..."

        **Timestamp Rules for Procedural Knowledge:**
        - valid_at: When procedure becomes valid/effective
        - invalid_at: When it expires/becomes obsolete or empty if current
        - For version-specific: use release dates
        - For best practices: invalid_at = ""
        """,
    }

    OUTPUT_TEMPLATES: ClassVar[dict[str, str]] = {
        MemoryType.SEMANTIC.name.lower(): """
        "semantic": [
            {
                "content": "Clear factual statement",
                "valid_at": "timestamp or empty",
                "invalid_at": "timestamp or empty"
            }
        ]
        """,
        MemoryType.EPISODIC.name.lower(): """
        "episodic": [
            {
                "content": "Narrative event description",
                "valid_at": "event start timestamp",
                "invalid_at": "event end timestamp or empty"
            }
        ]
        """,
        MemoryType.PROCEDURAL.name.lower(): """
        "procedural": [
            {
                "content": "Actionable instructions",
                "valid_at": "procedure effective timestamp",
                "invalid_at": "procedure expiration timestamp or empty"
            }
        ]
        """,
    }

    TRIPLE_INSTRUCTIONS = """
        **EXTRACT KNOWLEDGE GRAPH TRIPLES:**
        - Convert durable facts into subject-predicate-object edges
        - Normalize entity names; reuse lexicon names when they match
        - Use `User` as the head for the user's profile, preference, goal, constraint, ability, habit, and ownership edges
        - relation should be short snake_case or concise Chinese predicate
        - Mark is_correction=true when the conversation corrects earlier knowledge
        - confidence in [0,1]: explicit statement 0.85-1.0, unambiguous observed action 0.65-0.8; do not emit weak speculation
        - attrs should use only useful keys from: category, scope, source, stability, evidence, sensitivity
        - category should be one of: identity, background, experience, skill, project, preference, dislike, goal, constraint, work_style, decision, workflow, relationship, correction, other
        - source should be explicit, observed, or corrected; stability should be long_term, contextual, or temporary
        - scope must be specific when the statement is not globally true
        - sensitivity may be normal or sensitive; never emit secret credentials
        """

    TRIPLE_OUTPUT_TEMPLATE = """
        "triples": [
            {
                "head": "Subject entity",
                "relation": "predicate",
                "tail": "Object entity",
                "reverse_relation": "reverse_predicate",
                "attrs": {
                    "category": "preference|goal|constraint|skill|project|work_style|decision|other",
                    "scope": "global or specific context",
                    "source": "explicit|observed|corrected",
                    "stability": "long_term|contextual|temporary",
                    "evidence": "short supporting phrase",
                    "sensitivity": "normal|sensitive"
                },
                "is_correction": false,
                "confidence": 0.7,
                "entity_type_head": "concept|person|system|rule|event",
                "entity_type_tail": "concept|person|system|rule|event",
                "valid_at": "timestamp or empty",
                "invalid_at": "timestamp or empty"
            }
        ]
        """

    BASE_USER_PROMPT = """
**CONVERSATION:**
{conversation}

**CONVERSATION TIME:** {conversation_time}
**CURRENT TIME:** {current_time}

**ENTITY LEXICON (reuse these names when possible):**
{entity_lexicon}
"""

    @classmethod
    def assemble_system_prompt(cls, config: dict) -> str:
        types_to_extract = cls._get_types_to_extract(config["memory_type"])

        type_instructions = cls._generate_type_instructions(types_to_extract)

        output_format = cls._generate_output_format(types_to_extract)

        full_prompt = cls.SYSTEM_BASE_TEMPLATE.format(
            type_specific_instructions=type_instructions, timestamp_format=config.get("timestamp_format", "ISO 8601"), max_items=config.get("max_items_per_type", 5)
        )

        full_prompt += f"\n**REQUIRED OUTPUT FORMAT (JSON):**\n```json\n{{\n{output_format}\n}}\n```\n"

        examples = cls._generate_examples(types_to_extract)
        if examples:
            full_prompt += f"\n**EXAMPLES:**\n{examples}\n"

        return full_prompt

    @staticmethod
    def _get_types_to_extract(requested_types: list[str]) -> list[str]:
        types = set()
        for rt in requested_types:
            if rt in [e.name.lower() for e in MemoryType] and rt != MemoryType.RAW.name.lower():
                types.add(rt)
        return list(types)

    @classmethod
    def _generate_type_instructions(cls, types_to_extract: list[str]) -> str:
        target_types = set(types_to_extract)
        instructions = [cls.TYPE_INSTRUCTIONS[mt] for mt in target_types]
        # Always extract triples whenever any non-raw memory type is requested.
        if target_types:
            instructions.append(cls.TRIPLE_INSTRUCTIONS)
        return "\n".join(instructions)

    @classmethod
    def _generate_output_format(cls, types_to_extract: list[str]) -> str:
        target_types = set(types_to_extract)
        output_parts = [cls.OUTPUT_TEMPLATES[mt] for mt in target_types]
        if target_types:
            output_parts.append(cls.TRIPLE_OUTPUT_TEMPLATE)
        return ",\n".join(output_parts)

    @staticmethod
    def _generate_examples(types_to_extract: list[str]) -> str:
        examples = []

        if MemoryType.SEMANTIC.name.lower() in types_to_extract:
            examples.append("""
            **Semantic Example:**
            Input: "Python lists are mutable and support various operations."
            Output: {"semantic": [{"content": "Python lists are mutable data structures", "valid_at": "2024-01-15T10:00:00", "invalid_at": ""}]}
            """)

        if MemoryType.EPISODIC.name.lower() in types_to_extract:
            examples.append("""
            **Episodic Example:**
            Input: "I deployed the new feature yesterday afternoon."
            Output: {"episodic": [{"content": "User deployed new feature", "valid_at": "2024-01-14T14:00:00", "invalid_at": "2024-01-14T18:00:00"}]}
            """)

        if MemoryType.PROCEDURAL.name.lower() in types_to_extract:
            examples.append("""
            **Procedural Example:**
            Input: "To debug API errors: 1) Check logs 2) Verify endpoints 3) Test connectivity."
            Output: {"procedural": [{"content": "API error debugging: 1. Check logs 2. Verify endpoints 3. Test connectivity", "valid_at": "2024-01-15T10:00:00", "invalid_at": ""}]}
            """)

        if types_to_extract:
            examples.append("""
            **Triple Example:**
            Input: "User prefers official framework patterns over shortcuts in the RAGFlow project."
            Output: {"triples": [{"head": "User", "relation": "prefers", "tail": "official framework patterns", "reverse_relation": "preferred_by", "attrs": {"category": "work_style", "scope": "RAGFlow project", "source": "explicit", "stability": "long_term", "evidence": "User explicitly rejected shortcuts", "sensitivity": "normal"}, "is_correction": false, "confidence": 0.95, "entity_type_head": "person", "entity_type_tail": "rule", "valid_at": "2024-01-15T10:00:00", "invalid_at": ""}]}
            """)

        return "\n".join(examples)

    @classmethod
    def assemble_user_prompt(
        cls,
        conversation: str,
        conversation_time: str | None = None,
        current_time: str | None = None,
        entity_lexicon: list[str] | None = None,
    ) -> str:
        lexicon = entity_lexicon or []
        lexicon_text = ", ".join(lexicon[:80]) if lexicon else "(empty)"
        return cls.BASE_USER_PROMPT.format(
            conversation=conversation,
            conversation_time=conversation_time or "Not specified",
            current_time=current_time or current_timestamp(),
            entity_lexicon=lexicon_text,
        )

    @classmethod
    def get_raw_user_prompt(cls):
        return cls.BASE_USER_PROMPT
