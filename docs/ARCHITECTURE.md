# وثيقة مواصفات هندسة Ufuq AI Engine

**منصة أُفق التعليمية — محرك الذكاء الاصطناعي والـAgent**

| البند | القيمة |
| --- | --- |
| الإصدار | 1.0.0 |
| التاريخ | أغسطس 2026 |
| البيئة المستهدفة | محلي (RTX 4060 6GB VRAM / 16GB RAM) ثم سحابة مستقبلاً |
| التكلفة | مجانية 100% في نسخة MVP (تكلفة كهرباء فقط) |
| author | taha deab |

---

## 1. الملخص التنفيذي

هذا المستند هو **المخطط الهندسي الرسمي** للجزء المسؤول عنه فريق الـAI في مشروع منصة أُفق التعليمية. المنصة تستقبل مصادر تعليمية (PDF، DOCX، PPTX، مواقع ويب، روابط يوتيوب) وتحولها إلى **خرائط معرفية (Knowledge Maps)** و**مسارات تعلم (Learning Paths)** و**دروس واختبارات** مقترحة، مع آلية مراجعة بشرية للمدرس قبل النشر.

النظام مبني على ثلاثة مبادئ حاكمة:

1. **الفصل الصارم بين الطبقات**: Architecture (البنية) ≠ Technologies (التقنيات) ≠ Business Logic (منطق العمل). كل طبقة قابلة للاختبار والاستبدال بشكل مستقل.
2. **الأدوات الحتمية قبل عامل التنسيق**: نُبني الـPipelines الحتمية (Deterministic) الموثوقة أولاً، ثم نجعل الـAgent منسقاً ذكياً فوقها، وليس صندوقاً أسود.
3. **LLM واحد لا يفعل كل شيء**: التخليط (Parsing)، التضمين (Embedding)، الاستخراج المعرفي، والتحقق تُفصل في مراحل مستقلة لتقليل التكلفة ورفع الجودة.

> **التصحيح المفاهيمي الجوهري**: لا نستخدم MCP بدلاً من RAG، ولا Knowledge Graph بدلاً من Vector DB. هذه مكونات مختلفة تحل مشاكل مختلفة:
> - **RAG** يجيب: "ما المعلومات ذات الصلة؟"
> - **Knowledge Graph** يجيب: "ما العلاقة بين هذه المعلومات؟"
> - **Agent** يقرر: "ما الخطوة التالية التي يجب تنفيذها؟"
> - **MCP** يحدد: "كيف يتصل الـAgent بالأدوات والأنظمة الخارجية؟"
> - **LLM** يقوم بالفهم والاستدلال والتوليد.

---

## 2. الفصل بين الطبقات الثلاث (Architecture / Technology / Business Logic)

قبل أي كود، نثبت تعريف كل طبقة وحدودها:

### 2.1 Architecture — البنية (ما هي المكونات وكيف تتواصل)

هي الرسم الذي يصف المكونات ومسار البيانات بينها، **دون ذكر أي اسم تقنية**:

```text
                    المستخدم (مدرس/طالب)
                           │
                           ▼
                 ┌─────────────────────┐
                 │   واجهة التطبيق      │  (Frontend)
                 └──────────┬──────────┘
                            │ REST
                            ▼
                 ┌─────────────────────┐
                 │    Backend المنصة    │  (إدارة المستخدمين،
                 └──────────┬──────────┘   المصادر، التقدم...)
                            │ AI API Contract
                            ▼
                 ┌─────────────────────┐
                 │    Ufuq AI Engine    │  ← هذا هو نطاقنا
                 │                      │
                 │  ┌────────────────┐  │
                 │  │ Agent (منسق)   │  │
                 │  └───────┬────────┘  │
                 │  ┌───────▼────────┐  │
                 │  │   طبقة الأدوات   │  │
                 │  └──┬────┬────┬───┘  │
                 │     ▼    ▼    ▼      │
                 │  Ingestion  RAG  Knowledge  Learning
                 └─────────────────────┘
```

**قاعدة ذهبية**: أي شخص جديد يقرأ هذا الرسم يجب أن يفهم النظام **دون معرفة Python أو Ollama أو Qdrant**.

### 2.2 Technology — التقنيات (ما هي الأدوات التي تنفذ المكونات)

هي خريطة **التنفيذ الفعلي** لكل مكون معماري، وتكون قابلة للتبديل عبر Configuration:

