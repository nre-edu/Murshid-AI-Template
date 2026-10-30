"""
Fixes systematic Arabic PDF extraction errors (Lam-Alef ligature swaps
and common font-subset confusions). Does not invent content — only
deterministic character/word remapping of known extraction artifacts.
"""
from __future__ import annotations

import re
from typing import Tuple

# Ordered longest-first word replacements for known PDF subset/ligature errors.
WORD_FIXES: Tuple[Tuple[str, str], ...] = (
    ("اإلرشاف", "الإشراف"),
    ("لإلرشاف", "للإشراف"),
    ("إلرشاف", "إشراف"),
    ("اإللكرتونية", "الإلكترونية"),
    ("اإللكرتوني", "الإلكتروني"),
    ("إلكرتونياا", "إلكترونياً"),
    ("إلكرتونية", "إلكترونية"),
    ("إلكرتوني", "إلكتروني"),
    ("المبارشة", "المباشرة"),
    ("المبارش", "المباشر"),
    ("مبارشة", "مباشرة"),
    ("مبارش", "مباشر"),
    ("الهيئتني", "الهيئتين"),
    ("المنسوبني", "المنسوبين"),
    ("الموظفني", "الموظفين"),
    ("المراجعني", "المراجعين"),
    ("العاملني", "العاملين"),
    ("ممرضني", "ممرضين"),
    ("مؤهلني", "مؤهلين"),
    ("والختصاصات", "والاختصاصات"),
    ("والستئذان", "والاستئذان"),
    ("والتأخري", "والتأخير"),
    ("تأخري", "تأخير"),
    ("والرتجيع", "والترجيع"),
    ("الرتجيع", "الترجيع"),
    ("والرتقيات", "والترقيات"),
    ("رتقيات", "ترقيات"),
    ("التصالت", "الاتصالات"),
    ("االتصالت", "الاتصالات"),
    ("الرشوط", "الشروط"),
    ("رشوط", "شروط"),
    ("رشاكات", "شراكات"),
    ("التجهزيات", "التجهيزات"),
    ("تجهزيات", "تجهيزات"),
    ("تجهزيها", "تجهيزها"),
    ("تجهزي", "تجهيز"),
    ("المقرتحات", "المقترحات"),
    ("مقرتحات", "مقترحات"),
    ("مقرتح", "مقترح"),
    ("البرشية", "البشرية"),
    ("برشية", "بشرية"),
    ("الربامج", "البرامج"),
    ("المتمزية", "المتميزة"),
    ("متمزية", "متميزة"),
    ("التمزي", "التميز"),
    ("تمزي", "تميز"),
    ("العتماد", "الاعتماد"),
    ("األقسام", "الأقسام"),
    ("األمر", "الأمر"),
    ("األمراض", "الأمراض"),
    ("األولية", "الأولية"),
    ("األجهزة", "الأجهزة"),
    ("األصناف", "الأصناف"),
    ("األثاث", "الأثاث"),
    ("األدوات", "الأدوات"),
    ("األمن", "الأمن"),
    ("اآلمنة", "الآمنة"),
    ("اآليل", "الآلي"),
    ("اآللية", "الآلية"),
    ("باآلتي", "بالآتي"),
    ("اآلتية", "الآتية"),
    ("اآلتي", "الآتي"),
    ("وفقاا", "وفقاً"),
    ("مالياا", "مالياً"),
    ("فنياا", "فنياً"),
    ("تقنياا", "تقنياً"),
    ("أماناا", "أماناً"),
    ("ورقياا", "ورقياً"),
    ("أسبوعياا", "أسبوعياً"),
    ("شهرياا", "شهرياً"),
    ("سنوياا", "سنوياً"),
    ("سادساا", "سادساً"),
    ("أولاا", "أولاً"),
    ("أوالا", "أولاً"),
    ("ثانياا", "ثانياً"),
    ("ثالثاا", "ثالثاً"),
    ("رابعاا", "رابعاً"),
    ("خامساا", "خامساً"),
    ("سابعاا", "سابعاً"),
    ("ثامناا", "ثامناً"),
    ("تاسعاا", "تاسعاً"),
    ("عاشراا", "عاشراً"),
    ("عارشاً", "عاشراً"),
    ("الحالت", "الحالات"),
    ("حالت", "حالات"),
    ("المرىض", "المرضى"),
    ("تريض", "ترضي"),
    ("أكرث", "أكثر"),
    ("توفري", "توفير"),
    ("وفري", "وفير"),
    ("نرش", "نشر"),
    ("الرصف", "الصرف"),
    ("الستالم", "الاستلام"),
    ("استالم", "استلام"),
    ("الحتياجات", "الاحتياجات"),
    ("الحتياج", "الاحتياج"),
    ("والحتياطات", "والاحتياطات"),
    ("الحتياطات", "الاحتياطات"),
    ("والهتمام", "والاهتمام"),
    ("الاهتمام", "الاهتمام"),
    ("السالمة", "السلامة"),
    ("التسهيالت", "التسهيلات"),
    ("الجتماعات", "الاجتماعات"),
    ("واحرتافية", "واحترافية"),
    ("المعرتف", "المعترف"),
    ("العالقة", "العلاقة"),
    ("عالقتهم", "علاقتهم"),
    ("إىل", "إلى"),
    ("عىل", "على"),
    ("اليت", "التي"),
    ("يتوىلّ", "يتولى"),
    ("يتوىل", "يتولى"),
    ("تتوىلّ", "تتولى"),
    ("تتوىل", "تتولى"),
    ("الالزمة", "اللازمة"),
)


