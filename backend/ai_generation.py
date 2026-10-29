"""
StudyPilot AI Generation & RAG
------------------------------
Consumes the chunks.json format produced by the PDF extraction teammate:
[
  {"chunk_id": 1, "page": 1, "text": "..."},
  ...
]

Features:
- Lecture summarization (map-reduce for longer lectures)
- Grounded MCQ generation with answer and explanation
- Question answering with lightweight lexical retrieval (RAG)
- Page references in answers and questions
- Refusal when the retrieved lecture content does not support an answer

Setup:
    pip install -r requirements.txt
    # Windows PowerShell:
    $env:OPENAI_API_KEY="your_api_key_here"
    # macOS/Linux:
    export OPENAI_API_KEY="your_api_key_here"

Run:
    python demo.py
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from openai import OpenAI


DEFAULT_MODEL = os.getenv("STUDYPILOT_MODEL", "gpt-4o-mini")
DEFAULT_CHUNKS_PATH = Path(__file__).with_name("chunks.json")
MIN_RETRIEVAL_SCORE = 0.02
MIN_TERM_COVERAGE = 0.5  # at least half of the question keywords must appear in a chunk


class StudyPilotError(RuntimeError):
    """Base exception for StudyPilot AI errors."""


class MissingAPIKeyError(StudyPilotError):
    """Raised when OPENAI_API_KEY is not configured."""


def _clean_text(text: str) -> str:
    """Repair a PDF-extraction artifact where a number is split by a space, e.g. '1 5%' -> '15%'."""
    return re.sub(r"(?<=\d) (?=\d+\s?%)", "", text).strip()


def load_chunks(source: str | Path | list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Load and validate lecture chunks from a JSON file or an in-memory list."""
    if source is None:
        source = DEFAULT_CHUNKS_PATH

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(
                f"Chunks file not found: {path}. Ask the PDF-processing teammate for chunks.json."
            )
        with path.open("r", encoding="utf-8") as file:
            chunks = json.load(file)
    else:
        chunks = source

    if not isinstance(chunks, list):
        raise ValueError("chunks.json must contain a JSON list.")

    valid = []
    for index, item in enumerate(chunks, start=1):
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        valid.append({
            "chunk_id": item.get("chunk_id", index),
            "page": item.get("page", "unknown"),
            "text": _clean_text(str(item["text"])),
        })

    if not valid:
        raise ValueError("No non-empty text chunks were found.")
    return valid


def _client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise MissingAPIKeyError(
            "OPENAI_API_KEY is missing. Set it as an environment variable before using AI functions."
        )
    return OpenAI()


TPM_BUDGET = int(os.getenv("STUDYPILOT_TPM", "6000"))   # tokens/minute we allow ourselves (free tiers ~8000)
MAX_PROMPT_CHARS = int(os.getenv("STUDYPILOT_MAX_CHARS", "9000"))  # ~2.5k tokens per request
_usage: list[tuple[float, int]] = []


_usage_lock = threading.Lock()


def _wait_for_budget(estimated_tokens: int) -> None:
    """Pause so we stay under the provider's tokens-per-minute limit (safe with several server threads)."""
    while True:
        with _usage_lock:
            now = time.time()
            _usage[:] = [(t, n) for t, n in _usage if now - t < 60]
            used = sum(n for _, n in _usage)
            if not _usage or used + estimated_tokens <= TPM_BUDGET:
                _usage.append((now, estimated_tokens))
                return
            pause = max(1.0, 60 - (now - _usage[0][0]) + 0.5)
        time.sleep(pause)


