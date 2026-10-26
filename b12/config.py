import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "b12.sqlite"
BROWSER_PROFILE = DATA_DIR / "browser-profile"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DISCOVER_DIR = DATA_DIR / "discover"
SELECTORS_PATH = ROOT / "selectors.json"

MODEL = "claude-opus-5-5"

B12_URL = os.getenv("B12_URL", "https://student.b12app.com/")
B12_EMAIL = os.getenv("B12_EMAIL", "")
B12_PASSWORD = os.getenv("B12_PASSWORD", "")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
ALLOWED_WHATSAPP_NUMBER = os.getenv("ALLOWED_WHATSAPP_NUMBER", "")

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Amman"))
SYNC_EVERY_HOURS = float(os.getenv("SYNC_EVERY_HOURS", "3"))
MORNING_REMINDER_HOUR = int(os.getenv("MORNING_REMINDER_HOUR", "6"))

# Jordanian schools are off on Friday and Saturday (Python weekday: Mon=0 ... Sun=6).
WEEKEND_DAYS = {4, 5}
