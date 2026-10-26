"""The student's B12 sign-in, entered on the web page.

Stored in the operating system's password store (Windows Credential Manager, macOS Keychain),
never in a plain file. B12_EMAIL / B12_PASSWORD in .env are used only if nothing was saved.
"""

import keyring
from keyring.errors import PasswordDeleteError

from .config import B12_EMAIL, B12_PASSWORD

SERVICE = "b12-assistant"
EMAIL_KEY = "__email__"


def get() -> tuple[str, str] | None:
    email = keyring.get_password(SERVICE, EMAIL_KEY)
    if email:
        password = keyring.get_password(SERVICE, email)
        if password:
            return email, password
    if B12_EMAIL and B12_PASSWORD:
        return B12_EMAIL, B12_PASSWORD
    return None


def save(email: str, password: str) -> None:
    keyring.set_password(SERVICE, EMAIL_KEY, email)
    keyring.set_password(SERVICE, email, password)


def clear() -> None:
    email = keyring.get_password(SERVICE, EMAIL_KEY)
    for key in filter(None, [email, EMAIL_KEY]):
        try:
            keyring.delete_password(SERVICE, key)
        except PasswordDeleteError:
            pass
