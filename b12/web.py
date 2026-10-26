"""Web page for asking about school tasks, plus the background sync and morning reminder.

Run with: python -m b12 serve   then open http://localhost:8000
"""

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import assistant, store
from .config import ALLOWED_WHATSAPP_NUMBER, MORNING_REMINDER_HOUR, SYNC_EVERY_HOURS, TZ, WHATSAPP_TOKEN

PAGE = Path(__file__).with_name("static") / "index.html"

app = FastAPI(title="B12 assistant")

if WHATSAPP_TOKEN:
    from .whatsapp import router as whatsapp_router, send_text

    app.include_router(whatsapp_router)


class Question(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE.read_text(encoding="utf-8")


@app.post("/api/ask")
def ask(q: Question):
    return {"answer": assistant.ask(q.question)}


@app.post("/api/sync")
def sync():
    return {"result": assistant.sync_and_process()}


@app.get("/api/tasks")
def upcoming_tasks(days: int = 7):
    today = assistant.today()
    rows = store.tasks_between(today, today + timedelta(days=days))
    return {"tasks": [dict(r) for r in rows]}


def _scheduler() -> None:
    last_sync = 0.0
    last_brief_day = None
    while True:
        now = datetime.now(TZ)
        if time.time() - last_sync >= SYNC_EVERY_HOURS * 3600:
            try:
                print("sync:", assistant.sync_and_process())
            except Exception as e:  # keep the server running if B12 is down
                print("sync failed:", e)
            last_sync = time.time()
        if (
            WHATSAPP_TOKEN
            and ALLOWED_WHATSAPP_NUMBER
            and now.hour == MORNING_REMINDER_HOUR
            and last_brief_day != now.date()
        ):
            try:
                send_text(ALLOWED_WHATSAPP_NUMBER, "صباح الخير ☀️\n" + assistant.morning_brief())
            except Exception as e:
                print("morning reminder failed:", e)
            last_brief_day = now.date()
        time.sleep(60)


@app.on_event("startup")
def start_scheduler() -> None:
    threading.Thread(target=_scheduler, daemon=True).start()
