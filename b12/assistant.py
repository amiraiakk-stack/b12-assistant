"""Glue: sync B12, extract tasks from new messages, and answer questions."""

import threading
from datetime import datetime, timedelta

from . import llm, scraper, store
from .config import TZ


def today():
    return datetime.now(TZ).date()


def process_new_messages() -> int:
    count = 0
    for msg in store.unprocessed_messages():
        tasks = llm.extract_tasks(msg, today())
        store.save_tasks(msg["id"], tasks)
        count += len(tasks)
    return count


# The browser profile can only be open once, so the scheduler and the page's button take turns.
_sync_lock = threading.Lock()


def sync_and_process() -> str:
    with _sync_lock:
        new_messages = scraper.sync()
        new_tasks = process_new_messages()
    return f"{new_messages} new messages, {new_tasks} tasks extracted"


def ask(question: str) -> str:
    now = today()
    # Cover today plus the next two weeks; Claude picks the day the question is about and the
    # next school days after it for the reminder part.
    dated = store.tasks_between(now, now + timedelta(days=14))
    undated = store.recent_undated_tasks()
    focus = llm.next_school_days(now + timedelta(days=1), 3)
    return llm.answer(question, now, dated, undated, focus)


def morning_brief() -> str:
    return ask("شو عنا اليوم؟ وذكرني بالأيام الجاية")