def _chat(system_prompt: str, user_prompt: str, model: str | None = None,
          temperature: float = 0.2) -> str:
    """Call the configured chat model (with rate-limit pacing and retries)."""
    estimate = (len(system_prompt) + len(user_prompt)) // 3 + 800
    chosen = model or DEFAULT_MODEL
    extra = {}
    # gpt-oss models are "reasoning" models: keep thinking short so the reply text is not starved.
    if "gpt-oss" in chosen:
        extra["reasoning_effort"] = os.getenv("STUDYPILOT_REASONING", "low")

    finish = None
    for attempt in range(6):
        _wait_for_budget(estimate)
        try:
            response = _client().chat.completions.create(
                model=chosen,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **extra,
            )
        except Exception as exc:  # noqa: BLE001
            status = getattr(exc, "status_code", None)
            if status == 429 and attempt < 5:
                wait = 15 * (attempt + 1)
                print(f"[rate limit] waiting {wait}s then retrying...")
                time.sleep(wait)
                continue
            if status == 413:
                raise StudyPilotError(
                    "Request is too large for the model's per-minute token limit. "
                    "Lower STUDYPILOT_MAX_CHARS or use a model/plan with a higher limit."
                ) from exc
            raise
        choice = response.choices[0]
        content = choice.message.content
        finish = getattr(choice, "finish_reason", None)
        if content and content.strip():
            return content.strip()
        if attempt >= 2:
            break
        print(f"[empty reply, finish_reason={finish}] retrying...")
        time.sleep(2)
    raise StudyPilotError(
        f"The AI model returned an empty response (finish_reason={finish}). "
        "Try another model, e.g. set STUDYPILOT_MODEL=openai/gpt-oss-120b."
    )


STOPWORDS = set("""a an the is are was were be been being am do does did of in on at to for from by with
and or but if then so as it its this that these those what which who whom whose when where why how can could
should would will shall may might must not no yes about into over under between than there their they them
he she his her we our you your i me my us tell explain define describe give example examples""".split())


def _stem(word: str) -> str:
    """Very light stemmer so 'agents' matches 'agent' and 'learning' matches 'learn'."""
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def _words(text: str) -> list[str]:
    """Tokenize (English + Arabic), drop stop words, apply light stemming."""
    tokens = [t.strip("-'") for t in re.findall(r"[A-Za-z0-9_'-]+|[\u0600-\u06FF]+", text.lower())]
    return [_stem(t) for t in tokens if t and t not in STOPWORDS]