| المكون المعماري | التقنية في MVP | البديل عند التوسع |
| --- | --- | --- |
| LLM (العقل) | Ollama + Qwen3 8B محلي | OpenAI API / Gemini API |
| Embeddings | BGE-M3 محلي (CPU/GPU) | OpenAI embeddings / Gemini embeddings |
| Ingestion (التخليط) | Docling (يدعم PDF/DOCX/PPTX/XLSX/HTML) | Docling يبقى (مجاني ومفتوح المصدر) |
| Vector DB | Qdrant (Docker) | Qdrant Cloud / Milvus |
| Relational DB (للـAI metadata) | PostgreSQL + pgvector | نفس الشيء |
| Knowledge Graph | جداول PostgreSQL أولاً | Neo4j Community عند الحاجة لاستعلامات معقدة |
| API Framework | FastAPI | FastAPI يبقى |
| Agent | Python (Custom Orchestrator) | LangGraph عند الحاجة لتعقيد أكبر |
| Containerization | Docker Compose | Kubernetes |
| MCP | مكتبة mcp (Python SDK) | b2b |

### 2.3 Business Logic — منطق العمل (قواعد المنصة)

هي القواعد التي لا تتغير بتغير التقنيات:

- كل مسار تعلم **يجب** أن يمر بمراجعة بشرية (موافقة/تعديل/رفض لكل عنصر).
- كل معلومة في المخرجات **يجب** أن تكون مسندة بمقطع (Citation) من المصدر الأصلي.
- العلاقات ذات الاتجاه `prerequisite_of` **يجب** أن تكون خالية من الدورات (Cycles).
- استخراج JSON **يجب** أن يخضع لمخطط JSON Schema صارم (Structured Outputs).
- المدرس يرفع مصدراً → النظام يقترح → المدرس يقرر. القرار النهائي دائماً بشري.

**لماذا هذا الفصل مهم؟** لأن الكود الذي يخلط الطبقات (مثل استدعاء `ollama.chat()` مباشرة داخل دالة منطق عمل) يفشل عند: (1) التبديل من Ollama إلى Gemini، (2) كتابة اختبارات Unit دون تشغيل نماذج، (3) توسع المشروع وصعوبة الصيانة. لذلك نطبق قاعدة: **لا يستدعي منطق العمل أي API خارجي مباشرة؛ يستدعي واجهة مجردة فقط**.

---

## 3. Agent State Machine (آلة حالات الـAgent)

الـAgent الرئيسي هو **Ufuq Learning Architect Agent**، وهو Single Orchestrator فوق أدوات متخصصة (لا نستخدم عدة Agents مستقلة في MVP لتجنب تعقيد تعدد النماذج على جهاز 6GB VRAM).

```text
              ┌──────────────┐
              │   IDLE       │ ← بانتظار مهمة جديدة
              └──────┬───────┘
                     │ task received
                     ▼
              ┌──────────────┐
              │  PLANNING    │ ← تحليل المهمة وبناء خطة الخطوات
              └──────┬───────┘
                     │
        ┌────────────▼────────────┐
        │  EXECUTING (loop)       │ ← تنفيذ خطوة واحدة من الخطة
        │                         │
        │  select next tool       │
        │  call tool              │
        │  observe result         │ ◄──┐
        │  validate result        │    │
        └────────────┬────────────┘    │
                     │ failure         │ retry (≤3)
                     ▼                 │
              ┌──────────────┐         │
              │  RECOVERING  │ ────────┘
              │ (إصلاح/تجربة  │
              │  بديل)       │
              └──────┬───────┘
                     │ success
                     ▼
              ┌──────────────┐
              │  COMPLETED   │ ← إرجاع نتيجة منظمة
              └──────────────┘
                     │
              ┌──────────────┐
              │ FAILED       │ ← فشل حاسم + تقرير خطأ
              └──────────────┘
```

**قواعد الانتقال**:

1. في حالة `PLANNING` يبني القائمة: [تحليل المصدر ← بنية المستند ← استخراج المفاهيم ← استخراج العلاقات ← التحقق من المتطلبات ← بناء الرسم ← اكتشاف الدورات ← الترتيب الطوبولوجي ← توليد الوحدات والدروس والاختبارات ← إسناد الاقتباسات ← إرجاع مسودة للمراجعة].
2. في حالة `EXECUTING` ينفذ **خطوة واحدة** لكل دورة، ثم يعيد التقييم (لا ينفذ كل الخطة دفعة واحدة).
3. الحد الأقصى لمحاولات retry لكل أداة هو 3، بعدها ينتقل إلى `RECOVERING` ثم `FAILED` مع تقرير.
4. `COMPLETED` يعني دائماً `status = review_required` (القرار النهائي للمدرس).

