# StudyPilot - complete project

Upload a lecture PDF -> get a summary, an MCQ quiz, and answers to your questions with the page they came from.

```
studypilot/
  frontend/            website (Individual 3)
  backend/
    app.py             Flask server + API (Individual 4: integration)
    pdf_processing.py  text extraction and chunking (Individual 1)
    ai_generation.py   summary, MCQs, grounded Q&A with RAG (Individual 2)
    studypilot_api.py  converts AI output to the JSON the website expects (Individual 2)
    test_backend.py    28 backend tests (no key needed)
    test_offline.py    15 AI-module tests (no key needed)
    requirements.txt
  Procfile  Dockerfile  .env.example  .gitignore
```

## Run locally (Windows PowerShell)

```powershell
cd backend
pip install -r requirements.txt
$env:OPENAI_API_KEY = Read-Host "Paste key"
$env:OPENAI_BASE_URL = "https://api.groq.com/openai/v1"     # only for Groq; skip for OpenAI
$env:STUDYPILOT_MODEL = "openai/gpt-oss-20b"                # use a model name your provider offers
python app.py
```
Open http://127.0.0.1:5000

## Tests (no API key, no internet)

```powershell
cd backend
python test_backend.py     # 28 tests: website, upload checks, API shapes, caching, limits, errors, headers
python test_offline.py     # 15 tests: retrieval, refusals, MCQ parsing, page checks, adapters
```

## API (the website depends on these exact shapes)

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/upload` | multipart `file` (PDF) | `{doc_id, filename, pages}` |
| `POST /api/summarize` | `{doc_id}` | `{summary, key_points[]}` |
| `POST /api/quiz` | `{doc_id, count}` | `{questions:[{question, options[4], answer 0-3, explanation, page, topic}]}` |
| `POST /api/ask` | `{doc_id, question}` | `{answer, sources:[{page, snippet}]}` |
| `GET /healthz` | - | `{status:"ok"}` |

Every error is a non-200 status with `{"error": "clear message"}`; the website shows the message.

## Deployment checklist (Individual 5)

1. Start command (see `Procfile` / `Dockerfile`):
   `cd backend && gunicorn app:app --workers 1 --threads 4 --timeout 600 --bind 0.0.0.0:$PORT`
   - **One worker on purpose**: lectures are kept in memory, so every request must reach the same process.
   - **Long timeout**: a long lecture needs several model calls; the summary is cached per lecture after the first time.
2. Set the environment variables on the server (see `.env.example`). The key is never in the code or in Git.
3. Behind a cloud load balancer set `TRUST_PROXY=1` so rate limiting sees the real client IP, and serve over HTTPS.
4. Do not enable Flask debug mode in production (it is off unless `FLASK_DEBUG=1`).
5. After deploying: open the site, upload a PDF, test Summary, Quiz, Ask AI, and take screenshots (check the screenshots do not show any key).

## Security measures in the backend

| Measure | Where |
|---|---|
| API key only from environment variables; never returned or logged | `ai_generation.py`, `app.py` |
| Upload checks: .pdf name, PDF signature, size limit (20 MB), page limit (300), password-protected PDFs refused | `/api/upload` |
| PDFs are read from memory; nothing from users is written to disk | `extract_pages` |
| Rate limiting per IP (10 uploads and 20 AI requests per minute) protects the AI quota | `rate_limited` |
| Input limits: question max 500 characters, quiz count 1-10, strict `doc_id` format | endpoints |
| Provider errors are logged on the server; users get a safe message (no keys, no stack traces) | `run_ai` |
| Security headers (`nosniff`, `X-Frame-Options: DENY`, `no-referrer`), `no-store` for API responses | `security_headers` |
| Static files served only from the frontend folder (path traversal tested) | `/static/<path>` |
| Memory protection: at most 50 lectures, each expires after 2 hours | `get_doc`, `upload` |
| Prompts tell the model to use only the lecture text (limits prompt injection from PDF content) | `ai_generation.py` |

## Known limitations

- Lectures live in memory: they disappear when the server restarts, and the app cannot run on several workers.
  A database would be the next step. Quiz scores are stored in the browser only.
- Image-only (scanned) PDFs have no text and are refused; there is no OCR.
- Retrieval is keyword based; a question that shares no words with the lecture is refused.
- Free AI plans limit tokens per minute, so the first summary of a long lecture can take several minutes.
