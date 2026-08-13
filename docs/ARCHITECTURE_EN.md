# Ufuq AI Engine — Architecture Specification

**The "Ufuq" (أُفق) Educational Platform — AI Engine & Agent**

| Item | Value |
| --- | --- |
| Version | 1.0.0 |
| Date | August 2026 |
| Target environment | Local (RTX 4060 6GB VRAM / 16GB RAM), cloud later |
| Cost | 100% free in MVP (electricity only) |
| Author | taha deab |

> This document is the English companion to the Arabic architecture specification (`ARCHITECTURE.md`). Both are authoritative; the Arabic version contains the full details, while this document provides the complete structural summary.

---

## 1. Executive Summary

This document is the **official engineering blueprint** for the AI team's scope in the Ufuq Educational Platform project. The platform accepts learning sources (PDF, DOCX, PPTX, websites, YouTube links) and converts them into **Knowledge Maps**, **Learning Paths**, and **Lessons & Assessments**, with a human review loop by the teacher before publishing.

The system is governed by three principles:

1. **Strict layer separation**: Architecture ≠ Technologies ≠ Business Logic. Each layer is independently testable and replaceable.
2. **Deterministic pipelines before the orchestrator**: We build reliable deterministic pipelines first, then make the Agent a smart coordinator above them — not a black box.
3. **One LLM does not do everything**: Parsing, embedding, knowledge extraction, and validation are separated into independent stages to reduce cost and raise quality.

> **Core conceptual correction**: MCP is not a replacement for RAG, and a Knowledge Graph is not a replacement for a Vector DB. These are different components solving different problems:
> - **RAG** answers: "What information is relevant?"
> - **Knowledge Graph** answers: "What is the relationship between this information?"
> - **Agent** decides: "What is the next step to execute?"
> - **MCP** defines: "How does the Agent connect to tools and external systems?"
> - **LLM** performs understanding, reasoning, and generation.

---

## 2. Layer Separation (Architecture / Technology / Business Logic)

### 2.1 Architecture (what the components are and how they communicate)

```text
            User (teacher / student)
                   │
                   ▼
          ┌────────────────┐
          │  Frontend App   │
          └───────┬────────┘
                  │ REST
                  ▼
          ┌────────────────┐
          │  Platform       │
          │  Backend        │  (users, sources, progress...)
          └───────┬────────┘
                  │ AI API Contract
                  ▼
          ┌────────────────┐
          │  Ufuq AI Engine │  ← our scope
          │                 │
          │  ┌───────────┐  │
          │  │  Agent    │  │  orchestrator
          │  └─────┬─────┘  │
          │        ▼        │
          │  ┌───────────┐  │
          │  │  Tools    │  │  registry of deterministic pipelines
          │  └───────────┘  │
          └─────────────────┘
```

The Agent never knows about implementation details — it only sees registered **tools** with JSON Schemas describing their inputs and outputs.

### 2.2 Technologies (swappable, one-line changes)

| Component | Default (local, free) | Cloud upgrade path |
|---|---|---|
| LLM | Ollama (`qwen2.5:7b` / `llama3.2:3b`) | OpenAI (`gpt-4o-mini`) or Gemini (`gemini-2.5-flash`) |
| Embeddings | BGE-M3 (1024-dim, on-device) | OpenAI `text-embedding-3-small` |
| Parsing | Docling (PDF/DOCX/PPTX/XLSX/HTML) | Same (open-source) |
| Vector store | Qdrant (self-hosted) | Qdrant Cloud |
| Graph metadata | PostgreSQL | PostgreSQL |

Switching requires changing only `LLM_PROVIDER` in `.env`. The factory in `app/llm/factory.py` builds the correct provider.

### 2.3 Business Logic (technology-free)

- Concept/relationship extraction rules, duplicate merging, confidence defaults — `app/schemas/concepts.py`
- Graph validation, citation verification, composite confidence — `app/knowledge/validator.py`
- Cycle detection (DFS), Kahn topological sort — `app/algorithms/`
- Learning path rules (module → lesson → assessment ordering) — `app/tools/learning_tools.py`

---

## 3. Agent Architecture (State Machine)

```text
IDLE ──new job──▶ PLANNING ──▶ EXTRACTING ──▶ VALIDATING
                                           ▲          │
                                   fallback│          ▼
                                           │     review_required ──review──▶ GENERATING_PATH
                                           │          │                     │
                                   ┌───────┘          ▼                     ▼
                                   │            REVISING ◀───revise───▶ COMPLETED
                                   │                │
                                   └───────────fail────────▶ FAILED
```

States: `IDLE`, `PLANNING`, `EXTRACTING`, `VALIDATING`, `GENERATING_PATH`, `REVIEW_REQUIRED`, `REVISING`, `COMPLETED`, `FAILED`.

Transition policy (`app/agent/policy.py`):

- On failure with remaining retry budget → same state with backoff (max 3 attempts)
- On persistent failure in a non-final step → `fallback` to the previous stable state
- On persistent failure in the final generation step → `FAILED`
- `review_required` awaits human decision: `approve → COMPLETED`, `revise → REVISING`, `reject → FAILED`

---

## 4. Tool Registry (Agent tools)

The Agent sees exactly these tools. Each has a JSON Schema for inputs/outputs.

