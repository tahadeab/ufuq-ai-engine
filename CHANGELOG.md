# Changelog

## [0.1.0] — 2026-08

Initial release. / الإصدار الأولي.

### Features / المزايا

- **Ingestion**: Docling parser (PDF/DOCX/PPTX/XLSX/HTML) + semantic chunker preserving document structure
  تخليص المستندات بـDocling مع تقسيم دلالي يحافظ على البنية
- **Embeddings**: Local BGE-M3 with GPU-aware loading/unloading (safe for 6GB VRAM)
  تضمين محلي BGE-M3 مع إدارة ذاكرة GPU
- **Vector Store**: Qdrant with in-memory fallback
  مخزن متجهي Qdrant مع مخزن احتياطي في الذاكرة
- **Hybrid RAG**: Vector + keyword search with RRF fusion and optional CrossEncoder reranker, plus citations
  بحث هجين مع دمج RRF وإعادة ترتيب وخيارات اقتباس
- **Knowledge Extraction**: LLM-based concept/relationship extraction with strict JSON Schema validation
  استخراج مفاهيم وعلاقات عبر LLM مع تحقق صارم
- **Knowledge Graph**: Cycle Detection (DFS) + Kahn Topological Sort + citation verification (deterministic)
  رسم معرفي مع تحقق خوارزمي حتمي
- **Agent Orchestrator**: State machine loop (idle→extract→validate→build_graph→generate_path→review→completed) with retry/fallback
  منسق Agent بحلقة حالات مع استرداد
- **Learning Path Generation**: Modules, lessons, assessments with citations
  توليد مسارات ودروس واختبارات
- **MCP Server**: `search_ufuq_knowledge`, `get_learning_path`, `get_concept`, `recommend_course`
  مخدّم MCP بأربع أدوات
- **FastAPI Contract**: Full REST API with Swagger UI + human review workflow
  واجهة REST كاملة مع سير مراجعة بشرية
- **Bilingual docs**: Architecture + Local Setup guides
  وثائق ثنائية اللغة