def fix_lam_alef_swaps(text: str) -> str:
    """
    PDF fonts often emit Lam-Alef ligatures with Alef-variant before Lam:
      اإل → الإ ، األ → الأ ، اآل → الآ
    Do NOT replace bare لآل/لأل — those substrings appear inside correct words like الآلة.
    """
    if not text:
        return text
    text = text.replace("اإل", "الإ")
    text = text.replace("األ", "الأ")
    text = text.replace("اآل", "الآ")
    text = text.replace("لإل", "للإ")
    return text


def fix_arabic_pdf_text(text: str) -> str:
    """Apply deterministic PDF-extraction repairs to Arabic text."""
    if not text:
        return text

    # Skip when text looks already clean (avoid harming correct UTF-8 Markdown like DEMO).
    # Do not use لآل as a marker — it appears inside correct words like الآلة.
    corrupt_markers = ("اإل", "األ", "باآلتي", "اآلداري", "إلكرتون", "المبارش", "اإلداري")
    if not any(m in text for m in corrupt_markers):
        return text

    # Strip reversed/garbled council footer lines often extracted visually reversed
    text = re.sub(
        r"[\(\)]?[\d٠-٩/]*\s*عوضوم\s*[\(\)\d٠-٩/\-ء-ي\s]*?(?:سلجم|ءانمألا|الأمناء|ةسلجلا|ةنجم|مجلس)[^\n]*",
        "",
        text,
    )
    text = re.sub(r"\(.*?\-.*?\-.*?(?:سلجم|مجلس|ءانمألا|الأمناء).*?\)", "", text)

    # Word-level fixes first (include corrupted Lam-Alef forms)
    for bad, good in WORD_FIXES:
        if bad in text:
            text = text.replace(bad, good)

    # Then systematic Lam-Alef swaps for remaining cases
    text = fix_lam_alef_swaps(text)

    # Bare «لإشراف» (missing definite لام) — avoid touching already-correct «للإشراف»
    text = re.sub(r"(?<!ل)لإشراف", "للإشراف", text)

    # Collapse accidental triple+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def is_text_readable_arabic(text: str, min_letters: int = 40) -> bool:
    """Heuristic: reject heavily corrupted Arabic for map generation."""
    if not text or len(text.strip()) < 20:
        return False
    arabic_letters = len(re.findall(r"[\u0600-\u06FF]", text))
    if arabic_letters < min_letters:
        return False
    # High density of classic ligature-swap markers means still corrupted
    corrupt_hits = text.count("اإل") + text.count("األ") + text.count("اآل")
    if corrupt_hits > max(3, arabic_letters // 80):
        return False
    return True
