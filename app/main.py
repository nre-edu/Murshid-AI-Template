"""Murshid FastAPI app — Vercel-compatible (read-only filesystem in production)."""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.answer_map import DEMO_ANSWER_MAP, DEMO_ANSWER_TEXT, validate_answer_map
from app.branding import find_logo, get_branding_public, load_branding
from app.config import (
    IS_SERVERLESS,
    MAX_QUERY_CHARS,
    RATE_LIMIT_PER_MINUTE,
    get_gemini_api_key,
)
from app.gemini_client import gemini_client
from app.local_knowledge import local_knowledge

_brand = load_branding()
app = FastAPI(
    title=_brand.get("page_title") or "مرشد",
    description=_brand.get("description")
    or "محرك محادثة معرفي يعتمد حصرياً على أدلة Markdown محلية موثّقة",
    version="4.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory rate limit (per process only — not shared across Vercel instances)
_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)
_MAX_RATE_BUCKETS = 10_000
MAX_HISTORY_ITEMS = 6
MAX_HISTORY_ITEM_CHARS = 4000
MAX_BODY_BYTES = 64_000

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; base-uri 'none'; form-action 'self'"
    ),
}


@app.middleware("http")
async def guard_requests(request: Request, call_next):
    length = request.headers.get("content-length") or "0"
    if request.method == "POST" and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
        return JSONResponse({"detail": "حجم الطلب أكبر من المسموح."}, status_code=413)
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        return value[:MAX_HISTORY_ITEM_CHARS]


class ChatRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_CHARS)
    history: List[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


def _client_key(request: Request) -> str:
    # Vercel overwrites X-Forwarded-For; anywhere else a client could forge it
    forwarded = request.headers.get("x-forwarded-for") or ""
    if IS_SERVERLESS and forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _check_rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time.time()
    window = 60.0
    if len(_rate_buckets) > _MAX_RATE_BUCKETS:
        _rate_buckets.clear()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=(
                "تم تجاوز الحد المسموح من الطلبات مؤقتًا. حاول بعد قليل. "
                "(حد تقريبي داخل نسخة الخادم الحالية وليس حماية شاملة على Vercel.)"
            ),
        )
    bucket.append(now)


@app.get("/api/branding")
def get_branding():
    """Public product copy only — never includes secrets."""
    return get_branding_public(has_demo_docs=local_knowledge.get_status()["has_demo_docs"])


