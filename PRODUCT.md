# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are operators and builders of a local RAG knowledge system:

- Individual developers and power users who self-host RAGFlow for personal or small-team knowledge work
- Engineers and knowledge workers who need durable memory across chats, not only one-off document Q&A
- Operators who manage knowledge bases, agent workflows, memory stores, and retrieval quality

Primary job: turn documents, conversations, and corrections into reusable knowledge that can be searched, reasoned over, and reused in later sessions.

## Product Purpose

This product is a local, self-hostable RAG + Agent platform based on RAGFlow, extended toward permanent memory and structured knowledge reuse.

It exists to solve two related problems:

1. Document-grounded Q&A with high-quality parsing, chunking, retrieval, and agent orchestration
2. Conversation memory that persists beyond temporary model context, including structured graph-style relations that can be recalled, corrected, and reused

Success means a user can:

- Ingest and manage knowledge bases
- Chat / search with retrieval grounded in local data
- Persist agent memory across sessions
- Retrieve historical memory and structured graph context with the current question
- Correct wrong memory without destroying history (append-only supersede / soft expire)

## Positioning

Not just another chat UI over documents. The differentiated mechanism is a local context engine that combines:

- Deep document understanding and production RAG workflows
- Agent workflows and tools
- Durable memory stores with message-level management
- Incremental memory knowledge-graph triples stored as memory messages (`message_type=triple`), append-only corrections, and shared graph-aware recall (`search_memory_with_graph` / `graph_context`)

The intended product direction is "local Obsidian-like long-term memory + RAGFlow retrieval," without introducing a separate Neo4j system as the product path.

## Operating Context

Typical usage happens on a local or private machine / LAN stack:

- Frontend: React + TypeScript + Vite app in `web/` (dev commonly on port 9222)
- Backend: Python/Quart API and workers, with Go components for parts of the stack
- Runtime services: MySQL/PostgreSQL, Redis, MinIO, Elasticsearch/Infinity/OpenSearch depending on config
- Optional free/local model path: Ollama embeddings and chat models
- User workflows include login, knowledge-base management, document parsing, chat/search, agent configuration, memory management, settings, and admin

Important product surfaces already present in the frontend:

- Home / datasets / document viewing
- Chat and search
- Agents and workflows
- Memory list / memory messages / memory settings
- User settings and admin

## Capabilities and Constraints

Confirmed capabilities:

- Knowledge base creation, document ingestion, parsing, chunking, and retrieval
- Agent workflows and tool-oriented orchestration
- Memory product surface: create/list/update/delete memories; inspect messages; configure memory models/settings
- Memory graph path implemented as ES-backed triples reused through existing memory storage/index machinery
- Shared recall path that can return ordinary memory hits plus sibling `graph_context`
- Multilingual UI with Chinese as a first-class local experience (`web/index.html` is `zh-Hans`)

Confirmed constraints / current state:

- Product is operational-tool UI, not a marketing site; density, scanability, and workflow clarity outrank decorative expression
- Memory graph HTTP end-to-end validation has been partially proven at service level; full real-service E2E remains environment-sensitive (Docker / model endpoints)
- Design system is already present in code (Tailwind tokens, theme variables, logo assets) but no product-level `PRODUCT.md` / `DESIGN.md` existed before this init
- Free/local preference is an operating preference for this fork/use-case: Ollama + Docker base services when possible

Open / undecided:

- Whether the public brand remains pure "RAGFlow" or a local product name for the memory-graph fork
- Exact primary launch surface for the next design pass (memory console vs chat recall UX vs knowledge-graph visualization)
- Accessibility standard beyond ordinary web best practice is not yet product-specified

## Brand Commitments

- Product name currently presented by the UI/docs: **RAGFlow**
- Logo / wordmark assets live under `web/src/assets/` (including `logo-with-text.svg`)
- Existing product language mixes Chinese operational UI copy with English engineering terminology (RAG, Agent, Memory, Dataset)
- Do not invent enterprise customer logos, fake benchmarks, or unverified claims

## Evidence on Hand

Repository evidence:

- Upstream product docs: `README.md`, `README_zh.md`
- Frontend app: `web/`
- Memory backend modules: `memory/services/graph.py`, `memory/services/messages.py`, `memory/services/query.py`
- Memory APIs and joint services under `api/apps/restful_apis/memory_api.py`, `api/apps/services/memory_api_service.py`, `api/db/joint_services/memory_message_service.py`
- Frontend memory surfaces under `web/src/pages/memory/`
- Locale evidence for memory/knowledge-graph concepts in `web/src/locales/zh.ts`
- Theme tokens: `web/src/theme/theme.ts`, `web/tailwind.config.js`, CSS variables used across the app

Absences future design work must not fabricate:

- No independent marketing brand book
- No dedicated published memory-graph customer case studies in-repo
- No finalized visual redesign brief yet

## Product Principles

1. **Operate first.** This is a dense working tool for repeated knowledge tasks, not a campaign landing page.
2. **Memory must land permanently.** Conversation value is incomplete until it becomes durable, searchable, correctable knowledge.
3. **Structure beats raw transcript.** Prefer entities, relations, provenance, and recall context over dumping entire histories into the prompt.
4. **Corrections are history, not deletion.** Prefer append-only supersede / soft-expire over destructive overwrite.
5. **Local trust.** Self-hosting, free/local model options, and transparent provenance matter more than cloud-only polish.

## Accessibility & Inclusion

No formal product-mandated standard was confirmed. Future UI work should preserve keyboard operability, readable contrast, and i18n-safe text overflow, especially for Chinese labels and long memory content. Treat WCAG-minded defaults as a quality floor unless the user later specifies a harder requirement.