def retrieve_chunks(question: str, chunks: list[dict[str, Any]] | None = None,
                    top_k: int = 5) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant chunks using a small TF-IDF-style lexical ranker.
    This requires no vector database or embedding service. For a small class project,
    it is an easy-to-run baseline; it can later be replaced with embeddings.
    """
    if not question.strip():
        raise ValueError("Question cannot be empty.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    chunks = load_chunks(chunks) if chunks is None else load_chunks(chunks)
    query_terms = set(_words(question))
    if not query_terms:
        return []

    tokenized = [_words(c["text"]) for c in chunks]
    doc_freq = Counter(term for terms in tokenized for term in set(terms))
    n_docs = len(chunks)
    scored = []

    for chunk, terms in zip(chunks, tokenized):
        counts = Counter(terms)
        length_norm = math.sqrt(max(len(terms), 1))
        score = 0.0
        for term in query_terms:
            if counts[term]:
                idf = math.log(1 + (n_docs + 1) / (doc_freq[term] + 1))
                score += (1 + math.log(counts[term])) * idf / length_norm
        matched = sum(1 for term in query_terms if counts[term])
        coverage = matched / len(query_terms)
        # Require that a meaningful share of the question's key terms appear in the chunk.
        if score > 0 and coverage >= MIN_TERM_COVERAGE:
            scored.append((score * (0.5 + coverage), chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or scored[0][0] < MIN_RETRIEVAL_SCORE:
        return []
    return [chunk for _, chunk in scored[:top_k]]


def _context(chunks: Iterable[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[Source chunk {c['chunk_id']} | page {c['page']}]\n{c['text']}"
        for c in chunks
    )


PAGE_REF = re.compile(
    r"(?i)\b(pages?|pp?\.)\s*(\d+(?:\s*[-\u2010-\u2015]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-\u2010-\u2015]\s*\d+)?)*)"
)


def _strip_invalid_page_refs(text: str, max_page: int) -> str:
    """Models sometimes invent page numbers. Replace any page reference that points past the last real page."""
    def fix(match: re.Match) -> str:
        numbers = [int(n) for n in re.findall(r"\d+", match.group(2))]
        return "page ref. unverified" if any(n > max_page for n in numbers) else match.group(0)
    return PAGE_REF.sub(fix, text)


def _expand_pages(spec: str, limit: int = 60) -> set[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if len(nums) == 2 and nums[0] <= nums[1] <= nums[0] + limit:
            pages.update(range(nums[0], nums[1] + 1))
        else:
            pages.update(nums)
    return pages


def _verify_page_refs(summary: str, chunks: list[dict[str, Any]], threshold: float = 0.25) -> str:
    """
    Check every [p. N] reference against the lecture: the words next to the reference must actually
    appear on the cited page(s). If not, point to the best-matching page marked with '?'
    (student should verify), or flag it as unverified.
    """
    page_terms: dict[int, set[str]] = {}
    for c in chunks:
        if isinstance(c["page"], int):
            page_terms.setdefault(c["page"], set()).update(_words(c["text"]))

    def score(terms: set[str], pages: Iterable[int]) -> float:
        known = set().union(*(page_terms.get(p, set()) for p in pages))
        return len(terms & known) / max(len(terms), 1)

    fixed_lines = []
    for line in summary.splitlines():
        pieces, last = [], 0
        for match in PAGE_REF.finditer(line):
            segment = line[last:match.start()]
            terms = set(_words(PAGE_REF.sub("", segment)))
            replacement = match.group(0)
            claimed = _expand_pages(match.group(2))
            if len(terms) >= 2 and claimed and score(terms, claimed) < threshold:
                # Search every single page and every pair of neighbouring pages for the best match.
                windows = [(p,) for p in page_terms] + [(p, p + 1) for p in page_terms if p + 1 in page_terms]
                best = max(windows, key=lambda w: (score(terms, w), -len(w)))
                matched = score(terms, best) * len(terms)
                top = score(terms, best)
                if (top >= 0.8 and matched >= 2) or (top >= 0.6 and matched >= 4):
                    label = f"{best[0]}" if len(best) == 1 else f"{best[0]}-{best[1]}"
                    replacement = f"p. {label}?"
                else:
                    replacement = "page ref. unverified"
            pieces.append(segment + replacement)
            last = match.end()
        pieces.append(line[last:])
        fixed_lines.append("".join(pieces))
    return "\n".join(fixed_lines)


def _group_by_chars(items: list[str], limit: int) -> list[list[str]]:
    groups, current, size = [], [], 0
    for item in items:
        length = len(item) + 10
        if current and size + length > limit:
            groups.append(current)
            current, size = [], 0
        current.append(item)
        size += length
    if current:
        groups.append(current)
    return groups


def summarize_lecture(source: str | Path | list[dict[str, Any]] | None = None,
                      detail: str = "medium", model: str | None = None,
                      verbose: bool = True) -> str:
    """
    Summarize the complete lecture with a hierarchical map-reduce:
    1) summarize batches of chunks (each request is kept under MAX_PROMPT_CHARS),
    2) merge partial summaries in rounds until they fit in one request,
    3) write the final study notes.
    detail: 'short', 'medium', or 'detailed'.
    """
    if detail not in {"short", "medium", "detailed"}:
        raise ValueError("detail must be 'short', 'medium', or 'detailed'.")

    part_words = {"short": 100, "medium": 160, "detailed": 260}[detail]
    final_words = {"short": 300, "medium": 600, "detailed": 1000}[detail]
    chunks = load_chunks(source)

    # --- Map: summarize batches ---
    batches = _group_by_chars([_context([c]) for c in chunks], MAX_PROMPT_CHARS)
    partials = []
    for i, batch in enumerate(batches, start=1):
        if verbose:
            print(f"  summarizing part {i}/{len(batches)} ...", flush=True)
        prompt = f"""Summarize this part of a lecture for a university student in at most {part_words} words.