### Agent Memory / State (نموذج JSON)

```json
{
  "task_id": "job-abc123",
  "state": "EXECUTING",
  "plan": [
    {"step": 1, "tool": "parse_document", "status": "done"},
    {"step": 2, "tool": "extract_structure", "status": "done"},
    {"step": 3, "tool": "extract_concepts", "status": "in_progress"}
  ],
  "context": {
    "source_id": "src-42",
    "document_structure": {...},
    "extracted_chunks": 142,
    "candidate_concepts": 67,
    "validation_report": {...}
  },
  "retries_remaining": 2,
  "created_at": "2026-08-13T10:00:00Z",
  "updated_at": "2026-08-13T10:05:23Z"
}
```

---

## 4. Tool Registry — سجل الأدوات الكامل

الـAgent لا يتعامل مباشرة مع Qdrant أو PostgreSQL. يتعامل فقط مع **طبقة الأدوات**، والطبقة بدورها تتعامل مع الـRepositories.

### 4.1 Document Tools

| الأداة | المدخلات | المخرجات |
| --- | --- | --- |
| `get_source(source_id)` | source_id | `{"source_id", "type", "title", "path_or_url", "metadata"}` |
| `parse_source(source_id)` | source_id | `{"document": {title, pages[], metadata, toc}}` (Docling normalized) |
| `get_document_structure(source_id)` | source_id | `{"chapters": [{"title", "sections": [...], "page"}]}` |
| `get_chunks(source_id, filters?)` | source_id + optional filters | `{"chunks": [{"chunk_id", "text", "page", "section", "topic"}]}` |

### 4.2 RAG Tools

| الأداة | المدخلات | المخرجات |
| --- | --- | --- |
| `semantic_search(source_id, query, top_k)` | query, k | قائمة مقاطع مرتبة دلالياً + scores |
| `keyword_search(source_id, query, top_k)` | query, k | قائمة مقاطع + keyword match scores |
| `hybrid_search(source_id, query, top_k)` | query, k | Fusion (RRF) بين البحثين + reranking |
| `rerank_results(query, chunks)` | query + candidate chunks | قائمة أعيد ترتيبها + rerank scores |

### 4.3 Knowledge Tools

