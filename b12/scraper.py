"""Sign in to the B12 student portal with Playwright and pull messages, weekly plans and newsletters.

B12 has no public API, so this drives a real browser. The browser profile is kept in data/ so the
Microsoft sign-in is remembered between runs.

Which pages to read is set in selectors.json. Run `python -m b12 discover` first: it saves a
screenshot, the HTML and the links of the B12 pages so selectors.json can be filled in.
"""

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout, sync_playwright

from . import credentials, store
from .config import (
    B12_URL,
    BROWSER_PROFILE,
    DISCOVER_DIR,
    DOWNLOADS_DIR,
    SELECTORS_PATH,
)

MS_LOGIN_HOST = "login.microsoftonline.com"
MS_ERROR_SELECTOR = "#usernameError, #passwordError, #errorText, .alert-error"


class LoginError(Exception):
    """The B12 / Microsoft sign-in did not succeed."""


def _open(headless: bool):
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(str(BROWSER_PROFILE), headless=headless, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return pw, ctx, page


def _microsoft_sign_in(page: Page, email: str, password: str) -> None:
    """Fill the Microsoft sign-in form. Any step that is not shown is skipped."""
    try:
        page.fill("input[type=email]", email, timeout=10_000)
        page.click("input[type=submit]")
    except PWTimeout:
        pass
    try:
        page.fill("input[type=password]", password, timeout=15_000)
        page.click("input[type=submit]")
    except PWTimeout:
        pass
    try:
        # "Stay signed in?" -> Yes, or Microsoft's error under the email or password box
        page.wait_for_selector(f"#idSIButton9, {MS_ERROR_SELECTOR}", timeout=10_000)
    except PWTimeout:
        return
    error = page.query_selector(MS_ERROR_SELECTOR)
    if error and error.is_visible():
        raise LoginError(error.inner_text().strip() or "Microsoft rejected the sign-in")
    page.click("#idSIButton9")


def ensure_signed_in(page: Page, interactive: bool = False) -> None:
    page.goto(B12_URL, wait_until="networkidle")
    if MS_LOGIN_HOST not in page.url:
        # B12 may show its own page with a "Sign in with Microsoft" button first.
        button = page.get_by_text(re.compile("microsoft|office 365|sign in", re.I)).first
        try:
            button.click(timeout=5_000)
            page.wait_for_load_state("networkidle")
        except PWTimeout:
            return  # already signed in
    if MS_LOGIN_HOST in page.url:
        creds = credentials.get()
        if not creds and not interactive:
            raise LoginError("No student sign-in saved")
        if creds:
            _microsoft_sign_in(page, *creds)
    if interactive:
        print("If the browser still shows a sign-in step, finish it by hand. Waiting up to 3 minutes...")
    try:
        page.wait_for_url(lambda url: MS_LOGIN_HOST not in url, timeout=180_000 if interactive else 60_000)
    except PWTimeout:
        raise LoginError("Sign-in did not finish") from None
    page.wait_for_load_state("networkidle")


def sign_in_with(email: str, password: str) -> None:
    """Sign in from scratch with the given account and save it if it works. Raises LoginError."""
    shutil.rmtree(BROWSER_PROFILE, ignore_errors=True)
    pw, ctx, page = _open(headless=True)
    try:
        page.goto(B12_URL, wait_until="networkidle")
        if MS_LOGIN_HOST not in page.url:
            page.get_by_text(re.compile("microsoft|office 365|sign in", re.I)).first.click(timeout=15_000)
            page.wait_for_load_state("networkidle")
        _microsoft_sign_in(page, email, password)
        try:
            page.wait_for_url(lambda url: MS_LOGIN_HOST not in url, timeout=60_000)
        except PWTimeout:
            raise LoginError("Sign-in did not finish") from None
    finally:
        ctx.close()
        pw.stop()
    credentials.save(email, password)


def sign_out() -> None:
    credentials.clear()
    shutil.rmtree(BROWSER_PROFILE, ignore_errors=True)


def login() -> None:
    """Open a visible browser and sign in once, so the session is saved."""
    pw, ctx, page = _open(headless=False)
    try:
        ensure_signed_in(page, interactive=True)
        print("Signed in. Current page:", page.url)
    finally:
        ctx.close()
        pw.stop()


def _save_page(page: Page, name: str) -> dict:
    DISCOVER_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(DISCOVER_DIR / f"{name}.png"), full_page=True)
    (DISCOVER_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    links = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => ({text: e.innerText.trim().slice(0, 80), href: e.href}))"
    )
    return {"name": name, "url": page.url, "links": [l for l in links if l["text"]]}


