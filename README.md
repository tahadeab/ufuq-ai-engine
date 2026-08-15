# Ufuq AI Engine

**Ufuq Educational Roadmap Engine** — Converts documents and learning sources into auditable Knowledge Maps and personalized Learning Paths.

**محرك أُفق التعليمي** — يحوّل المستندات والمصادر إلى خرائط معرفية ومسارات تعلم قابلة للمراجعة والتدقيق.

| Field / البند | Value / القيمة |
|---|---|
| Version / الإصدار | 0.1.0 |
| Author / المؤلف | taha deab |
| License / الرخصة | MIT |
| Default Mode / الوضع الافتراضي | 100% Local & Free (Ollama + BGE-M3 + Docling + Qdrant) |
| Hardware / الأجهزة | RTX 4060 6GB VRAM + 16GB RAM (or higher) |
| Language / اللغة | Python 3.10+ |

---

## Overview / نظرة عامة

The engine runs as a standalone FastAPI service that accepts documents (PDF / DOCX / PPTX / XLSX / HTML) or URLs, then executes a full Agent loop:

يعمل المحرك كمخدم FastAPI مستقل يستقبل مستندات أو روابط، ثم ينفّذ حلقة Agent كاملة:

```text
Document / مستند → Ingestion (Docling) → Semantic Chunking
                 → Embeddings (BGE-M3) → Vector Store (Qdrant)
                 → Knowledge Extraction (LLM + JSON Schema validation)
                 → Knowledge Graph (Cycle Detection + Topological Sort)
                 → Learning Path / Lessons / Assessments
```

All LLM outputs undergo **strict JSON Schema validation**, and every knowledge graph passes through **deterministic algorithmic verification** (cycle detection + Kahn topological sort + citation verification) before persistence.

كل مخرجات LLM تخضع لـ**تحقق JSON Schema صارم**، وكل رسم معرفي يمر عبر**تحقق خوارزمي حتمي** (كشف الدورات + الترتيب الطوبولوجي Kahn + التحقق من الاقتباسات) قبل الحفظ.

## Architecture / البنية المعمارية

The project strictly separates Architecture, Technologies, and Business Logic:

يفصل المشروع بوضوح بين البنية والتقنيات ومنطق العمل:

| Layer / الطبقة | Description / الوصف |
|---|---|
| **Architecture** | Agent State Machine, transition policy, Agent tools |
| **Technologies** | LLM Providers (Ollama/OpenAI/Gemini), BGE-M3, Docling, Qdrant — swappable via one line in `.env` |
| **Business Logic** | Knowledge extraction, graph building, path generation, deterministic validation |

- `app/llm/` — Abstract layer; switching local ↔ cloud requires only changing `LLM_PROVIDER` in `.env`.
- `app/ingestion/` — Document parsing via Docling with a `SemanticChunker` that preserves structure (chapter/section/topic/page).
- `app/rag/` — Hybrid search (Vector + Keyword + RRF Fusion + optional CrossEncoder Reranker) with citations.
- `app/knowledge/` — Concept/relationship extraction, knowledge graph builder, repository (PostgreSQL/In-memory).
- `app/algorithms/` — Deterministic Cycle Detection (DFS) and Topological Sort (Kahn).
- `app/agent/` — Orchestrator with a step-by-step execution loop and retry/fallback recovery.
- `app/tools/` — Unified tool registry (Document / RAG / Knowledge / Learning).
- `app/mcp_server/` — MCP server with `search_ufuq_knowledge`, `get_learning_path`, `get_concept`, `recommend_course`.
- `prompts/` — 8 Arabic prompt templates for extraction, validation, and generation.

## API Contract / واجهة البرمجة

```text
POST /sources/upload      → Upload a document (multipart)      / رفع مستند
POST /sources/url         → Index a URL                        / فهرسة رابط
GET  /sources/{id}        → Indexed source metadata            / بيانات مصدر مفهرس

POST /jobs                → Create an Agent job (process_source | generate_path | refresh)
GET  /jobs/{id}           → Job status (queued|processing|review_required|completed|failed)
POST /jobs/{id}/review    → Human review (approve | revise | reject)

POST /rag/search          → Hybrid RAG search with citations   / بحث RAG هجين
GET  /knowledge/{source}  → Full knowledge graph               / الرسم المعرفي
GET  /learning/{source}/path → Generated learning path         / مسار التعلم
GET  /learning/{source}/review → Evidence and quality review    / مراجعة الأدلة والجودة
GET  /learning/{source}/versions → Roadmap version history       / إصدارات المسار
GET  /learning/{source}/export.json|md|pdf → Export formats      / التصدير
GET  /mcp/tools           → Available MCP tools                / أدوات MCP
GET  /health              → Health check                       / فحص الصحة
GET  /docs                → Interactive Swagger UI             / واجهة توثيق تفاعلية
```

