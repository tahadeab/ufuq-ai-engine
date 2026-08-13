"""
Prompt Loader — تحميل الـprompts من ملفات prompts/*.md

المبدأ (من وثيقة المشروع): كل prompts خارج الكود كملفات markdown
في مجلد prompts/ — الكود يحملها ويحقنها بالمتغيرات فقط.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

_templates: Dict[str, str] = {}


def load_prompt(name: str, **variables) -> str:
    """
    تحميل prompt + حقن المتغيرات {document_title}، {json_schema}، {chunk_text}، ...
    """
    if name not in _templates:
        path = PROMPTS_DIR / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt غير موجود: {path}")
        _templates[name] = path.read_text(encoding="utf-8")

    text = _templates[name]
    for key, value in variables.items():
        text = text.replace("{" + key + "}", str(value))
    return text
