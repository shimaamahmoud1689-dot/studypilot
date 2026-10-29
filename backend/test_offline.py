"""Offline tests: no API key needed. Run:  python test_offline.py
Tests retrieval + JSON validation + the refusal path using a fake model."""
import json, sys, types
try:
    import openai  # noqa
except ImportError:
    sys.modules["openai"] = types.SimpleNamespace(OpenAI=object)  # allow testing without the SDK
import ai_generation as ai

def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name

# 1) Retrieval finds the right page
r = ai.retrieve_chunks("Who is the instructor?", "chunks.json")
check("retrieval: instructor -> page 2", r and r[0]["page"] == 2)

# 2) Out-of-lecture question => no chunks => refusal WITHOUT calling the model
ai._chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("model must not be called"))
res = ai.answer_question("What is the capital of France?", "chunks.json")
check("refusal: unrelated question", res["source_pages"] == [] and "not find enough" in res["answer"])

# 3) MCQ parsing with markdown fences + validation
fake = {"questions": [{"question": "Q?", "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                       "correct_answer": "b", "explanation": "e", "source_pages": [6]}]}
ai._chat = lambda *a, **k: "```json\n" + json.dumps(fake) + "\n```"
q = ai.generate_mcqs("chunks.json", num_questions=1)
check("mcq: fenced JSON parsed, answer normalized to 'B'", q[0]["correct_answer"] == "B")

# 4) Bad inputs
for bad, name in [(lambda: ai.answer_question("  ", "chunks.json"), "empty question"),
                  (lambda: ai.generate_mcqs("chunks.json", num_questions=0), "num_questions=0"),
                  (lambda: ai.load_chunks("missing.json"), "missing file")]:
    try: bad(); ok = False
    except (ValueError, FileNotFoundError): ok = True
    check("error handling: " + name, ok)
# 5) Invented page numbers (beyond the last real page) are flagged in summaries
cleaned = ai._strip_invalid_page_refs("FIPA (p. 163-168). Agents (p. 12-15).", 150)
check("summary: invalid page refs flagged, valid kept", "unverified" in cleaned and "p. 12-15" in cleaned)
# 6) In-range but WRONG page refs are corrected/flagged by checking the cited page's text
ch = ai.load_chunks("chunks.json")
bad = ai._verify_page_refs("Examples: Toolformer, Gorilla [p. 125-126].", ch)
good = ai._verify_page_refs("Chess is an example of a discrete environment [p. 71].", ch)
check("page check: wrong page corrected to 108/109 with '?'", "?" in bad and ("108" in bad or "109" in bad))
check("page check: correct page left unchanged", "[p. 71]" in good)
# 7) PDF artifact "1 5%" is repaired so grading weights are not misread
fixed = ai.load_chunks([{"chunk_id": 1, "page": 38, "text": "1 5% Programming 20% Midterm 40% Final 1 5% Participation"}])[0]["text"]
check("text cleaning: '1 5%' -> '15%', other numbers untouched", "15% Programming" in fixed and "20% Midterm" in fixed and "40% Final" in fixed)
# 8) source_pages lists only pages the answer cites (e.g. "[Page 96–97]"), not every retrieved page
check("cited pages: only the cited ones are returned",
      ai._cited_pages("Reflexion ... [Page 96\u201397].", [7, 31, 96, 97, 140]) == [96, 97])
check("cited pages: falls back to retrieved pages if none cited",
      ai._cited_pages("No citations here.", [3, 4]) == [3, 4])
# 9) API adapter: shapes expected by the website
import studypilot_api as api
ch_all = ai.load_chunks("chunks.json")
def _fake(system, user, model=None, temperature=0.2):
    if "multiple-choice" in user:
        return json.dumps({"questions": [{"question": "Q?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                                          "correct_answer": "C", "explanation": "e", "topic": "Reflexion", "source_pages": [96, 9999]}]})
    if "Answer the student" in user:
        return "Reflexion lets agents reflect on feedback. [Page 96]"
    if "overview" in user:
        return "A short plain overview."
    return "- **Reflexion** lets agents learn from feedback [p. 96].\n- Agents can be reactive or deliberative [p. 128]."
ai._chat = api._chat = _fake
q = api.quiz_response(ch_all, 1)["questions"][0]
check("api quiz: options list of 4, answer index, page, topic",
      q["options"] == ["a", "b", "c", "d"] and q["answer"] == 2 and q["page"] == 96 and q["topic"] == "Reflexion")
s = api.summary_response(ch_all)
check("api summary: plain text + key_points without markdown/page refs",
      s["summary"] == "A short plain overview." and s["key_points"][0] == "Reflexion lets agents learn from feedback.")
a = api.ask_response(ch_all, "What is Reflexion?")
check("api ask: sources=[{page, snippet}] and no page tags in the text",
      a["sources"] and a["sources"][0]["page"] == 96 and a["sources"][0]["snippet"] and "[Page" not in a["answer"])
print("\nAll offline tests passed.")