Keep key definitions, concepts, examples, comparisons, and formulas, with page references like [p. 4].
Do not add facts that are not in the source. If a detail is unclear, omit it.

LECTURE TEXT:
{chr(10).join(batch)}"""
        partials.append(_chat(
            "You are StudyPilot, a careful study assistant. Use only the supplied lecture text.",
            prompt, model=model))

    # --- Reduce: merge in rounds so no request gets too big ---
    while len(partials) > 1 and sum(len(p) for p in partials) > MAX_PROMPT_CHARS:
        groups = _group_by_chars(partials, MAX_PROMPT_CHARS)
        if len(groups) >= len(partials):
            break
        if verbose:
            print(f"  merging {len(partials)} notes into {len(groups)} ...", flush=True)
        merged = []
        for group in groups:
            if len(group) == 1:
                merged.append(group[0])
                continue
            merged.append(_chat(
                "You are an accurate academic note editor. Never invent lecture content.",
                "Merge these notes into one set of notes of at most 250 words. Keep distinct key points "
                "and page references. Add nothing new.\n\n" + "\n\n---\n\n".join(group),
                model=model))
        partials = merged

    max_page = max((c["page"] for c in chunks if isinstance(c["page"], int)), default=10**9)

    if len(partials) == 1:
        return _verify_page_refs(_strip_invalid_page_refs(partials[0], max_page), chunks)

    if verbose:
        print("  writing final summary ...", flush=True)
    final_prompt = (
        f"Combine the following partial notes into one coherent lecture summary of about {final_words} words. "
        "Remove repetition but keep all distinct important points. Use headings and bullets. "
        "Do not introduce facts absent from these notes. Keep page references exactly as given; never invent or extend page numbers.\n\n"
        + "\n\n---\n\n".join(partials)
    )
    final = _chat("You are an accurate academic note editor. Never invent lecture content.",
                  final_prompt, model=model)
    return _verify_page_refs(_strip_invalid_page_refs(final, max_page), chunks)


def generate_mcqs(source: str | Path | list[dict[str, Any]] | None = None,
                  num_questions: int = 5, topic: str | None = None,
                  model: str | None = None) -> list[dict[str, Any]]:
    """
    Generate multiple-choice questions grounded in the lecture.
    Returns a list with question, options (A-D), correct_answer, explanation, topic, source_pages.
    """
    if not 1 <= num_questions <= 20:
        raise ValueError("num_questions must be between 1 and 20.")

    chunks = load_chunks(source)
    if topic:
        relevant = retrieve_chunks(topic, chunks, top_k=min(max(num_questions * 2, 5), 12))
        selected = relevant or chunks[:12]
    else:
        # Spread chunks across the lecture to cover more than its opening pages.
        step = max(1, len(chunks) // min(num_questions * 2, 12))
        selected = chunks[::step][:12]

    prompt = f"""Create exactly {num_questions} university-level multiple-choice questions using ONLY the lecture context.
Return valid JSON only, with this schema:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": {{"A": "option", "B": "option", "C": "option", "D": "option"}},
      "correct_answer": "A",
      "explanation": "Brief explanation supported by the lecture",
      "topic": "Short topic name (2-4 words) the question belongs to, e.g. Reflexion",
      "source_pages": [1]
    }}
  ]
}}
Rules:
- Exactly four options, A-D, and exactly one best correct answer.
- Distractors should be plausible but clearly incorrect based on the supplied source.
- The explanation and correct answer must be supported by the context.
- Do not ask about information missing from the context.
- Use page numbers from the source labels.
- No markdown fences.