## Quality, Review and Learning Features / الجودة والمراجعة والميزات التعليمية

Every generated path includes deterministic quality signals for citation coverage, concept coverage, graph validity, unsupported claims, and review status. Each module exposes its source citations and learning objectives in the bilingual dashboard. The path also includes estimated hours and an initial weekly plan, while every regeneration is retained as a version in the in-memory job store.

تتضمن كل خارطة مؤشرات حتمية لجودة الاستشهادات وتغطية المفاهيم وصحة الرسم والادعاءات غير المدعومة وحالة المراجعة. وتعرض الواجهة كل وحدة وأهدافها وأدلتها الأصلية، إضافة إلى مدة التعلم التقديرية والخطة الأسبوعية الأولية، مع حفظ الإصدارات السابقة أثناء تشغيل الخدمة.

## Local Setup / التشغيل المحلي (Docker)

```bash
# 1. Install Ollama from https://ollama.com and pull models:
ollama pull qwen2.5:7b
ollama pull llama3.2:3b

# 2. Set up environment
cp .env.example .env          # LLM_PROVIDER=ollama is the default

# 3. Run
docker compose -f docker/docker-compose.yml up -d   # PostgreSQL + Qdrant
make run-local                 # or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Running without Docker is also supported (see `docs/LOCAL_SETUP_GUIDE.md`):

التشغيل بدون Docker متاح أيضاً:

```bash
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Cloud Mode (Future) / التشغيل السحابي (مستقبلاً)

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
# or
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

No code changes needed — the factory builds the provider from settings only.

لا يلزم أي تغيير في الكود.

## Testing / الاختبارات

```bash
pytest -q                              # Full suite
pytest tests/unit -v                    # Unit tests (algorithms, schemas, Agent, RAG, tools, quality)
python tests/integration_test.py        # Full FastAPI integration tests
```

Algorithm tests are deterministic and require no LLM — they run instantly.

## Project Structure / هيكل المشروع

```text
ufuq-ai-engine/
├── app/
│   ├── api/            routes_jobs|sources|rag|knowledge|exports.py
│   ├── llm/            base | ollama_provider | openai_provider | gemini_provider | factory | prompts.py
│   ├── ingestion/      docling_parser.py | chunker.py
│   ├── embeddings/     model.py | service.py (GPU-aware loading/unloading)
│   ├── vectorstore/    qdrant_store.py
│   ├── schemas/        concepts | graph | learning_path | jobs.py
│   ├── rag/            hybrid_search | retriever | reranker.py
│   ├── knowledge/      extractor | graph_builder | graph_store | validator.py
│   ├── algorithms/     cycle_detection | topological_sort.py
│   ├── agent/          state | policy | orchestrator.py
│   ├── tools/          registry | document_tools | rag_tools | knowledge_tools | learning_tools.py
│   ├── mcp_server/     server.py
│   ├── services/       job_store.py
│   ├── config.py | main.py
│   └── storage/        sources/ (uploaded files)
├── prompts/            8 Arabic prompt templates
├── tests/              unit/ + integration_test.py
├── docker/             Dockerfile + docker-compose.yml (PostgreSQL + Qdrant)
├── docs/               ARCHITECTURE.md + LOCAL_SETUP_GUIDE.md
├── .env.example  Makefile  requirements.txt  LICENSE
└── README.md
```

## Model Strategy by VRAM (RTX 4060 6GB) / استراتيجية النماذج حسب الذاكرة

| Task / المهمة | Model / النموذج | VRAM (approx) |
|---|---|---|
| Main generation / التوليد الرئيسي | qwen2.5:7b | ~6GB |
| Light tasks (summary/verify) / المهام الخفيفة | llama3.2:3b | ~3GB |
| Embeddings | BGE-M3 (1024-dim) | ~2GB (GPU-aware load/unload) |

The system automatically unloads the embedding model from GPU when idle to avoid memory overflow.

---

**Full documentation / الوثائق الكاملة:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
