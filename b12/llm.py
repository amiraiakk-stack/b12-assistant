"""LLM calls: turn B12 messages into dated tasks, and answer the parent's questions.

LLM_PROVIDER in .env picks the model: "claude" (Claude API, paid) or "ollama" (a free model
running on this computer through Ollama).
"""

import base64
import functools
import mimetypes
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

import anthropic
import httpx
from pydantic import BaseModel, Field
from pypdf import PdfReader

from .config import LLM_PROVIDER, MODEL, OLLAMA_MODEL, OLLAMA_URL, WEEKEND_DAYS


@functools.cache
def _claude() -> anthropic.Anthropic:
    return anthropic.Anthropic()

# Server-side fallback: if a request is declined, the API re-runs it on a fallback model.
FALLBACK_KWARGS = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


class Task(BaseModel):
    due_date: Optional[str] = Field(
        description="YYYY-MM-DD the task is due or the item must be brought; null if no date can be worked out"
    )
    kind: Literal["homework", "bring", "exam", "quiz", "project", "event", "uniform", "other"]
    subject: Optional[str] = Field(description="School subject, e.g. Math, Arabic, Science; null if none")
    title: str = Field(description="Short task in the language of the message")
    details: Optional[str] = Field(description="Pages, exercises, materials or other specifics")
    platform: Optional[Literal["B12", "Teams", "Kutobee", "Tamreen", "paper", "other"]] = Field(
        description="Where the work is done or submitted, if stated"
    )


class Extraction(BaseModel):
    tasks: list[Task]


EXTRACT_SYSTEM = """You read messages a school sends to a student through the B12 app: weekly plans, \
newsletters, reminders to bring things, homework notices, and notices about homework on Teams, \
Kutobee or Tamreen. Extract every actionable item for the student or parent as a task.

Resolve relative dates ("tomorrow", "next Sunday", a weekday name, a date range in a weekly plan) \
to an exact YYYY-MM-DD using the message's sent date and today's date. The school week runs \
Sunday to Thursday. A weekly plan usually lists work per day and subject: make one task per item. \
Skip greetings, general news and anything with no action. Return an empty list if nothing is actionable."""


def _attachment_block(path: str):
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or ""
    data = base64.standard_b64encode(p.read_bytes()).decode()
    if mime == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": data}}
    if mime in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
        return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
    return None


def _message_text(msg, today: date) -> str:
    return (
        f"Today is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"Source: {msg['source']}\nSent: {msg['sent_at'] or 'unknown'}\n"
        f"Title: {msg['title'] or ''}\n\n{msg['body'] or ''}"
    )


def _ollama_chat(system: str, text: str, schema: dict | None = None) -> str:
    body = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
        "stream": False,
        "options": {"temperature": 0},
    }
    if schema:
        body["format"] = schema
    response = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600)
    response.raise_for_status()
    return response.json()["message"]["content"]


def _pdf_text(path: str) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def extract_tasks(msg, today: date) -> list[Task]:
    if LLM_PROVIDER == "ollama":
        text = _message_text(msg, today)
        path = msg["attachment_path"]
        if path and path.lower().endswith(".pdf"):
            # Local models can't read PDFs directly, so pass the PDF's text.
            text += f"\n\nAttached file text:\n{_pdf_text(path)}"
        raw = _ollama_chat(EXTRACT_SYSTEM, text, Extraction.model_json_schema())
        return Extraction.model_validate_json(raw).tasks

    content = []
    if msg["attachment_path"]:
        block = _attachment_block(msg["attachment_path"])
        if block:
            content.append(block)
    content.append({"type": "text", "text": _message_text(msg, today)})
    response = _claude().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_format=Extraction,
        output_config={"effort": "medium"},
        **FALLBACK_KWARGS,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return []
    return response.parsed_output.tasks


def next_school_days(start: date, count: int) -> list[date]:
    days, d = [], start
    while len(days) < count:
        if d.weekday() not in WEEKEND_DAYS:
            days.append(d)
        d += timedelta(days=1)
    return days


ANSWER_SYSTEM = """You are a helpful assistant for a parent in Jordan. You answer questions about \
their son's school tasks, using only the task list you are given (taken from the school's B12 app). \
Reply in friendly Levantine Arabic, short and easy to read on WhatsApp: group by day, then subject, \
use simple bullet points and clear day names with dates. Put the day they asked about first, then \
add a short "للتذكير" part for the next school days. Say plainly when a day has nothing recorded. \
Never invent tasks."""


def _format_tasks(rows) -> str:
    if not rows:
        return "(no tasks)"
    lines = []
    for r in rows:
        parts = [r["due_date"] or "no date", r["kind"], r["subject"] or "-", r["title"]]
        if r["details"]:
            parts.append(r["details"])
        if r["platform"]:
            parts.append(f"on {r['platform']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def answer(question: str, today: date, dated_rows, undated_rows, focus_days: list[date]) -> str:
    text = (
        f"Today is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"School days to cover: {', '.join(d.strftime('%A %Y-%m-%d') for d in focus_days)}\n\n"
        f"Tasks with dates:\n{_format_tasks(dated_rows)}\n\n"
        f"Recent reminders with no date:\n{_format_tasks(undated_rows)}\n\n"
        f"Parent's question: {question}"
    )
    if LLM_PROVIDER == "ollama":
        return _ollama_chat(ANSWER_SYSTEM, text).strip()
    response = _claude().beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=ANSWER_SYSTEM,
        messages=[{"role": "user", "content": text}],
        output_config={"effort": "low"},
        **FALLBACK_KWARGS,
    )
    if response.stop_reason == "refusal":
        return "ما قدرت جاوب على هالسؤال، جربي تسأليه بطريقة تانية."
    return "".join(b.text for b in response.content if b.type == "text").strip()