LECTURE CONTEXT:
{_context(selected)}"""

    raw = _chat(
        "You generate grounded educational assessments. Follow the requested JSON schema exactly. Never invent lecture facts.",
        prompt, model=model, temperature=0.1
    )
    try:
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        payload = json.loads(raw)
        questions = payload["questions"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise StudyPilotError(f"Could not parse MCQ JSON returned by the model: {exc}") from exc

    if not isinstance(questions, list) or len(questions) != num_questions:
        raise StudyPilotError("The model did not return the requested number of questions.")

    cleaned = []
    for item in questions:
        options = item.get("options", {})
        answer = str(item.get("correct_answer", "")).strip().upper()
        if not isinstance(options, dict) or set(options.keys()) < {"A", "B", "C", "D"}:
            raise StudyPilotError("A generated question is missing one or more A-D options.")
        if answer not in {"A", "B", "C", "D"}:
            raise StudyPilotError("A generated question has an invalid correct_answer.")
        cleaned.append({
            "question": str(item.get("question", "")).strip(),
            "options": {letter: str(options[letter]) for letter in "ABCD"},
            "correct_answer": answer,
            "explanation": str(item.get("explanation", "")).strip(),
            "topic": str(item.get("topic", "")).strip() or "General",
            "source_pages": item.get("source_pages", []),
        })
    return cleaned


def answer_question(question: str,
                    source: str | Path | list[dict[str, Any]] | None = None,
                    top_k: int = 5, model: str | None = None) -> dict[str, Any]:
    """
    Answer a question from retrieved lecture chunks only.
    Returns {'answer': ..., 'source_pages': [...], 'source_chunks': [...]}.
    If evidence is insufficient, the model is instructed to say so.
    """
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    chunks = load_chunks(source)
    retrieved = retrieve_chunks(question, chunks, top_k=top_k)
    if not retrieved:
        return {
            "answer": "I could not find enough relevant information in the uploaded lecture to answer this reliably.",
            "source_pages": [],
            "source_chunks": [],
        }

    prompt = f"""Answer the student's question using ONLY the lecture context below.
Rules:
1. Every sentence you write must be directly supported by the context. Do NOT add general knowledge, examples,
   advantages/disadvantages, or explanations that are not written in the context, even if they are true.
2. If the context only names a concept without explaining it, say what the lecture states and add:
   "The lecture does not give more detail."
3. If the context does not contain enough evidence, reply exactly:
   "The lecture does not provide enough information to answer this reliably."
4. Cite the supporting page after each statement in exactly this format: [Page 4] or [Page 4-5].
   Never write "Source chunk" and never cite a page that is not in the context.
QUESTION: {question}

LECTURE CONTEXT:
{_context(retrieved)}"""

    answer = _chat(
        "You are StudyPilot, a grounded lecture Q&A assistant. Accuracy is more important than sounding confident. Never make up facts or citations.",
        prompt, model=model, temperature=0.0
    )
    retrieved_pages = sorted({c["page"] for c in retrieved if c["page"] != "unknown"})
    return {
        "answer": answer,
        "source_pages": _cited_pages(answer, retrieved_pages),
        "retrieved_pages": retrieved_pages,
        "source_chunks": [c["chunk_id"] for c in retrieved],
    }


def _cited_pages(answer: str, retrieved_pages: list) -> list:
    """Pages the answer actually cites (limited to retrieved pages); fall back to all retrieved pages."""
    cited: set[int] = set()
    for m in re.finditer(r"(?i)pages?\s*(\d+)(?:\s*[-\u2010-\u2015]\s*(\d+))?", answer):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start <= end <= start + 20:
            cited.update(range(start, end + 1))
    pages = [p for p in retrieved_pages if p in cited]
    return pages or list(retrieved_pages)


if __name__ == "__main__":
    print("StudyPilot AI module loaded.")
    print("Try: from ai_generation import summarize_lecture, generate_mcqs, answer_question")
