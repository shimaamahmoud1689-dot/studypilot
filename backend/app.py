"""
StudyPilot backend (Flask) - Individual 4: integration.

Connects the three parts of the project:
  * Individual 1  -> pdf_processing.py   (text extraction + chunking with page numbers)
  * Individual 2  -> ai_generation.py + studypilot_api.py   (summary, MCQs, grounded Q&A)
  * Individual 3  -> ../frontend         (the website; its JSON shapes are fixed)

Endpoints (JSON shapes are exactly what the frontend expects):
  POST /api/upload     (multipart file)              -> {doc_id, filename, pages}
  POST /api/summarize  {doc_id}                      -> {summary, key_points[]}
  POST /api/quiz       {doc_id, count}               -> {questions:[{question, options[4], answer 0-3,
                                                                     explanation, page, topic}]}
  POST /api/ask        {doc_id, question}            -> {answer, sources:[{page, snippet}]}
  GET  /healthz                                      -> {status: "ok"}
Errors: non-200 status with {"error": "clear message"}.

Run locally:   python app.py            (needs the environment variables below)
Production:    gunicorn app:app --workers 1 --threads 4 --timeout 600 --bind 0.0.0.0:$PORT

Environment variables (never put the key in code):
  OPENAI_API_KEY, OPENAI_BASE_URL (optional), STUDYPILOT_MODEL (optional)
  MAX_UPLOAD_MB (20), MAX_PAGES (300), TRUST_PROXY (set to 1 behind a cloud load balancer)
"""
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque

import pymupdf
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

import pdf_processing as p1
import studypilot_api as ai_api
from ai_generation import MissingAPIKeyError, StudyPilotError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "300"))
MAX_DOCS = 50                 # lectures kept in memory
DOC_TTL = 2 * 60 * 60         # seconds a lecture stays available
MAX_QUESTION_CHARS = 500
RATE_LIMITS = {"upload": (10, 60), "ai": (20, 60)}   # (requests, per seconds) for each client IP

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
if os.getenv("TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

DOCS: dict[str, dict] = {}    # doc_id -> {filename, pages, chunks, created, summary, lock}
_docs_lock = threading.Lock()
_hits: dict[tuple, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


# ----------------------------------------------------------------- helpers
def err(message: str, status: int = 400):
    return jsonify(error=message), status


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def reset_rate_limits() -> None:
    with _hits_lock:
        _hits.clear()


def rate_limited(bucket: str) -> bool:
    limit, window = RATE_LIMITS[bucket]
    now, key = time.time(), (bucket, request.remote_addr or "?")
    with _hits_lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
    return False


def get_doc():
    """Return the lecture for the request's doc_id, or None (unknown or expired)."""
    doc_id = str(body().get("doc_id", ""))
    if not re.fullmatch(r"[0-9a-f]{12}", doc_id):
        return None
    with _docs_lock:
        for key in [k for k, d in DOCS.items() if time.time() - d["created"] > DOC_TTL]:
            del DOCS[key]
        return DOCS.get(doc_id)


def extract_pages(data: bytes) -> list[dict]:
    """Individual 1's cleaning applied to a PDF held in memory (nothing is written to disk)."""
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass:
            raise ValueError("This PDF is password-protected.")
        return [{"page": n, "text": p1.clean_text(page.get_text())} for n, page in enumerate(pdf, start=1)]


def run_ai(fn):
    """Call an AI function and turn every failure into the {"error": ...} format the frontend shows."""
    try:
        return jsonify(fn())
    except MissingAPIKeyError:
        app.logger.error("OPENAI_API_KEY is not set on the server")
        return err("The AI service is not configured on the server.", 503)
    except ValueError as exc:
        return err(str(exc), 400)
    except StudyPilotError as exc:
        return err(str(exc), 502)
    except Exception:  # provider down, bad key, rate limit...  details go to the log, not to the user
        app.logger.exception("AI call failed")
        return err("The AI service is unavailable or busy right now. Please try again in a minute.", 502)


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(413)
def too_large(_):
    return err(f"File is too large (limit {MAX_UPLOAD_MB} MB).", 413)


@app.errorhandler(404)
def not_found(_):
    return err("Not found.", 404) if request.path.startswith("/api/") else ("Not found", 404)


@app.errorhandler(405)
def bad_method(_):
    return err("Method not allowed.", 405)


@app.errorhandler(500)
def server_error(_):
    return err("Unexpected server error.", 500)


# ----------------------------------------------------------------- website
@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/static/<path:path>")
def assets(path):
    return send_from_directory(os.path.join(ROOT, "static"), path)


@app.get("/healthz")
def health():
    return jsonify(status="ok")


# ----------------------------------------------------------------- API
@app.post("/api/upload")
def upload():
    if rate_limited("upload"):
        return err("Too many uploads. Please wait a minute.", 429)
    f = request.files.get("file")
    if not f or not (f.filename or "").lower().endswith(".pdf"):
        return err("Please upload a PDF file.")
    data = f.read()
    if b"%PDF" not in data[:1024]:
        return err("This file is not a valid PDF.")
    try:
        pages = extract_pages(data)
    except ValueError as exc:
        return err(str(exc))
    except Exception:
        app.logger.exception("PDF could not be read")
        return err("This file could not be read as a PDF.")
    if len(pages) > MAX_PAGES:
        return err(f"This PDF has too many pages (limit {MAX_PAGES}).")
    chunks = p1.chunk_pages(pages)
    if not chunks:
        return err("No text found in this PDF. It may be scanned (images only).")

    doc_id = uuid.uuid4().hex[:12]
    filename = re.sub(r"[\x00-\x1f]", "", os.path.basename(f.filename))[:120]
    with _docs_lock:
        while len(DOCS) >= MAX_DOCS:
            DOCS.pop(min(DOCS, key=lambda k: DOCS[k]["created"]))
        DOCS[doc_id] = {"filename": filename, "pages": len(pages), "chunks": chunks,
                        "created": time.time(), "summary": None, "lock": threading.Lock()}
    return jsonify(doc_id=doc_id, filename=filename, pages=len(pages))


@app.post("/api/summarize")
def summarize():
    if rate_limited("ai"):
        return err("Too many requests. Please wait a minute.", 429)
    doc = get_doc()
    if not doc:
        return err("Document not found. Please upload it again.", 404)

    def work():
        with doc["lock"]:                       # two clicks must not run the summary twice
            if doc["summary"] is None:
                doc["summary"] = ai_api.summary_response(doc["chunks"])
            return doc["summary"]
    return run_ai(work)


@app.post("/api/quiz")
def quiz():
    if rate_limited("ai"):
        return err("Too many requests. Please wait a minute.", 429)
    doc = get_doc()
    if not doc:
        return err("Document not found. Please upload it again.", 404)
    try:
        count = int(body().get("count", 5))
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 10))
    return run_ai(lambda: ai_api.quiz_response(doc["chunks"], count))


@app.post("/api/ask")
def ask():
    if rate_limited("ai"):
        return err("Too many requests. Please wait a minute.", 429)
    doc = get_doc()
    if not doc:
        return err("Document not found. Please upload it again.", 404)
    question = str(body().get("question", "")).strip()
    if not question:
        return err("Please type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        return err(f"The question is too long (max {MAX_QUESTION_CHARS} characters).")
    return run_ai(lambda: ai_api.ask_response(doc["chunks"], question))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG") == "1")
