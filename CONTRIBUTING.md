# Contributing to Ufuq AI Engine

Thank you for your interest in contributing! / نشكرك على اهتمامك بالمساهمة!

## How to Contribute / كيف تساهم

1. **Fork** the repository / اعمل fork للمستودع
2. **Create a branch** for your change / أنشئ فرعاً جديداً: `git checkout -b feature/your-feature`
3. **Write tests** for new behavior / اكتب اختبارات لسلوكك الجديد
4. **Run the test suite** and ensure it passes / شغّل الاختبارات وتأكد من نجاحها:

```bash
python -m pytest tests/unit -v
python tests/integration_test.py
```

5. **Open a Pull Request** with a clear description / افتح Pull Request بوصف واضح

## Coding Standards / معايير الكود

The project enforces strict separation between **Architecture**, **Technologies**, and **Business Logic**. When contributing:

- Never hard-code a provider-specific import outside `app/llm/` / لا تستورد مزوداً معيناً خارج `app/llm/`
- All LLM-generated JSON must be validated against a schema in `app/schemas/` or `prompts/` / يجب التحقق من كل JSON مولّد بمخطط
- Deterministic algorithms (graph, sorting, validation) live in `app/algorithms/` and `app/knowledge/validator.py` / الخوارزميات الحتمية في `app/algorithms/`
- Add bilingual (Arabic/English) comments and documentation where feasible / أضف تعليقات ثنائية اللغة عند الإمكان

## Reporting Issues / الإبلاغ عن مشاكل

Use the GitHub Issues tab with:
- Environment details (OS, GPU, Python version, Ollama version)
- Reproduction steps and expected vs actual behavior

---

The project is licensed under MIT. Contributions are implicitly under the same license. / المشروع مرخص تحت MIT.
