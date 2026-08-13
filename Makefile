# Ufuq AI Engine — Makefile
#
# الأوامر الأساسية:
#   make setup       → إنشاء البيئة الافتراضية وتثبيت المتطلبات
#   make dev         → تشغيل المحرك محلياً (بدون Docker)
#   make docker-up   → تشغيل كل المكونات في Docker
#   make docker-down → إيقاف Docker
#   make models      → تحميل النماذج في Ollama
#   make test        → تشغيل الاختبارات
#   make lint        → فحص التنسيق
#   make pull-model  → تحميل نموذج محدد: make pull-model MODEL=qwen2.5:7b

PYTHON ?= python3
PIP ?= pip3
VENV ?= .venv

.PHONY: setup dev dev-gpu docker-up docker-down models test lint pull-model clean help

help:
	@echo "Ufuq AI Engine — الأوامر المتاحة:"
	@echo "  setup        إنشاء البيئة وتثبيت المتطلبات"
	@echo "  dev          تشغيل المحرك (بدون Docker)"
	@echo "  dev-gpu      تشغيل المحرك مع تسريع GPU (CUDA)"
	@echo "  docker-up    تشغيل Docker (ollama+qdrant+postgres+engine)"
	@echo "  docker-down  إيقاف Docker"
	@echo "  models       تحميل النماذج الافتراضية في Ollama"
	@echo "  test         تشغيل الاختبارات"
	@echo "  lint         فحص التنسيق (ruff)"
	@echo "  clean        تنظيف الملفات المؤقتة"

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	@cp -n .env.example .env 2>/dev/null || true
	@echo "✓ البيئة جاهزة — عدّل .env ثم شغّل: source $(VENV)/bin/activate && make dev"

dev:
	$(PYTHON) -m uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

dev-gpu:
	CUDA_VISIBLE_DEVICES=0 $(PYTHON) -m uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

docker-up:
	cd docker && docker compose up -d --build

docker-down:
	cd docker && docker compose down

models:
	ollama pull qwen2.5:7b
	ollama pull llama3.2:3b

pull-model:
	ollama pull $(MODEL)

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit:
	$(PYTHON) -m pytest tests/unit -v --tb=short

lint:
	$(PYTHON) -m ruff check app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .mypy_cache
	@echo "✓ تم التنظيف"
