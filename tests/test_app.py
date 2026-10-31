import json

import pytest
from fastapi.testclient import TestClient

from app import branding, gemini_client as gc, local_knowledge as lk, main
from app.local_knowledge import LocalKnowledgeEngine, build_index_payload, local_knowledge


@pytest.fixture(autouse=True)
def reset_limits():
    main._rate_buckets.clear()


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def make_engine(tmp_path, monkeypatch):
    # Serverless mode: the index stays in memory and nothing is written to the project
    monkeypatch.setattr(lk, "IS_SERVERLESS", True)
    return lambda folder: LocalKnowledgeEngine(folder, tmp_path / "missing-index.json")


def sse_events(response):
    return [json.loads(l[6:]) for l in response.text.splitlines() if l.startswith("data: ")]


def test_sample_front_matter_is_parsed():
    assert "ai-demo-001" in local_knowledge.documents
    assert local_knowledge.get_status()["has_demo_docs"] is True


@pytest.mark.parametrize("question", [
    "ما الذكاء الاصطناعي؟ اذكر تطبيقين وردا في الدليل.",
    "ما الفرق بين تعلم الآلة والتعلم العميق؟",
    "كيف يمكن استخدام الذكاء الاصطناعي لتوقع أعطال المعدات؟",
])
def test_sample_questions_find_sources(question):
    assert local_knowledge.retrieve_for_chat(question)[2] is True


@pytest.mark.parametrize("question", ["كم سعر اشتراك ChatGPT اليوم؟", "ما عاصمة فرنسا؟"])
def test_off_topic_questions_are_refused(question):
    assert local_knowledge.retrieve_for_chat(question)[2] is False


def test_term_frequency_is_counted():
    assert max(p[1] for v in local_knowledge.inverted_index.values() for p in v) > 1


def test_own_sources_work_in_both_languages_and_bom(tmp_path, make_engine):
    (tmp_path / "a.md").write_text(
        "---\nid: reg\ntitle: دليل التسجيل\n---\n## مقرر الذكاء الاصطناعي\n"
        "يفتح التسجيل في مقرر الذكاء الاصطناعي يوم الأحد الأول من شهر سبتمبر لجميع الطلاب.\n",
        encoding="utf-8-sig",
    )
    (tmp_path / "b.txt").write_text(
        "# Handbook\n## Registration\nRegistration for the spring semester opens "
        "on the first Sunday of January for all enrolled students.\n",
        encoding="utf-8",
    )
    engine = make_engine(tmp_path)
    assert engine.documents["reg"]["title"] == "دليل التسجيل"
    assert engine.retrieve_for_chat("متى يفتح التسجيل في مقرر الذكاء الاصطناعي؟")[2]
    assert engine.retrieve_for_chat("When does registration open for the spring semester?")[2]


@pytest.mark.parametrize("question,expected", [
    ("التسجيل", True),
    ("متى التسجيل؟", True),
    ("ما نسبة الغياب؟", True),
    ("كيف أسدد الرسوم؟", True),
    ("هل يمكن تقسيط الرسوم الدراسية؟", True),
    ("ما عاصمة فرنسا؟", False),
    ("وصفة كبسة دجاج", False),
    ("ما هو؟", False),
])
def test_short_natural_questions_on_a_small_guide(tmp_path, make_engine, question, expected):
    (tmp_path / "guide.md").write_text(
        "# دليل الطالب\n## التسجيل\nيفتح التسجيل في المقررات يوم الأحد الأول من شهر سبتمبر.\n"
        "## الغياب\nيحرم الطالب من الاختبار إذا تجاوزت نسبة غيابه خمسة وعشرين بالمئة.\n"
        "## الرسوم\nتسدد الرسوم الدراسية قبل بداية الفصل، ويمكن تقسيطها بعد الموافقة.\n",
        encoding="utf-8",
    )
    assert make_engine(tmp_path).retrieve_for_chat(question)[2] is expected