| Tool | Category | Inputs | Outputs |
|---|---|---|---|
| `ingest_document` | document | file_path, source_id | parsed chunks with structure metadata |
| `ingest_url` | document | url, source_id | parsed chunks |
| `search_knowledge` | rag | query, source_id?, top_k | ranked chunks + hybrid scores + citations |
| `extract_concepts` | knowledge | chunks | concepts + relationships (validated schema) |
| `validate_extraction` | knowledge | extraction payload | accepted / rejected + error list |
| `build_graph` | knowledge | concepts, relationships | validated KnowledgeGraph with metadata |
| `generate_module` | learning | graph, target | LearningModule |
| `generate_lesson` | learning | concepts | Lesson with citations |
| `generate_assessment` | learning | concepts | Assessment |
| `generate_path` | learning | source_id | LearningPath |
| `get_concept` | knowledge | concept_id | Concept |
| `recommend_course` | learning | topic, level | module recommendations |

---

## 5. RAG Pipeline

```text
        Query
      ┌────┴────┐
      ▼         ▼
  Vector    Keyword
  Search    (TF/BM25)
      └────┬────┘
           ▼
   Reciprocal Rank Fusion (k=60, weights [2.0, 1.0])
           ▼
   CrossEncoder Reranker (optional)
           ▼
   Top-k Chunks + Scores + Citations
```

Design decisions: vector search captures semantic similarity; keyword search captures exact matches (concept names, terms); RRF fuses both without score calibration; reranker is optional for 6GB VRAM.

---

## 6. Knowledge Graph Schema

Nodes carry: `id`, `name`, `type` (concept|definition|skill|topic|method|tool|example|assessment), `definition`, `source_chunk_ids`, `confidence`, `metadata`.

Edges carry: `source_concept_id`, `relation` (prerequisite_of|part_of|type_of|related_to|depends_on|example_of|teaches|assesses|generalization_of), `target_concept_id`, `evidence_chunk_ids`, `confidence`.

**Deterministic validation** before persistence:

1. JSON Schema validation of LLM output
2. Citation existence check (every referenced chunk_id must exist)
3. Citation accuracy check (claim must be supported by chunk text, threshold 0.6)
4. Confidence threshold (edges < 0.5 rejected)
5. Cycle detection (DFS) — prerequisites must be acyclic
6. Kahn topological sort — produces learning order
7. Composite confidence = weighted mean of extraction + citation + graph confidence

---

## 7. Prompt Architecture (in `prompts/`, Arabic templates)

| Template | Purpose |
|---|---|
| `extract_concepts.md` | Extract concepts with definitions and chunk references |
| `extract_relationships.md` | Extract typed relationships with evidence |
| `extract_prerequisites.md` | Infer prerequisite chains |
| `chunk_summarize.md` | Summarize a chunk |
| `generate_module.md` | Generate a learning module |
| `generate_lesson.md` | Generate a lesson with citations |
| `generate_assessment.md` | Generate MCQ/open assessments |
| `validate_concepts.md` | Cross-check extracted concepts against source text |

All prompts enforce structured JSON output and Arabic-first answers (Arabic content, English technical terms).

---

## 8. Local Model Strategy (RTX 4060 6GB)

| Task | Model | Approx VRAM |
|---|---|---|
| Main generation | qwen2.5:7b | ~6GB |
| Light tasks (summary/verify) | llama3.2:3b | ~3GB |
| Embeddings | BGE-M3 (1024-dim) | ~2GB, loaded/unloaded GPU-aware |

The embedding service unloads from GPU when idle so the LLM always fits. If the GPU is fully occupied, the system falls back to CPU with a warning.

---

## 9. FastAPI Contract

```text
POST /sources/upload      → upload document (multipart)
POST /sources/url         → index a URL
GET  /sources/{id}        → source metadata

POST /jobs                → create Agent job (process_source | generate_path | refresh)
GET  /jobs/{id}           → job status
POST /jobs/{id}/review    → human review (approve | revise | reject)

POST /rag/search          → hybrid RAG search + citations + scores
GET  /knowledge/{source}  → full knowledge graph
GET  /learning/{source}/path → generated learning path
GET  /mcp/tools           → available MCP tools
GET  /health              → health (provider, local_mode, ci_mode, ollama)
GET  /docs                → interactive Swagger UI
```

---

## 10. MCP Server

Four tools exposed to external AI agents (Claude Desktop, Cursor, ...):

- `search_ufuq_knowledge` — hybrid search across indexed sources
- `get_learning_path` — retrieve a generated learning path
- `get_concept` — retrieve a concept node with definition and context
- `recommend_course` — recommend modules for a topic/level

---

## 11. Testing Strategy

| Suite | Scope |
|---|---|
| `tests/unit/test_algorithms.py` | Cycle detection, Kahn sort (deterministic, no LLM) |
| `tests/unit/test_schemas.py` | Pydantic validation, JSON Schema rejection cases |
| `tests/unit/test_agent_policy.py` | State transitions, retry/fallback policy |
| `tests/unit/test_validator.py` | Citation checks, composite confidence |
| `tests/unit/test_rag.py` | RRF fusion, keyword search, tokenization |
| `tests/unit/test_ingestion.py` | Semantic chunking, structure preservation |
| `tests/unit/test_knowledge.py` | Graph builder, tool registry validation |
| `tests/unit/test_llm.py` | Provider interface, factory |
| `tests/integration_test.py` | Full FastAPI contract |

CI runs all suites on Python 3.10/3.11/3.12 (`/.github/workflows/ci.yml`).

---

*Full Arabic specification: `docs/ARCHITECTURE.md`*
