"""Load public branding settings from config/branding.json (no secrets)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import BASE_DIR

BRANDING_PATH = BASE_DIR / "config" / "branding.json"
INSTRUCTIONS_PATH = BASE_DIR / "config" / "instructions.md"
LOGO_DIR = BASE_DIR / "Logo"
LOGO_SUFFIXES = (".svg", ".png", ".webp", ".jpg", ".jpeg")
MAX_INSTRUCTIONS_CHARS = 4000
DEFAULT_CONTACT_MESSAGE = "لم أجد الإجابة في الأدلة المتاحة. يمكنك التواصل مع المسؤول:"

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
    "demo_questions": [],
    "contact": {},
    "audience": "",
    "notes": "",
}


def find_logo() -> Optional[Path]:
    """First image in Logo/, whatever it is called."""
    if not LOGO_DIR.is_dir():
        return None
    images = [p for p in LOGO_DIR.iterdir() if p.is_file() and p.suffix.lower() in LOGO_SUFFIXES]
    return min(images, key=lambda p: p.name.lower(), default=None)


@lru_cache(maxsize=1)
def load_custom_instructions() -> str:
    """Site owner's instructions; HTML comments are guidance and are dropped."""
    if not INSTRUCTIONS_PATH.is_file():
        return ""
    try:
        text = INSTRUCTIONS_PATH.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()[:MAX_INSTRUCTIONS_CHARS]


def _clean_questions(questions: Any) -> List[Dict[str, str]]:
    cleaned: List[Dict[str, str]] = []
    for item in questions if isinstance(questions, list) else []:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if not query:
            continue
        label = str(item.get("label") or query[:48]).strip()
        cleaned.append({"label": label, "query": query})
    return cleaned


def _clean_contact(contact: Any) -> Optional[Dict[str, str]]:
    """Contact options shown when no answer is found; None hides them."""
    if not isinstance(contact, dict):
        return None
    whatsapp = re.sub(r"\D", "", str(contact.get("whatsapp") or "")).lstrip("0")
    email = str(contact.get("email") or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        email = ""
    if not whatsapp and not email:
        return None
    message = str(contact.get("message") or "").strip() or DEFAULT_CONTACT_MESSAGE
    return {"message": message, "whatsapp": whatsapp, "email": email}


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
    data["suggested_questions"] = _clean_questions(data.get("suggested_questions"))
    data["demo_questions"] = _clean_questions(data.get("demo_questions"))
    data["contact"] = _clean_contact(data.get("contact"))
    data["product_name"] = str(data.get("product_name") or "مرشد").strip() or "مرشد"
    data["variant_name"] = (
        str(data.get("variant_name") or data["product_name"]).strip()
        or data["product_name"]
    )
    return data


def get_branding_public(has_demo_docs: bool = False) -> Dict[str, Any]:
    """Safe public payload for /api/branding (no secrets by design).

    Demo questions only make sense while the bundled sample is still indexed.
    """
    b = load_branding()
    questions = b["suggested_questions"] or (b["demo_questions"] if has_demo_docs else [])
    logo = find_logo()
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
        "suggested_questions": questions,
        "show_demo_map": has_demo_docs,
        "contact": b["contact"],
        # The size changes with the image, so a new logo is not hidden by browser cache
        "logo_url": f"/api/logo?v={logo.stat().st_size}" if logo else None,
        "audience": b.get("audience") or "",
    }