| الأداة | المدخلات | المخرجات |
| --- | --- | --- |
| `extract_concepts(chunks)` | list of chunks | `{"concepts": [{"name", "type", "definition", "source_chunk_id", "confidence"}]}` |
| `extract_relationships(concepts, chunks)` | concepts + chunks | `{"relationships": [{"source", "relation", "target", "evidence_chunk_id"}]}` |
| `merge_concepts(concepts)` | concept candidates | مفاهيم مدمجة بعد كشف التكرارات |
| `build_graph(concepts, relationships)` | مفاهيم + علاقات | `{"nodes": [...], "edges": [...]}` |
| `validate_graph(graph)` | graph | `{"valid", "issues": [...], "confidence"}` |
| `detect_cycles(graph)` | graph | `{"has_cycle": bool, "cycles": [[...]]}` |
| `topological_sort(graph)` | graph | ترتيب خطي للمفاهيم (Kahn's algorithm) |

### 4.4 Learning Tools

| الأداة | المدخلات | المخرجات |
| --- | --- | --- |
| `generate_learning_path(sorted_graph, source)` | graph مرتب + source | `{"modules": [{"title", "order", "objectives"}]}` |
| `generate_module(module_spec, chunks)` | مواصفة وحدة | `{"lessons": [...]}` |
| `generate_lesson(lesson_spec, chunks)` | مواصفة درس | `{"title", "content", "exercises", "citations": [...]}` |
| `generate_assessment(objectives, chunks)` | أهداف + مقاطع | `{"questions": [{"type", "question", "options?", "answer", "rationale", "citations"}]}` |

### 4.5 Validation Tools

| الأداة | الوظيفة |
| --- | --- |
| `verify_source()` | التحقق من أن المعلومة موجودة فعلاً في المقطع المسند |
| `check_citations()` | مطابقة كل citation مع chunk_id صالح |
| `validate_json(payload, schema)` | التحقق من المخرجات مقابل JSON Schema |
| `calculate_confidence()` | حساب درجة ثقة مركبة لكل كيان/علاقة |

### 4.6 Persistence Tools

| الأداة | الوظيفة |
| --- | --- |
| `save_draft(job_id, payload)` | حفظ مسودة في حالة `review_required` |
| `update_graph(graph)` | حفظ/تحديث الرسم المعرفي |
| `save_learning_path(path_id, payload)` | حفظ مسار التعلم النهائي بعد المراجعة |

---

## 5. JSON Schemas — المخططات الهيكلية

### 5.1 Concept (المفهوم)

```json
{
  "type": "object",
  "required": ["id", "name", "type", "definition", "source_chunk_ids"],
  "properties": {
    "id": {"type": "string"},
    "name": {"type": "string"},
    "type": {"enum": ["concept", "definition", "skill", "topic", "method", "tool", "example", "assessment"]},
    "definition": {"type": "string"},
    "source_chunk_ids": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

### 5.2 Relationship (العلاقة)

```json
{
  "type": "object",
  "required": ["source_concept_id", "relation", "target_concept_id", "evidence_chunk_ids"],
  "properties": {
    "relation": {
      "enum": [
        "prerequisite_of", "part_of", "type_of", "related_to",
        "depends_on", "example_of", "teaches", "assesses", "generalization_of"
      ]
    },
    "evidence_chunk_ids": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

### 5.3 Learning Path

```json
{
  "type": "object",
  "required": ["source_id", "modules"],
  "properties": {
    "source_id": {"type": "string"},
    "title": {"type": "string"},
    "modules": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["order", "title", "learning_objectives", "concepts_covered"],
        "properties": {
          "order": {"type": "integer"},
          "title": {"type": "string"},
          "learning_objectives": {"type": "array", "items": {"type": "string"}},
          "concepts_covered": {"type": "array", "items": {"type": "string"}},
          "estimated_hours": {"type": "number"}
        }
      }
    }
  }
}
```

### 5.4 Lesson + Assessment (مختصر)

- **Lesson**: `{title, objectives[], body (markdown), examples[], citations[], exercises[]}`
- **Assessment**: `{questions[]}` حيث السؤال: `{type: "mcq|open", question, options?[], answer, rationale, citations[], difficulty}`

---

## 6. RAG Pipeline بالتفصيل (Hybrid RAG)

```text
               استعلام المستخدم (أو استعلام داخلي من الـAgent)
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
        Vector Search               Keyword Search
      (cosine similarity         (BM25 / Postgres full-text
       عبر Qdrant + BGE-M3)        search عبر pgvector)
                │                           │
                └─────────────┬─────────────┘
                              ▼
                      Reciprocal Rank Fusion
                      (RRF: score = Σ 1/(60+rank))
                              │
                              ▼
                        Reranker
            (cross-encoder محلي حسب توفر VRAM — اختياري)
                              │
                              ▼
                  Top-k Chunks ذات الصلة
                              │
                              ▼
                  LLM يولّد جواب/استخراج + Citations
```

**مخرجات الاسترجاع لكل chunk**:

```json
{
  "chunk_id": "chk-7f2a",
  "text": "Supervised Learning uses labeled data...",
  "source_id": "src-42",
  "page": 15,
  "section": "Machine Learning Types",
  "topic": "Supervised Learning",
  "score": 0.91
}
```

الاحتفاظ بـ `page/section/topic` ضروري لأن الهدف النهائي هو **خريطة معرفية** وليس دردشة فقط — كل عقدة في الرسم تشير إلى موقعها في المستند.

---

## 7. Knowledge Graph Schema

### 7.1 التخزين (مرحلتان)

**MVP**: جداول PostgreSQL — أسرع في البدء، وأسهل للتكامل مع Backend الذي يملك PostgreSQL أصلاً:

```sql
CREATE TABLE concepts (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,            -- concept, definition, skill, ...
  definition TEXT,
  source_id UUID NOT NULL,       -- ربط بجدول المصادر في Backend
  confidence REAL,
  metadata JSONB
);

CREATE TABLE relationships (
  id UUID PRIMARY KEY,
  source_concept_id UUID REFERENCES concepts(id),
  relation TEXT NOT NULL,        -- prerequisite_of, type_of, part_of, ...
  target_concept_id UUID REFERENCES concepts(id),
  evidence_chunk_ids JSONB,
  confidence REAL,
  UNIQUE (source_concept_id, relation, target_concept_id)
);
```

**Phase 2**: Neo4j Community Edition (GPLv3) عند الحاجة لاستعلامات graph معقدة (multi-hop، traversal). الانتقال سهل لأن الـRepositories تعزل منطق الوصول.

### 7.2 Schema للرسم (مخرجات الـAgent)

```json
{
  "graph_id": "g-1",
  "source_id": "src-42",
  "nodes": [
    {"id": "c1", "name": "Artificial Intelligence", "type": "topic",
     "definition": "...", "metadata": {"page": 1, "section": "Intro"}}
  ],
  "edges": [
    {"source": "c2", "target": "c1", "relation": "type_of",
     "confidence": 0.94, "evidence": ["chk-3a"]}
  ],
  "metadata": {
    "algorithm_validated": true,
    "cycles_detected": 0,
    "topological_order": ["c1", "c2", "c3"],
    "generated_at": "2026-08-13T10:10:00Z"
  }
}
```

---

## 8. Prompt Architecture (بنية الـPrompts)

جميع الـPrompts ملفات `.md` منفصلة في مجلد `prompts/` (لا تُكتب داخل الكود). البنية الموحدة لكل prompt:

```text
<Role>
أنت مهندس معرفة تعليمية متخصص في استخراج الخرائط المفاهيمية من المحتوى الأكاديمي.
</Role>

<Context>
المستند: {document_title} — القسم: {section}
</Context>

<Task>
استخرج المفاهيم والعلاقات من المقطع التالي...
</Task>

<Schema>
استخرج JSON مطابقاً تماماً للمخطط: {json_schema}
</Schema>

<Constraints>
- العربية الفصحى في المخرجات
- لا تخترع معلومات غير موجودة في النص
- كل concept يجب أن يسند إلى chunk_id
- إذا لم تجد علاقات، أعد مصفوفة فارغة (لا تخمن)
</Constraints>

<Input>
{chunk_text}
</Input>
```

**مجموعة الـPrompts المطلوبة**:

| الملف | الاستخدام |
| --- | --- |
| `extract_concepts.md` | استخراج المفاهيم من chunk |
| `extract_relationships.md` | استخراج العلاقات بين المفاهيم |
| `extract_prerequisites.md` | تحديد المتطلبات السابقة |
| `chunk_summarize.md` | تلخيص chunk للاستخدام في الترتيب الطوبولوجي |
| `generate_module.md` | توليد وحدة تعلم |
| `generate_lesson.md` | توليد درس |
| `generate_assessment.md` | توليد أسئلة تقييم |
| `validate_concepts.md` | مراجعة المفاهيم (Self-reflection/Validation) |

---

## 9. استراتيجية النماذج المحلية (RTX 4060 6GB VRAM + 16GB RAM)

### 9.1 مبدأ GPU-aware

لا نحمل كل النماذج في VRAM في نفس الوقت. ننفذ **بالتتابع** مع تفريغ الذاكرة بين المراحل:

```text
Embedding (BGE-M3) → تفريغ/إزاحة → LLM (Qwen3) → تفريغ → Reranker (اختياري)
```

### 9.2 الاختيار النهائي المقترح

| الاستخدام | النموذج | الحجم التقريبي | ملاحظات |
| --- | --- | --- | --- |
| Agent الرئيسي (استخراج + توليد) | `qwen3:8b` (Q4_K_M) | ~5.2GB ملف | يُحمَّل للـGPU كلما لزم؛ context 4096–8192 |
| Agent أخف/أسرع (تجارب) | `qwen3:4b` | ~2.5GB | البديل إذا كان 8B بطيئاً |
| Vision / PDF معقد بصرياً | `gemma3:4b` | ~3.3GB | لفهم الجداول والمخططات في PDF |
| Embeddings | `bge-m3` | ~1.1GB | CPU/GPU مشترك، مستقل عن LLM |
| Reranker (اختياري) | `bge-reranker-v2-m3` | ~1GB | يُحمَّل فقط أثناء الاسترجاع |

**إعدادات Ollama المقترحة**:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_GPU=999        # offload كل ما يمكن
TEMPERATURE_EXTRACTION=0.1   # منخفضة لاستخراج JSON
```

- استخدام **Structured Outputs + JSON Schema** بدل الاعتماد على كتابة JSON يدوياً (Ollama يدعم واجهة OpenAI-compatible مع tools وJSON mode).
-Concurrency = 1 (لا نحتاج معالجة متوازية متعددة النماذج على جهاز 6GB).

### 9.3 خطة البينشمارك قبل الاعتماد

اختبار 20–50 مستنداً عربياً وإنجليزياً وقياس: جودة العربية، جودة الإنجليزية، صحة JSON، جودة استخراج المفاهيم والعلاقات، Tool Calling، زمن الاستجابة، استهلاك VRAM/RAM. إذا نجح `qwen3:8b` نعتمده؛ وإلا ننزل إلى `qwen3:4b`، ونبقي `gemma3:4b` خياراً للمهام البصرية.

---

## 10. FastAPI Contract — التكامل مع Backend الفريق

### 10.1 المبدأ

فريق Backend **لا يستدعي Ollama مباشرة** ولا يعرف شيئاً عن RAG. ينادي فقط:

```text
Backend  ──REST──▶  Ufuq AI Engine (FastAPI)  ──▶ Agent  ──▶ Tools
```

### 10.2 Endpoints

| Method | Endpoint | الوظيفة |
| --- | --- | --- |
| `POST` | `/api/v1/health` | فحص جاهزية المحرك (LLM+Qdrant+DB) |
| `POST` | `/api/v1/sources/{source_id}/process` | بدء معالجة مصدر → يرجع `job_id` |
| `GET` | `/api/v1/jobs/{job_id}` | حالة المهمة: `queued/processing/completed/review_required/failed` |
| `GET` | `/api/v1/jobs/{job_id}/result` | النتيجة الكاملة (مفاهيم، علاقات، رسم، مسار مقترح) |
| `POST` | `/api/v1/sources/{source_id}/learning-path` | توليد مسار تعلم من مصدر معالج |
| `POST` | `/api/v1/sources/{source_id}/ask` | سؤال RAG عن مصدر معين |
| `GET` | `/api/v1/sources/{source_id}/concepts` | مفاهيم المصدر |
| `GET` | `/api/v1/sources/{source_id}/graph` | الرسم المعرفي (JSON للـvisualization) |
| `POST` | `/api/v1/review/{item_id}/decision` | مدرس يوافق/يعدل/يرفض عنصراً |

### 10.3 نمط الاستجابة القياسي

```json
{
  "source_id": "src-42",
  "job_id": "job-abc123",
  "status": "review_required",
  "concepts": [...],
  "relationships": [...],
  "graph": {"nodes": [...], "edges": [...]},
  "learning_path": {...},
  "citations": [...],
  "metrics": {
    "chunk_count": 142,
    "concept_count": 67,
    "avg_confidence": 0.88,
    "processing_time_seconds": 245
  }
}
```

الـBackend يبني عليه **Teacher Dashboard**: Review AI Draft → Approve / Edit / Reject.

---

## 11. خطة الانتقال من Ollama المحلي إلى Cloud

نصمم **LLM Provider Interface** من اليوم الأول. الـAgent وRAG وTools وPrompts وValidation تبقى نفسها تماماً؛ يتغير فقط الـProvider:

```env
# محلي (MVP)
AI_MODE=local
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b

# سحابي (مستقبلاً)
AI_MODE=cloud
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=...
```

مسار PDF المعقد بصرياً (جداول + مخططات + صور) يمكن أن يُوجه إلى Gemini Files API حتى في الوضع المحلي عند توفر مفتاح، بينما PDF البسيط يُعالج بـ Docling + Qwen محلياً — وهذا يبقى **قراراً في طبقة الـRouting** وليس في منطق العمل.

---

## 12. MCP Architecture (المرحلة المستقبلية)

MCP ليس في قلب MVP. يظهر أولاً كـ**Integration Layer** ثم يتحول إلى **واجهة استهلاك خارجية**:

**المرحلة الحالية (MVP)**: Agent → Internal Tools مباشرة (لا MCP).

**المرحلة الثانية**: كل مجموعة أدوات تُغلَّف كمخدّم MCP مستقل:

```text
LLM
  │
  ▼
Agent
  │
  ▼
MCP Client
  ├── Document MCP Server   (parse_pdf, parse_docx, extract_metadata)
  ├── RAG MCP Server        (semantic_search, keyword_search, hybrid_search)
  ├── Knowledge MCP Server  (search_concepts, get_related_nodes, save_graph)
  └── Learning MCP Server   (generate_path, generate_lesson, get_assessment)
```

**المرحلة الثالثة (Ufuq MCP Server)**: agents خارجية تستهلك منصتنا:

```text
External AI Agent (Claude Desktop, Cursor, ...)
        │
        ▼
  Ufuq MCP Server (مكتبة mcp — open-source SDK)
        ├── search_ufuq_knowledge
        ├── get_learning_path
        ├── get_concept
        └── recommend_course
```

بهذا يتحول المشروع من منصة إلى **AI-Accessible Educational Knowledge Platform**.

---

## 13. خطة Testing وEvaluation

### 13.1 مستويات الاختبار

| المستوى | الأداة | ماذا يختبر |
| --- | --- | --- |
| Unit | pytest | كل أداة (Tool) بشكل مستقل مع mocks — دون نماذج |
| Algorithm | pytest | cycle detection + topological sort بمدخلات حتمية |
| Schema | pydantic | صحة كل JSON مقابل schema قبل الحفظ |
| Integration | pytest + Docker | المحرك كاملاً: Ingestion → RAG → Extraction → Graph |
| E2E | curl / Postman | API Contract كاملاً |
| LLM Quality | تقييم يدوي + آلي | جودة استخراج عربي/إنجليزي، صحة JSON، tool calling |

### 13.2 مقاييس التقييم (AI Evaluation)

- **JSON Validity Rate**: نسبة الاستجابات الصالحة schema (الهدف ≥ 95%).
- **Citation Accuracy**: نسبة الاقتباسات المطابقة فعلاً للنص (الهدف ≥ 90%).
- **Cycle-Free Guarantee**: 100% (ضمان خوارزمي حتمي، ليس احتمالياً).
- **Extraction Completeness**: نسبة المفاهيم المستخرجة مقارنة بمعيار يدوي.
- **Latency**: زمن معالجة مستند 50 صفحة (الهدف < 10 دقائق على الجهاز المستهدف).
- **VRAM Headroom**: التأكد من بقاء ≥ 1GB حرة.

---

## 14. هيكل مستودع GitHub

```text
ufuq-ai-engine/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md          ← هذه الوثيقة
│   └── LOCAL_SETUP.md           ← دليل التشغيل المحلي خطوة بخطوة
├── app/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI entry point
│   ├── config.py                ← إعدادات موحدة (pydantic-settings)
│   ├── api/
│   │   ├── routes_jobs.py       ← إدارة المهام
│   │   ├── routes_sources.py    ← معالجة المصادر
│   │   ├── routes_rag.py        ← استعلامات RAG
│   │   └── routes_learning.py   ← مسارات ودروس
│   ├── llm/
│   │   ├── base.py              ← LLMProvider interface (Abstract)
│   │   ├── factory.py           ← بناء provider من env
│   │   ├── ollama_provider.py
│   │   ├── openai_provider.py
│   │   └── gemini_provider.py
│   ├── ingestion/
│   │   ├── parser.py            ← واجهة DocumentParser
│   │   ├── docling_parser.py    ← تنفيذ Docling
│   │   ├── chunker.py           ← Semantic Chunking مع retaining structure
│   │   └── metadata.py          ← metadata enrichment
│   ├── embeddings/
│   │   ├── model.py             ← BGE-M3 wrapper
│   │   └── service.py           ← خدمة التضمين
│   ├── vectorstore/
│   │   └── qdrant_store.py      ← Qdrant repository
│   ├── rag/
│   │   ├── retriever.py         ← vector retriever
│   │   ├── hybrid_search.py     ← RRF fusion + keyword
│   │   ├── reranker.py          ← reranker (optional)
│   │   └── citations.py         ← إسناد الاقتباسات
│   ├── knowledge/
│   │   ├── extractor.py         ← مفهوم + علاقات عبر LLM
│   │   ├── graph_builder.py     ← بناء الرسم
│   │   ├── validator.py         ← تحقق و confidence
│   │   └── graph_store.py       ← repository للرسم (Postgres/Neo4j)
│   ├── algorithms/
│   │   ├── cycle_detection.py   ← خوارزمي حتمي
│   │   └── topological_sort.py  ← Kahn's algorithm
│   ├── learning/
│   │   ├── path_generator.py
│   │   ├── lesson_generator.py
│   │   └── assessment_generator.py
│   ├── agent/
│   │   ├── state.py             ← AgentState dataclass
│   │   ├── orchestrator.py      ← حلقة التنفيذ + transitions
│   │   └── policy.py            ← قواعد الانتقال
│   ├── tools/
│   │   ├── registry.py          ← Tool Registry
│   │   ├── document_tools.py
│   │   ├── rag_tools.py
│   │   ├── knowledge_tools.py
│   │   └── learning_tools.py
│   ├── mcp_server/
│   │   └── server.py            ← Ufuq MCP server (future)
│   └── schemas/
│       ├── concepts.py          ← Pydantic models
│       ├── graph.py
│       ├── learning_path.py
│       └── jobs.py
├── prompts/                     ← كل prompts كملفات markdown
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                ← مستندات تجريبية
├── docker/
│   └── docker-compose.yml
├── .env.example
├── requirements.txt
└── Makefile
```

---

## 15. خطة التطوير المرحلية (Phases)

| المرحلة | المحتوى | الناتج |
| --- | --- | --- |
| Phase 1 | AI Engine Foundation (config, main, health, LLM abstraction) | محرك يعمل، قابل لتبديل provider |
| Phase 2 | Document Intelligence (Docling + Chunking + metadata) | مستند → chunks منظمة |
| Phase 3 | RAG (BGE-M3 + Qdrant + Hybrid Search + Reranker) | استرجاع موثوق + citations |
| Phase 4 | Knowledge Extraction (concepts + relationships + validation) | مفاهيم موثقة |
| Phase 5 | Knowledge Graph (build + algorithmic validation + topological sort) | رسم معتمد خوارزمياً |
| Phase 6 | Learning Path Agent (modules + lessons + assessments) | مسودات للمراجعة |
| Phase 7 | Human Review Integration (review decisions) | دورة إغلاق المراجعة |
| Phase 8 | Backend Integration (AI API Contract كامل) | تكامل مع منصة أُفق |
| Phase 9 | MCP (مخدّمات الأدوات + Ufuq MCP Server) | منصة قابلة للاستهلاك من agents خارجية |
| Phase 10 | Evaluation + Optimization (بينشمارك + تحسين prompts) | تقرير جودة جاهز للعرض الأكاديمي |

---

## 16. البرامج مفتوحة المصدر القابلة للدمج (لتسريع التطوير)

| الأداة | الترخيص | الدور |
| --- | --- | --- |
| [Ollama](https://ollama.com) | MIT | تشغيل النماذج المحلية بواجهة OpenAI-compatible |
| [Docling](https://docling-project.github.io/docling/) | MIT | تخليط موحد لجميع أنواع المستندات |
| [Qdrant](https://qdrant.tech) | Apache-2.0 | Vector DB مع hybrid search مدمج |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) | MIT | تضمين متعدد اللغات (100+ لغة، 1024 بعد) |
| [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | MIT | إعادة ترتيب النتائج (cross-encoder) |
| [FastAPI](https://fastapi.tiangolo.com) | MIT | API framework |
| [pgvector](https://github.com/pgvector/pgvector) | PostgreSQL License | بحث متجهي داخل PostgreSQL |
| [Neo4j Community](https://neo4j.com) | GPLv3 | graph DB للمستقبل |
| [mcp Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | بناء مخدّم MCP |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Apache-2.0 | تشغيل BGE-M3 محلياً |
| [LangGraph](https://langchain-ai.github.io/langgraph/) | MIT | بديل مستقبلي للـorchestration عند التعقيد |

---

## 17. تقييم استخدام الذكاء الاصطناعي في التطوير والبرمجة

استخدام الذكاء الاصطناعي كأداة مساعدة في التطوير له قيمة عالية، بشرط ضوابط محددة تجعله أداة لا بديلاً عن الفهم الهندسي:

**المزايا**: توليد boilerplate (models، routes)، كتابة الاختبارات الأولية، مراجعة الكود واكتشاف الأخطاء، وشرح المكتبات الجديدة. هذه الاستخدامات تسرع التطوير بشكل كبير دون مخاطرة معمارية.

**المخاطر وضوابطها**:

| الخطر | الضابط |
| --- | --- |
| كود AI يفهمه أحد فقط | لا يقبل أي كود لم يفهمه الفريق سطراً بسطر |
| أخطاء خفية في المنطق الحاسم | الخوارزميات الحتمية (cycles, topological sort) تُكتب يدوياً وتُختبر بدقة؛ لا تُفوَّض للـLLM |
| تدهور الأمن (hardcoded secrets) | مراجعة كل كود AI بحثاً عن مفاتيح أو ثغرات |
| اعتماد على توليد بدون تحقق | كل مخرج LLM يمر بـ JSON Schema validation قبل الاستخدام |

**الخلاصة**: نستخدم AI لتسريع البناء، ونستخدم الفهم البشري للتحكم في القرار. كل سطر في هذا المشروع يجب أن يكون مفهوماً ومختبراً.

---

## 18. المتطلبات غير الوظيفية

1. **الموثوقية**: لا فقدان بيانات عند فشل مهمة؛ كل خطوة تُسجَّل في حالة المهمة.
2. **القابلية للمراقبة**: logging منظم + `processing_time` metrics + OpenTelemetry لاحقاً.
3. **القابلية للتوسع**: كل مكون يعمل في حاوية Docker منفصلة؛ يمكن نقله للسحابة بنقل الحاوية.
4. **الأمان**: لا مفاتيح في الكود؛ `.env` خارج المستودع؛ فحص المدخلات قبل الـparsing.
5. **اللغة**: دعم كامل للعربية والإنجليزية في كل الطبقات (prompts، extraction، UI payloads).
6. **الاستدامة على الجهاز**: لا يحترق الجهاز — تحميل النماذج بالتتابع مع مراقبة VRAM.