@app.get("/api/logo")
def get_logo():
    logo = find_logo()
    if not logo:
        raise HTTPException(status_code=404, detail="لا يوجد شعار في مجلد Logo/.")
    return FileResponse(logo, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/status")
def get_system_status():
    k_status = local_knowledge.get_status()
    has_gemini = bool(get_gemini_api_key())
    has_docs = k_status["ready"]

    if has_gemini and has_docs:
        overall = "ready"
        label = "الأدلة المعتمدة مفهرسة وجاهزة"
        desc = (
            f"النظام متصل بقاعدة الأدلة المحلية "
            f"({k_status['documents_count']} دليل، {k_status['chunks_count']} مقطع مفهرس)."
        )
    elif not has_gemini:
        overall = "incomplete"
        label = "الإعداد غير مكتمل"
        desc = (
            "الأدلة مفهرسة، لكن مفتاح GEMINI_API_KEY غير مهيأ. "
            "أضفه في Vercel من Settings ثم Environment Variables، ثم أعد النشر."
        )
    else:
        overall = "incomplete"
        label = "قاعدة الأدلة فارغة"
        desc = "لم يتم العثور على ملفات .md أو .txt داخل مجلد Knowledge/."

    unsupported = k_status["unsupported_files"]
    if unsupported:
        desc += f" ملفات لن تُقرأ (حوّلها إلى .md أو .txt): {', '.join(unsupported[:5])}."

    return {
        "status": overall,
        "label": label,
        "description": desc,
        "source_type": "local_markdown",
        "documents_count": k_status["documents_count"],
        "chunks_count": k_status["chunks_count"],
        "last_indexed": k_status["last_indexed"],
        "has_gemini_key": has_gemini,
        "readonly_deploy": IS_SERVERLESS,
        "unsupported_files": unsupported,
        # Never return key values or ADMIN secrets
    }


@app.get("/api/sources")
def get_sources():
    docs = local_knowledge.get_documents_list()
    k_status = local_knowledge.get_status()
    return {
        "source_type": "local_markdown",
        "total_documents": len(docs),
        "total_chunks": k_status["chunks_count"],
        "last_indexed": k_status["last_indexed"],
        "documents": docs,
    }


@app.get("/api/source/{doc_id}/{chunk_id}")
def view_source_section(doc_id: str, chunk_id: str):
    clean_doc_id = os.path.basename(doc_id.strip())
    clean_chunk_id = os.path.basename(chunk_id.strip())
    section_data = local_knowledge.get_source_section(clean_doc_id, clean_chunk_id)
    if not section_data:
        raise HTTPException(
            status_code=404,
            detail="المصدر المطلوب غير موجود أو غير متاح في الأدلة المعتمدة.",
        )
    return {"success": True, "source": section_data}


@app.post("/api/chat")
async def handle_chat(req: ChatRequest, request: Request):
    _check_rate_limit(request)

    query = (req.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="السؤال لا يمكن أن يكون فارغًا")
    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"طول السؤال يتجاوز الحد المسموح ({MAX_QUERY_CHARS} حرفًا).",
        )

    if not get_gemini_api_key():
        async def config_error_stream():
            msg = (
                "⚠️ **الإعداد غير مكتمل**\n\n"
                f"• **قاعدة الأدلة:** "
                f"{'متوفرة' if local_knowledge.get_status()['ready'] else 'غير متوفرة'} "
                f"({local_knowledge.get_status()['documents_count']} أدلة).\n"
                "• **الذكاء الاصطناعي:** مفتاح `GEMINI_API_KEY` غير مهيأ.\n\n"
                "افتح زر «إضافة مفتاح الذكاء» واتبع التعليمات "
                "(متغيرات البيئة في Vercel، أو ملف `.env` عند التشغيل المحلي)."
            )
            yield f"data: {json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'citations': [], 'answer_map': None}, ensure_ascii=False)}\n\n"

        return StreamingResponse(config_error_stream(), media_type="text/event-stream")

    citations, context_str, has_evidence = local_knowledge.retrieve_for_chat(query, top_k=4)
    if not has_evidence:
        async def no_evidence_stream():
            msg = (
                "بناءً على المصادر المتاحة حاليًا، "
                "لا تتوفر تفاصيل كافية للإجابة عن هذا السؤال بدقة.\n\n"
                "💡 *يمكنك صياغة السؤال بكلمات مفتاحية أخرى، "
                "أو استعراض قائمة الأدلة من زر «المصادر».*"
            )
            yield f"data: {json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'citations': [], 'answer_map': None}, ensure_ascii=False)}\n\n"

        return StreamingResponse(no_evidence_stream(), media_type="text/event-stream")

    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return StreamingResponse(
        gemini_client.stream_chat_completion(
            query=query,
            chat_history=history_dicts,
            context_str=context_str,
            citations=citations,
        ),
        media_type="text/event-stream",
    )


@app.get("/api/demo/answer-map")
def get_demo_answer_map():
    validated = validate_answer_map(
        DEMO_ANSWER_MAP,
        allowed_chunk_ids={"demo-1", "demo-2", "demo-3"},
        citations=[],
        allow_demo=True,
    )
    return {
        "success": True,
        "isDemo": True,
        "query": "ما الذكاء الاصطناعي؟ وما الفرق بين تعلم الآلة والتعلم العميق؟ وما أبرز التطبيقات العملية؟",
        "answer_text": DEMO_ANSWER_TEXT,
        "answer_map": validated,
        "badge": "عينة توضيحية",
    }


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    name = load_branding().get("variant_name") or "مرشد"
    return f"<h1>{name}</h1>"