def discover(max_pages: int = 15) -> Path:
    """Save the landing page and every page linked from it, for writing selectors.json."""
    pw, ctx, page = _open(headless=False)
    report = []
    try:
        ensure_signed_in(page, interactive=True)
        home = _save_page(page, "00-home")
        report.append(home)
        seen = {page.url}
        for i, link in enumerate(home["links"]):
            if len(seen) > max_pages or "b12app" not in link["href"] or link["href"] in seen:
                continue
            seen.add(link["href"])
            page.goto(link["href"], wait_until="networkidle")
            slug = re.sub(r"[^a-z0-9]+", "-", link["text"].lower()).strip("-")[:30] or "page"
            report.append(_save_page(page, f"{i + 1:02d}-{slug}"))
    finally:
        ctx.close()
        pw.stop()
    out = DISCOVER_DIR / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(report)} pages to {DISCOVER_DIR}")
    return out


def _download(ctx: BrowserContext, url: str) -> str | None:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    resp = ctx.request.get(url)
    if not resp.ok:
        return None
    name = re.sub(r"[^\w.-]+", "_", url.rsplit("/", 1)[-1].split("?")[0]) or "file"
    path = DOWNLOADS_DIR / name
    path.write_bytes(resp.body())
    return str(path)


def _text(el, selector: str | None) -> str:
    if not selector:
        return ""
    found = el.query_selector(selector)
    return found.inner_text().strip() if found else ""


def _scrape_section(ctx: BrowserContext, page: Page, section: dict) -> int:
    """Read one section from selectors.json. Returns how many new messages were stored."""
    page.goto(urljoin(B12_URL, section["url"]), wait_until="networkidle")
    name = section["name"]
    new = 0

    item_selector = section.get("item_selector")
    if not item_selector:
        # Snapshot mode: the whole page text is one message. Only a changed page is stored.
        body = page.inner_text("body")
        pdf = next(iter(page.eval_on_selector_all("a[href$='.pdf']", "els => els.map(e => e.href)")), None)
        attachment = _download(ctx, pdf) if pdf else None
        return int(store.save_message(name, section.get("title", name), "", body, attachment, replace_source=True))

    count = len(page.query_selector_all(item_selector))
    for idx in range(min(count, section.get("max_items", 20))):
        item = page.query_selector_all(item_selector)[idx]
        title = _text(item, section.get("title_selector"))
        sent_at = _text(item, section.get("date_selector"))
        body = _text(item, section.get("body_selector")) or item.inner_text().strip()
        attachment = None
        if section.get("open_item"):
            item.click()
            page.wait_for_load_state("networkidle")
            detail = section.get("detail_selector")
            body = page.inner_text(detail) if detail and page.query_selector(detail) else page.inner_text("body")
            link = page.query_selector(section.get("attachment_selector", "a[href$='.pdf']"))
            if link:
                attachment = _download(ctx, urljoin(page.url, link.get_attribute("href")))
            page.go_back(wait_until="networkidle")
        new += store.save_message(name, title, sent_at, body, attachment)
    return new


def sync() -> int:
    """Fetch every section in selectors.json. Returns the number of new messages."""
    sections = json.loads(SELECTORS_PATH.read_text(encoding="utf-8"))["sections"]
    pw, ctx, page = _open(headless=True)
    total = 0
    try:
        ensure_signed_in(page)
        for section in sections:
            try:
                total += _scrape_section(ctx, page, section)
            except PWTimeout as e:
                print(f"[{section['name']}] timed out: {e}")
    finally:
        ctx.close()
        pw.stop()
    return total
