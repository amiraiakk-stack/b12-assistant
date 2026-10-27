"""The student's B12 sign-in, entered on the web page.

Stored in the operating system's password store (Windows Credential Manager, macOS Keychain).
Where there is none, as on WSL or a server, it goes to data/credentials.json, readable only by
the current user. B12_EMAIL / B12_PASSWORD in .env are used only if nothing was saved.
"""

import json
import os

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from .config import B12_EMAIL, B12_PASSWORD, DATA_DIR

SERVICE = "b12-assistant"
EMAIL_KEY = "__email__"
FILE = DATA_DIR / "credentials.json"


def _keyring_get() -> tuple[str, str] | None:
    email = keyring.get_password(SERVICE, EMAIL_KEY)
    password = email and keyring.get_password(SERVICE, email)
    return (email, password) if password else None


def _file_get() -> tuple[str, str] | None:
    if not FILE.exists():
        return None
    data = json.loads(FILE.read_text(encoding="utf-8"))
    return data["email"], data["password"]


def get() -> tuple[str, str] | None:
    try:
        creds = _keyring_get()
    except KeyringError:
        creds = None
    creds = creds or _file_get()
    if creds:
        return creds
    if B12_EMAIL and B12_PASSWORD:
        return B12_EMAIL, B12_PASSWORD
    return None


def save(email: str, password: str) -> None:
    try:
        keyring.set_password(SERVICE, EMAIL_KEY, email)
        keyring.set_password(SERVICE, email, password)
        return
    except KeyringError:
        pass
    fd = os.open(FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"email": email, "password": password}, f)


def clear() -> None:
    FILE.unlink(missing_ok=True)
    try:
        email = keyring.get_password(SERVICE, EMAIL_KEY)
    except KeyringError:
        return
    for key in filter(None, [email, EMAIL_KEY]):
        try:
            keyring.delete_password(SERVICE, key)
        except PasswordDeleteError:
            pass
