# StudyPilot — Frontend (Person 3)

Structure:
  index.html
  static/css/style.css
  static/js/app.js

## For Person 4 (Backend)
Flask: serve this folder as-is.
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    @app.route("/")
    def home(): return send_from_directory(".", "index.html")

Endpoints (all POST, JSON unless stated). On error return a non-200 status and {"error": "message"}.
  /api/upload     multipart/form-data, field "file"      -> {doc_id, filename, pages}
  /api/summarize  {doc_id}                               -> {summary, key_points:[..]}
  /api/quiz       {doc_id, count}                        -> {questions:[{question, options:[4], answer:0-3, explanation, page, topic}]}
  /api/ask        {doc_id, question}                     -> {answer, sources:[{page, snippet}]}

If the backend is on another domain: set CFG.API at the top of static/js/app.js and enable CORS.

## Demo mode
ON automatically when index.html is opened as a local file, or with ?demo=1 in the URL.
OFF on the deployed site (talks to the real backend).
