"""Load public branding settings from config/branding.json (no secrets)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List

from app.config import BASE_DIR

BRANDING_PATH = BASE_DIR / "config" / "branding.json"

_DEFAULTS: Dict[str, Any] = {
    "product_name": "مرشد",
    "variant_name": "مرشد طلابي",
    "tagline": "مساعدك للأدلة المعتمدة",
    "page_title": "مرشد — مساعدك المعرفي",
    "description": "مساعد يجيب من الأدلة المعتمدة فقط مع إظهار المصادر.",
    "hero_title_html": "اسأل أدلتك، واحصل على <span class=\"highlight-orange\">إجابة موثّقة</span>",
    "hero_description": "يبحث في الأدلة المعتمدة ويعرض المصادر التي استند إليها.",
    "welcome_title": "مرحباً بك في «مرشد»",
    "welcome_message": "اطرح استفسارك وسأبحث حصرياً داخل الأدلة المعتمدة.",
    "assistant_name": "مرشد",
    "compact_banner": "مرشد: اسأل أدلتك المعتمدة واحصل على إجابة موثّقة",
    "how_it_works_title": "كيف يعمل مرشد؟",
    "footer_brand": "مرشد — المعرفة من مصادرها المعتمدة",
    "footer_disclaimer": "قد تخطئ الإجابات الآلية؛ راجع المصادر عند الحاجة.",
    "input_placeholder": "اكتب استفسارك هنا حول الأدلة المعتمدة...",
    "suggestions_title": "اقتراحات لبدء المحادثة:",
    "suggested_questions": [],
    "audience": "",
    "notes": "",
}


@lru_cache(maxsize=1)
def load_branding() -> Dict[str, Any]:
    data = dict(_DEFAULTS)
    if BRANDING_PATH.is_file():
        try:
            raw = json.loads(BRANDING_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({k: v for k, v in raw.items() if v is not None})
        except (OSError, json.JSONDecodeError):
            pass
    questions = data.get("suggested_questions") or []
    if not isinstance(questions, list):
        questions = []
    cleaned: List[Dict[str, str]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if not query:
            continue
        label = str(item.get("label") or query[:48]).strip()
        cleaned.append({"label": label, "query": query})
    data["suggested_questions"] = cleaned
    data["product_name"] = str(data.get("product_name") or "مرشد").strip() or "مرشد"
    data["variant_name"] = (
        str(data.get("variant_name") or data["product_name"]).strip()
        or data["product_name"]
    )
    return data


def get_branding_public() -> Dict[str, Any]:
    """Safe public payload for /api/branding (no secrets by design)."""
    b = load_branding()
    return {
        "product_name": b["product_name"],
        "variant_name": b["variant_name"],
        "tagline": b["tagline"],
        "page_title": b["page_title"],
        "description": b["description"],
        "hero_title_html": b["hero_title_html"],
        "hero_description": b["hero_description"],
        "welcome_title": b["welcome_title"],
        "welcome_message": b["welcome_message"],
        "assistant_name": b["assistant_name"],
        "compact_banner": b["compact_banner"],
        "how_it_works_title": b["how_it_works_title"],
        "footer_brand": b["footer_brand"],
        "footer_disclaimer": b["footer_disclaimer"],
        "input_placeholder": b["input_placeholder"],
        "suggestions_title": b["suggestions_title"],
        "suggested_questions": b["suggested_questions"],
        "audience": b.get("audience") or "",
    }
