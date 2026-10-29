"""Backend tests - no API key and no internet needed (the AI model is replaced by a stand-in).
Run:  python test_backend.py
Covers: website serving, upload validation, the four API shapes, caching, limits, errors, security headers."""
import io, json, re, sys
import pymupdf

import ai_generation, studypilot_api
import app as backend

CALLS = {"model": 0}

def fake_model(system, user, model=None, temperature=0.2):
    CALLS["model"] += 1
    if "multiple-choice" in user:
        n = int(re.search(r"exactly (\d+)", user).group(1))
        return json.dumps({"questions": [{"question": f"Question {i}?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "B", "explanation": "because", "topic": "Assessment", "source_pages": [2]} for i in range(n)]})
    if "overview" in user:
        return "This lecture explains the course plan and the grading system."
    if "Answer the student" in user:
        return "The final exam is 40% of the grade. [Page 2]"
    return "- The final exam is worth 40% of the course grade [p. 2].\n- The course has twelve lectures [p. 1]."

ai_generation._chat = studypilot_api._chat = fake_model
client = backend.app.test_client()
passed = 0

def check(name, cond):
    global passed
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name
    passed += 1

def make_pdf(pages=3, text=True):
    pdf = pymupdf.open()
    lines = ["The final exam is worth 40 percent of the grade in this course.",
             "Assessment includes a midterm exam, a project, and class participation.",
             "The course contains twelve lectures and several practical readings."]
    for n in range(pages):
        page = pdf.new_page()
        if text:
            for i, line in enumerate(lines):
                page.insert_text((60, 80 + 20 * i), f"{line} Page {n + 1}.")
    return pdf.tobytes()

def upload(data, name="lecture.pdf"):
    return client.post("/api/upload", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")

# ---- website
r = client.get("/")
check("website: / serves index.html", r.status_code == 200 and b"StudyPilot" in r.data)
check("website: static files served", client.get("/static/js/app.js").status_code == 200)
check("health: /healthz", client.get("/healthz").get_json() == {"status": "ok"})
check("security headers present", r.headers.get("X-Content-Type-Options") == "nosniff" and r.headers.get("X-Frame-Options") == "DENY")
check("static path traversal blocked", client.get("/static/../backend/app.py").status_code == 404)

# ---- upload
r = upload(make_pdf(3))
j = r.get_json()
check("upload: returns doc_id, filename, real page count", r.status_code == 200 and j["pages"] == 3 and j["filename"] == "lecture.pdf" and len(j["doc_id"]) == 12)
doc_id = j["doc_id"]
r = upload(b"hello world", "notes.pdf")
check("upload: fake .pdf rejected with {error}", r.status_code == 400 and "error" in r.get_json())
r = upload(make_pdf(1), "notes.txt")
check("upload: wrong extension rejected", r.status_code == 400)
r = upload(make_pdf(2, text=False))
check("upload: image-only PDF explained", r.status_code == 400 and "scanned" in r.get_json()["error"])
backend.app.config["MAX_CONTENT_LENGTH"] = 1000
r = upload(make_pdf(3))
backend.app.config["MAX_CONTENT_LENGTH"] = backend.MAX_UPLOAD_MB * 1024 * 1024
check("upload: too-large file -> 413 with {error}", r.status_code == 413 and "error" in r.get_json())
r = client.post("/api/upload")
check("upload: no file -> 400", r.status_code == 400)

# ---- summarize (+ caching)
r = client.post("/api/summarize", json={"doc_id": doc_id}); j = r.get_json()
check("summarize: {summary, key_points[]} plain text", r.status_code == 200 and isinstance(j["summary"], str)
      and isinstance(j["key_points"], list) and j["key_points"] and "**" not in j["summary"] and "[p." not in "".join(j["key_points"]))
before = CALLS["model"]
r2 = client.post("/api/summarize", json={"doc_id": doc_id})
check("summarize: second call is cached (no new model calls)", r2.get_json() == j and CALLS["model"] == before)

# ---- quiz
r = client.post("/api/quiz", json={"doc_id": doc_id, "count": 3}); q = r.get_json()["questions"]
check("quiz: 3 questions with the exact frontend fields",
      len(q) == 3 and all(set(x) == {"question", "options", "answer", "explanation", "page", "topic"} for x in q))
check("quiz: options list of 4, answer is index 0-3, page and topic present",
      all(len(x["options"]) == 4 and x["answer"] == 1 and x["page"] == 2 and x["topic"] == "Assessment" for x in q))
check("quiz: count is capped at 10", len(client.post("/api/quiz", json={"doc_id": doc_id, "count": 999}).get_json()["questions"]) == 10)
check("quiz: bad count falls back to 5", len(client.post("/api/quiz", json={"doc_id": doc_id, "count": "abc"}).get_json()["questions"]) == 5)

# ---- ask
r = client.post("/api/ask", json={"doc_id": doc_id, "question": "What percent is the final exam?"}); j = r.get_json()
check("ask: {answer, sources:[{page, snippet}]}", r.status_code == 200 and "40%" in j["answer"] and "[Page" not in j["answer"]
      and j["sources"] and j["sources"][0]["page"] == 2 and j["sources"][0]["snippet"])
before = CALLS["model"]
r = client.post("/api/ask", json={"doc_id": doc_id, "question": "What is the capital of France?"}); j = r.get_json()
check("ask: out-of-scope question refused without calling the model", j["sources"] == [] and CALLS["model"] == before)
check("ask: empty question -> 400", client.post("/api/ask", json={"doc_id": doc_id, "question": "   "}).status_code == 400)
check("ask: too long question -> 400", client.post("/api/ask", json={"doc_id": doc_id, "question": "x" * 501}).status_code == 400)

# ---- unknown document / bad input
for path, payload in [("/api/summarize", {"doc_id": "nope"}), ("/api/quiz", {}), ("/api/ask", {"doc_id": "../../etc", "question": "hi"})]:
    r = client.post(path, json=payload)
    check(f"{path}: unknown/invalid doc_id -> 404 with {{error}}", r.status_code == 404 and "error" in r.get_json())
check("wrong method -> JSON error", client.get("/api/ask").get_json().get("error") == "Method not allowed.")

# ---- AI failures never leak details
def boom(*a, **k): raise RuntimeError("secret provider details sk-123")
ai_generation._chat = studypilot_api._chat = boom
r = client.post("/api/ask", json={"doc_id": doc_id, "question": "What is the final exam?"})
check("AI failure -> 502 with a safe message (no details leaked)", r.status_code == 502 and "sk-123" not in r.get_data(as_text=True))
ai_generation._chat = studypilot_api._chat = fake_model

# ---- rate limiting
backend.reset_rate_limits()
codes = [client.post("/api/ask", json={"doc_id": doc_id, "question": "What is the final exam?"}).status_code for _ in range(22)]
check("rate limit: 21st AI request in a minute -> 429", codes[:20] == [200] * 20 and codes[20] == 429)
backend.reset_rate_limits()
codes = [upload(make_pdf(1)).status_code for _ in range(12)]
check("rate limit: 11th upload in a minute -> 429", codes[10] == 429)

print(f"\nAll {passed} backend tests passed.")
