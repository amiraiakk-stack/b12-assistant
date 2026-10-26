"""WhatsApp bot (Meta WhatsApp Cloud API).

The router is mounted by b12.web when WHATSAPP_TOKEN is set.
Meta must reach the /webhook URL over HTTPS, e.g. through `ngrok http 8000` or a small server.
"""

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from . import assistant
from .config import (
    ALLOWED_WHATSAPP_NUMBER,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
    WHATSAPP_VERIFY_TOKEN,
)

GRAPH_URL = "https://graph.facebook.com/v21.0"
MAX_WHATSAPP_TEXT = 4096

router = APIRouter()


def send_text(to: str, text: str) -> None:
    for start in range(0, len(text), MAX_WHATSAPP_TEXT):
        httpx.post(
            f"{GRAPH_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text[start : start + MAX_WHATSAPP_TEXT]},
            },
            timeout=30,
        ).raise_for_status()


@router.get("/webhook")
def verify(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


def _reply(sender: str, text: str) -> None:
    if text.strip() in {"تحديث", "sync"}:
        send_text(sender, "عم حدّث من B12...")
        send_text(sender, assistant.sync_and_process())
        return
    send_text(sender, assistant.ask(text))


@router.post("/webhook")
async def receive(request: Request, background: BackgroundTasks):
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                sender = message.get("from", "")
                if sender != ALLOWED_WHATSAPP_NUMBER or message.get("type") != "text":
                    continue
                # Answer in the background so Meta gets its 200 straight away and does not resend.
                background.add_task(_reply, sender, message["text"]["body"])
    return {"ok": True}
