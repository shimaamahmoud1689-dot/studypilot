"""
StudyPilot - API adapter (Individual 2).

Turns the output of ai_generation.py into the exact JSON shapes the website (frontend) expects,
so the Backend only has to call three functions:

    summary_response(chunks)            -> {"summary": str, "key_points": [str, ...]}
    quiz_response(chunks, count=5)      -> {"questions": [{question, options[4], answer 0-3,
                                                           explanation, page, topic}]}
    ask_response(chunks, question)      -> {"answer": str, "sources": [{"page": int, "snippet": str}]}

`chunks` is the list produced by the PDF-processing step: [{"chunk_id", "page", "text"}, ...]
Errors raise StudyPilotError / ValueError; the Flask route turns them into {"error": "..."}.
"""
from __future__ import annotations

import re
from typing import Any

from ai_generation import (StudyPilotError, _chat, answer_question, generate_mcqs,
                           summarize_lecture)

__all__ = ["summary_response", "quiz_response", "ask_response", "StudyPilotError"]

_PAGE_REF = re.compile(r"\s*[\[(]\s*(?:pages?|pp?\.)\s*[\d\s,\-\u2010-\u2015?]+[\])]", re.I)


def _plain(text: str) -> str:
    """Remove markdown markers and page references (the website shows plain text)."""
    text = _PAGE_REF.sub("", text)
    text = re.sub(r"[*_`]{1,3}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _key_points(notes: str, limit: int = 8) -> list[str]:
    points = []
    for line in notes.splitlines():
        if re.match(r"\s*([-*\u2022]|\d+\.)\s+", line):
            clean = _plain(re.sub(r"^\s*([-*\u2022]|\d+\.)\s+", "", line))
            if len(clean) >= 20:
                points.append(clean)
    if not points:  # no bullets: use the first sentences
        sentences = re.split(r"(?<=[.!?])\s+", _plain(notes))
        points = [s for s in sentences if len(s) >= 20]
    return points[:limit]


def summary_response(chunks: list[dict[str, Any]], detail: str = "short") -> dict[str, Any]:
    notes = summarize_lecture(chunks, detail=detail, verbose=False)
    points = _key_points(notes)
    try:
        overview = _plain(_chat(
            "You write short plain-text overviews of lecture notes. Use only the notes.",
            "Write a 3-4 sentence plain-text overview (no markdown, no lists, no page numbers) "
            "of these lecture notes:\n\n" + notes, temperature=0.1))
    except StudyPilotError:
        overview = " ".join(points[:3])
    return {"summary": overview or _plain(notes), "key_points": points}


def quiz_response(chunks: list[dict[str, Any]], count: int = 5) -> dict[str, Any]:
    count = max(1, min(int(count or 5), 20))
    default_page = next((c["page"] for c in chunks if isinstance(c["page"], int)), 1)
    valid_pages = {c["page"] for c in chunks}
    questions = []
    for item in generate_mcqs(chunks, num_questions=count):
        pages = [p for p in item["source_pages"] if isinstance(p, int) and p in valid_pages]
        questions.append({
            "question": item["question"],
            "options": [item["options"][letter] for letter in "ABCD"],
            "answer": "ABCD".index(item["correct_answer"]),
            "explanation": item["explanation"],
            "page": pages[0] if pages else default_page,
            "topic": item["topic"],
        })
    return {"questions": questions}


def ask_response(chunks: list[dict[str, Any]], question: str) -> dict[str, Any]:
    result = answer_question(question, chunks)
    by_id = {c["chunk_id"]: c for c in chunks}
    sources, seen = [], set()
    for chunk_id in result["source_chunks"]:           # best-ranked chunks first
        chunk = by_id.get(chunk_id)
        if chunk and chunk["page"] in result["source_pages"] and chunk["page"] not in seen:
            seen.add(chunk["page"])
            text = _plain(chunk["text"])
            sources.append({"page": chunk["page"], "snippet": text[:160] + ("..." if len(text) > 160 else "")})
    for page in result["source_pages"]:                 # cited page whose chunk was not matched above
        if page not in seen:
            sources.append({"page": page, "snippet": ""})
    return {"answer": _plain_answer(result["answer"]), "sources": sorted(sources, key=lambda s: s["page"])}


def _plain_answer(text: str) -> str:
    """Keep the answer readable as plain text; the page badges are shown from `sources`."""
    text = re.sub(r"\s*\[\s*Pages?\s*[\d\s,\-\u2010-\u2015]+\]", "", text, flags=re.I)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()
