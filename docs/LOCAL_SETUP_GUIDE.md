# دليل التشغيل المحلي الكامل

**Ufuq AI Engine — وضع التشغيل المحلي المجاني 100%**

هذا الدليل يشرح تشغيل المحرك بالكامل على جهاز ببطاقة RTX 4060 (6GB VRAM) و16GB RAM، دون أي تكلفة اشتراك.

---

## الخطوة 1: تثبيت Ollama

1. نزّل Ollama من [ollama.com](https://ollama.com) وثبّته (Windows/Linux/Mac).
2. بعد التثبيت، تأكّد أنه يعمل:

```bash
ollama --version
ollama serve            # إن لم يكن يعمل كخدمة
```

3. نزّل النماذج المطلوبة:

```bash
ollama pull qwen2.5:7b      # النموذج الرئيسي للتوليد (~4.9GB)
ollama pull llama3.2:3b     # نموذج خفيف للتلخيص والتحقق (~2GB)
```

ملاحظة: `qwen2.5:7b` يستهلك ~5–6GB VRAM. إن كانت الذاكرة ممتلئة أثناء تشغيل embeddings، النظام يفرّغ نموذج BGE-M3 من GPU تلقائياً.

## الخطوة 2: إعداد بيئة بايثون

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

إن واجهت مشاكل مع `docling` (مكتبة ضخمة)، يمكنك تأجيلها؛ النظام يعمل في وضع تجريبي بدونها للنصوص البسيطة، أو ثبّتها بالأمر:

```bash
pip install 'docling[PDFS]'
```

## الخطوة 3: إعداد المتغيرات

```bash
cp .env.example .env
```

القيم الافتراضية في `.env` جاهزة للوضع المحلي — لا حاجة لتعديل أي شيء:

```env
LLM_PROVIDER=ollama
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_SMALL_MODEL=llama3.2:3b
EMBEDDING_MODEL=BAAI/bge-m3
```

## الخطوة 4: تشغيل المخازن (Qdrant + PostgreSQL) — اختياري

لأول تجربة سريعة، يعمل النظام بمخازن **In-Memory** تلقائياً (بدون أي تبعيات). للبيانات الدائمة:

```bash
docker compose -f docker/docker-compose.yml up -d
```

سيشغّل هذا Qdrant على المنفذ 6333 وPostgreSQL على المنفذ 5432 بالبيانات الافتراضية الموجودة في `.env`.

## الخطوة 5: تشغيل المحرك

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

أو باستخدام Makefile:

```bash
make run-local
```

افتح `http://localhost:8000/docs` لعرض Swagger UI التفاعلي الكامل.

## الخطوة 6: أول استخدام — تجربة end-to-end

من Swagger UI أو عبر curl:

**1. رفع مستند:**

```bash
curl -X POST http://localhost:8000/sources/upload \
  -F "file=@كتابك.pdf"
# → يعيد source_id مثل src-xxxx
```

**2. إنشاء مهمة Agent (فهرسة + استخراج معرفة + رسم معرفي):**

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"source_id": "src-xxxx", "job_type": "process_source"}'
# → job_id، ثم تابع الحالة:
curl http://localhost:8000/jobs/{job_id}
```

**3. بعد اكتمال المهمة (status: completed):**

```bash
# الرسم المعرفي
curl http://localhost:8000/knowledge/src-xxxx

# مسار التعلم
curl http://localhost:8000/learning/src-xxxx/path

# بحث RAG
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "ما المقصود بالتعلم الآلي؟", "source_id": "src-xxxx"}'
```

## سير العمل مع المدرس (المراجعة البشرية)

عند اكتمال المعالجة، حالة المهمة تصبح `review_required`. المدرس يراجع المخرجات ثم:

```bash
curl -X POST http://localhost:8000/jobs/{job_id}/review \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'   # أو revise / reject
```

## حل المشاكل الشائعة

| المشكلة | السبب | الحل |
|---|---|---|
| `ollama unavailable` في /health | Ollama غير مشغّل | `ollama serve` |
| نفاد VRAM (CUDA OOM) | أكثر من نموذج محمّل | النظام يدير التفريغ تلقائياً؛ أغلق البرامج الثقيلة |
| `Docling غير مثبت` | لم تُثبّت المكتبة | `pip install 'docling[PDFS]'` |
| embeddings بطيئة على CPU | لا توجد CUDA متاحة | ثبّت `torch` بإصدار CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu124` |

## التبديل إلى الوضع السحابي (مستقبلاً)

عند الرغبة في استخدام Gemini أو OpenAI API بدل النماذج المحلية، عدّل `.env` فقط:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=sk-...
GEMINI_MODEL=gemini-2.5-flash
```

بدون أي تغيير في الكود.