def test_committed_stale_index_cannot_hide_new_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(lk, "IS_SERVERLESS", True)
    knowledge = tmp_path / "Knowledge"
    knowledge.mkdir()
    source = knowledge / "a.md"
    source.write_text("# old\n## old\nthe old content of this document is here\n", encoding="utf-8")
    index = tmp_path / "index.json"
    index.write_text(json.dumps(build_index_payload(knowledge)), encoding="utf-8")

    assert LocalKnowledgeEngine(knowledge, index).get_status()["index_source"] == "built"
    source.write_text("# new\n## new\nthe replaced content of this document is here\n", encoding="utf-8")
    engine = LocalKnowledgeEngine(knowledge, index)
    assert engine.get_status()["index_source"] == "live"
    assert "replaced" in engine.chunks[0]["content"]


def test_pdf_is_reported_not_silently_ignored(tmp_path, make_engine):
    (tmp_path / "guide.pdf").write_bytes(b"%PDF")
    assert make_engine(tmp_path).get_status()["unsupported_files"] == ["guide.pdf"]


def test_custom_instructions_reach_the_prompt(tmp_path, monkeypatch):
    path = tmp_path / "instructions.md"
    path.write_text("<!-- مخفي -->\nخاطب الطلاب ببساطة", encoding="utf-8")
    monkeypatch.setattr(branding, "INSTRUCTIONS_PATH", path)
    branding.load_custom_instructions.cache_clear()
    prompt = gc.build_system_prompt()
    branding.load_custom_instructions.cache_clear()
    assert "خاطب الطلاب ببساطة" in prompt
    assert "مخفي" not in prompt
    assert "لا تختلق" in prompt


def test_logo_from_folder(client, tmp_path, monkeypatch):
    assert client.get("/api/logo").status_code == 404
    (tmp_path / "my logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(branding, "LOGO_DIR", tmp_path)
    assert client.get("/api/branding").json()["logo_url"].startswith("/api/logo")
    response = client.get("/api/logo")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_chat_answer_uses_header_key_and_not_url(client, monkeypatch):
    seen = {}

    class Reply:
        status_code = 200
        text = ""
        encoding = None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "الإجابة: نص [1]"}]}}]}

    def fake_post(url, **kwargs):
        seen.update(url=url, headers=kwargs["headers"])
        return Reply()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gc.requests, "post", fake_post)
    events = sse_events(client.post("/api/chat", json={"query": "ما الفرق بين تعلم الآلة والتعلم العميق؟"}))
    assert "test-key" not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    assert "الإجابة" in "".join(e.get("text", "") for e in events)
    assert events[-1]["done"] and events[-1]["citations"]


def test_bad_key_is_not_retried_on_other_models(client, monkeypatch):
    calls = []

    class Reply:
        status_code = 400
        text = "API key not valid"

    monkeypatch.setenv("GEMINI_API_KEY", "bad")
    monkeypatch.setattr(gc.requests, "post", lambda *a, **k: calls.append(1) or Reply())
    events = sse_events(client.post("/api/chat", json={"query": "ما الفرق بين تعلم الآلة والتعلم العميق؟"}))
    assert len(calls) == 1
    assert "error" in events[0]


def test_abuse_limits(client):
    assert client.post("/api/chat", json={"query": "x", "history": [{"role": "user", "content": "a" * 70000}]}).status_code == 413
    assert client.post("/api/chat", json={"query": "x", "history": [{"role": "system", "content": "a"}]}).status_code == 422
    last = None
    for i in range(main.RATE_LIMIT_PER_MINUTE + 1):
        last = client.post("/api/chat", json={"query": "مرحبا"}, headers={"x-forwarded-for": f"1.1.1.{i}"})
    assert last.status_code == 429


def test_no_cors_and_security_headers(client):
    response = client.get("/", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
    assert "script-src 'self'" in response.headers["content-security-policy"]
