"""
Advanced Browser Automation — SIYA / JARVIS tools module
=========================================================

Chrome DevTools Protocol (CDP) based browser control via Playwright.
Drop-in replacement for the original browser_automation.py — every original
tool name (web_navigate, web_click_element, web_fill_form,
read_web_page_content, youtube_search_and_play, youtube_media_control) is
kept, so nothing else in the agent's tool list needs to change. New tools
are additive.

What changed vs. the original, and why:

DYNAMIC
  - A single, unified element-finder (`_find_best_locator`) replaces the
    repeated ad-hoc locator lists in every tool. It tries ARIA role +
    accessible name first (survives redesigns/class-name churn), then
    placeholder/label, then visible text — in that order of reliability.
  - Search-result extraction understands Google, Bing, and DuckDuckGo
    (previously Google-only) and falls back to generic readability-style
    text extraction for everything else.
  - Chrome's real install path is resolved dynamically via the project's
    own `desktop_registry`, with an Edge fallback, instead of assuming
    `chrome.exe` is on PATH.

ACCURATE
  - Every action confirms the element is actually visible before acting,
    scrolls it into view, and retries once with a forced click if a normal
    click is intercepted/overlaid.
  - "First/top result" clicking now works across search engines, not just
    Google.
  - YouTube search skips Shorts/playlists/channel results and picks the
    first genuine `/watch?v=` link; ad skip-buttons are auto-dismissed.
  - Tab tracking is session-aware: the "active page" is validated on every
    call and a fresh one is picked automatically if it was closed.

SAFE
  - `_validate_target_url` enforces an *allow-list* (http/https/about:blank)
    for navigation. This specifically guards against a page's own content
    steering the agent into `file://`, `javascript:`, `data:`, `chrome://`
    etc. — the realistic risk here is indirect prompt injection: a
    malicious/compromised page instructs the agent (via text the agent
    later reads back into its own context) to navigate to a local file and
    read it back, which would leak local data through the chat.
  - Every Playwright call carries an explicit timeout — nothing can hang
    the agent forever on a slow or hostile page.
  - `_safe_evaluate` wraps all in-page JS execution with a hard timeout and
    never string-interpolates user-provided text into JS source — values
    are always passed as arguments, never concatenated into the script.
  - Closing the last remaining tab blanks it instead of actually closing
    it, so the Chrome process/CDP session never dies unexpectedly.

Tool list:
  Navigation:   web_navigate, web_go_back, web_go_forward, web_reload_page
  Tabs:         list_browser_tabs, switch_browser_tab, open_new_tab,
                close_browser_tab
  Interaction:  web_click_element, web_fill_form, web_select_dropdown_option,
                web_scroll_page
  Reading:      read_web_page_content, extract_page_links,
                take_page_screenshot
  YouTube:      youtube_search_and_play, youtube_media_control
"""

import os
import re
import time
import asyncio
import logging
import urllib.parse
import urllib.request
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Any

from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PWTimeoutError,
)
from livekit.agents import function_tool, RunContext, ToolError

from .desktop_registry import resolve_app_dynamically

logger = logging.getLogger("desktop_automation.browser")

CDP_URL = "http://127.0.0.1:9222"
NAV_TIMEOUT_MS = 15000
ACTION_TIMEOUT_MS = 5000
JS_TIMEOUT_S = 5.0
CDP_LAUNCH_WAIT_ATTEMPTS = 25
CDP_LAUNCH_POLL_S = 0.3

SCREENSHOT_DIR = os.path.expanduser(r"~\.jarvis_browser_screenshots")

# Chrome profile JARVIS launches (and attaches to) over CDP. If you set up a
# manual "JARVIS-ready Chrome" shortcut (see jarvis_chrome_launcher.bat),
# its --user-data-dir MUST point at this exact same folder — otherwise the
# manually-opened window and JARVIS's own auto-launch end up as two
# different, unrelated profiles again.
CHROME_PROFILE_DIR = os.path.expanduser(r"~\.jarvis_chrome_profile")

# ---------------------------------------------------------------------------
# Session state (module-level singleton, matching the rest of this project)
# ---------------------------------------------------------------------------

@dataclass
class _BrowserSession:
    pw: Optional[Playwright] = None
    browser: Optional[Browser] = None
    active_page: Optional[Page] = None


_session = _BrowserSession()


# ---------------------------------------------------------------------------
# Safety: navigation allow-list
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_target_url(url: str) -> str:
    """
    Only http/https (and about:blank) navigation is permitted. Blocks
    file://, javascript:, data:, chrome://, edge://, etc. — this matters
    most when a navigation target could be influenced by content the agent
    just read off an untrusted page (indirect prompt injection), since
    those schemes could read local files or run injected script.
    """
    cleaned = url.strip()
    if cleaned.lower() == "about:blank":
        return cleaned

    parsed = urllib.parse.urlsplit(cleaned)
    scheme = parsed.scheme.lower()

    if scheme not in _ALLOWED_SCHEMES:
        raise ToolError(
            f"Security ke wajah se '{scheme or url}' scheme allowed nahi hai. "
            f"Sirf http/https websites open ki ja sakti hain."
        )
    return cleaned


# ---------------------------------------------------------------------------
# CDP connection management
# ---------------------------------------------------------------------------

def _is_cdp_port_active() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def _resolve_browser_launch_cmd() -> str:
    """Chrome (ya fallback Edge) ka asli installed path registry/start-menu se dynamically nikalta hai."""
    for name in ("chrome", "edge"):
        try:
            app_info = resolve_app_dynamically(name)
        except Exception:
            app_info = None
        if app_info and app_info.get("cmd"):
            return app_info["cmd"]
    return "chrome.exe"


def _launch_chrome_with_cdp():
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    browser_cmd = _resolve_browser_launch_cmd()

    # "start" ke baad khaali "" title zaroori hai — warna quoted path (jisme
    # spaces hon, jaise "C:\Program Files\...") galti se window-title samajh
    # liya jaata hai aur launch fail ho jaata hai.
    cmd = (
        f'start "" {browser_cmd} --remote-debugging-port=9222 '
        f'--user-data-dir="{CHROME_PROFILE_DIR}" --no-first-run --no-default-browser-check'
    )
    logger.info("Launching browser with CDP debugging enabled...")
    subprocess.Popen(cmd, shell=True)


# Jab ek hi voice command mein multiple tool calls fire hote hain (e.g. "open
# facebook, whatsapp aur X website" -> 3 parallel web_navigate calls), har
# call independently CDP port check karke "inactive" paata tha aur apna khud
# ka browser launch kar deta tha -> isi wajah se 2+ alag Chrome windows khul
# rahe the. Yeh lock poora launch-aur-connect critical section ko serialize
# karta hai: sirf ek hi coroutine kabhi Chrome launch karega, baaki sab uska
# result reuse karenge.
_launch_lock = asyncio.Lock()


async def _get_browser() -> Browser:
    async with _launch_lock:
        # Fast path: pehle se hi connected browser hai, seedha wahi return karo.
        if _session.browser is not None and _session.browser.is_connected():
            return _session.browser

        if not _is_cdp_port_active():
            logger.info("CDP port inactive, launching browser...")
            _launch_chrome_with_cdp()
            for _ in range(CDP_LAUNCH_WAIT_ATTEMPTS):
                await asyncio.sleep(CDP_LAUNCH_POLL_S)
                if _is_cdp_port_active():
                    break

        if not _is_cdp_port_active():
            raise ToolError("Chrome CDP port 9222 par connect nahi ho saka.")

        if _session.pw is None:
            _session.pw = await async_playwright().start()

        try:
            _session.browser = await _session.pw.chromium.connect_over_cdp(
                CDP_URL, timeout=NAV_TIMEOUT_MS
            )
        except Exception as e:
            _session.browser = None
            raise ToolError(f"Browser se connect nahi ho saka: {e}")

        return _session.browser


async def _get_context() -> BrowserContext:
    browser = await _get_browser()
    if not browser.contexts:
        raise ToolError("Browser ka koi active context nahi mila.")
    return browser.contexts[0]


async def _get_active_page(open_new: bool = False) -> Page:
    ctx = await _get_context()
    pages = [p for p in ctx.pages if not p.is_closed()]

    if open_new:
        page = await ctx.new_page()
        _session.active_page = page
        return page

    if _session.active_page and not _session.active_page.is_closed() and _session.active_page in pages:
        return _session.active_page

    if pages:
        _session.active_page = pages[-1]
        return _session.active_page

    page = await ctx.new_page()
    _session.active_page = page
    return page


async def _safe_evaluate(page: Page, js_expression: str, arg: Any = None):
    """Page-context JS ko hamesha ek hard timeout ke saath chalata hai, aur
    user text ko kabhi seedhe JS source mein interpolate nahi karta — arg
    hamesha data ke roop mein pass hota hai."""
    try:
        return await asyncio.wait_for(page.evaluate(js_expression, arg), timeout=JS_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("Page JS evaluation timed out.")
        return None
    except Exception as e:
        logger.warning(f"Page JS evaluation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Unified element finder
# ---------------------------------------------------------------------------

async def _find_best_locator(
    page: Page,
    text: str,
    roles: Optional[List[str]] = None,
    timeout_ms: int = ACTION_TIMEOUT_MS,
):
    """
    Resilient element finder, tried in order of reliability:
      1. ARIA role + accessible name (survives DOM/class-name changes)
      2. Placeholder / label text (inputs)
      3. Visible text match (last resort — least specific)
    Returns the first strictly-visible match, or None.
    """
    roles = roles or ["button", "link", "menuitem", "tab", "checkbox", "radio", "textbox"]
    candidates = []

    for role in roles:
        try:
            candidates.append(page.get_by_role(role, name=text, exact=False))
        except Exception:
            continue

    candidates.append(page.get_by_placeholder(text, exact=False))
    candidates.append(page.get_by_label(text, exact=False))
    candidates.append(page.get_by_text(text, exact=False))

    for loc in candidates:
        try:
            count = await loc.count()
        except Exception:
            continue
        for i in range(min(count, 5)):
            el = loc.nth(i)
            try:
                if await el.is_visible(timeout=800):
                    return el
            except Exception:
                continue

    return None


async def _dismiss_consent_banner(page: Page):
    """YouTube/Google jaise consent walls ko best-effort dismiss karta hai.
    Sirf specific, well-known selectors — kisi bhi site ke arbitrary
    'Accept' button ko blindly click nahi karta."""
    selectors = [
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "form[action*='consent'] button",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible(timeout=500):
                await btn.click(timeout=1500)
                await asyncio.sleep(0.3)
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

async def _do_navigate(page: Page, url_or_query: str) -> str:
    target = url_or_query.strip()
    if not target:
        raise ToolError("Boss, koi URL ya search query nahi mila.")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
        looks_like_domain = bool(re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", target)) and " " not in target
        target = (
            f"https://{target}"
            if looks_like_domain
            else f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
        )

    target = _validate_target_url(target)

    try:
        await page.goto(target, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except PWTimeoutError:
        logger.warning(f"Navigation timeout, page likely still usable: {target}")
    except Exception as e:
        raise ToolError(f"'{target}' open nahi ho saka: {e}")

    return (await page.title()) or target


@function_tool(
    name="web_navigate",
    description="Open a website or run a Google search in the browser. Pass a full URL, a bare domain, or a search phrase. Set new_tab=True to open it in a fresh tab.",
)
async def web_navigate(context: RunContext, url_or_query: str, new_tab: bool = False) -> str:
    page = await _get_active_page(open_new=new_tab)
    title = await _do_navigate(page, url_or_query)
    suffix = " naye tab mein" if new_tab else ""
    return f"Boss, '{title}'{suffix} open ho gaya hai."


@function_tool(name="web_go_back", description="Navigate back to the previous page in browser history.")
async def web_go_back(context: RunContext) -> str:
    page = await _get_active_page()
    try:
        await page.go_back(timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    except Exception:
        raise ToolError("Boss, pichle page par wapas nahi ja saka — history khaali ho sakti hai.")
    return f"Boss, '{await page.title()}' par wapas aa gaya."


@function_tool(name="web_go_forward", description="Navigate forward in browser history.")
async def web_go_forward(context: RunContext) -> str:
    page = await _get_active_page()
    try:
        await page.go_forward(timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    except Exception:
        raise ToolError("Boss, aage koi page history mein nahi hai.")
    return f"Boss, '{await page.title()}' par forward ho gaya."


@function_tool(name="web_reload_page", description="Reload/refresh the active web page.")
async def web_reload_page(context: RunContext) -> str:
    page = await _get_active_page()
    try:
        await page.reload(timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    except Exception as e:
        raise ToolError(f"Page reload nahi ho saka: {e}")
    return "Boss, page reload kar diya gaya hai."


# ---------------------------------------------------------------------------
# Tab management
# ---------------------------------------------------------------------------

@function_tool(name="list_browser_tabs", description="List all currently open browser tabs with their titles and URLs.")
async def list_browser_tabs(context: RunContext) -> str:
    ctx = await _get_context()
    pages = [p for p in ctx.pages if not p.is_closed()]
    if not pages:
        return "Boss, koi tab open nahi hai."

    lines = []
    for i, p in enumerate(pages, start=1):
        marker = " (active)" if p == _session.active_page else ""
        try:
            title = await p.title()
        except Exception:
            title = "(loading...)"
        lines.append(f"{i}. {title}{marker} - {p.url}")

    return "Open tabs:\n" + "\n".join(lines)


@function_tool(
    name="switch_browser_tab",
    description="Switch the active browser tab, identified by its number (from list_browser_tabs) or a keyword from its title/URL.",
)
async def switch_browser_tab(context: RunContext, tab_number_or_title: str) -> str:
    ctx = await _get_context()
    pages = [p for p in ctx.pages if not p.is_closed()]
    if not pages:
        raise ToolError("Boss, koi tab open nahi hai.")

    identifier = tab_number_or_title.strip()
    target_page = None

    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(pages):
            target_page = pages[idx]
    else:
        for p in pages:
            try:
                if identifier.lower() in (await p.title()).lower() or identifier.lower() in p.url.lower():
                    target_page = p
                    break
            except Exception:
                continue

    if not target_page:
        raise ToolError(f"Boss, '{tab_number_or_title}' se match karta koi tab nahi mila.")

    await target_page.bring_to_front()
    _session.active_page = target_page
    return f"Boss, '{await target_page.title()}' tab par switch kar diya."


@function_tool(name="open_new_tab", description="Open a new browser tab, optionally navigating it to a URL or search query.")
async def open_new_tab(context: RunContext, url_or_query: Optional[str] = None) -> str:
    page = await _get_active_page(open_new=True)
    if url_or_query:
        title = await _do_navigate(page, url_or_query)
        return f"Boss, naye tab mein '{title}' open kar diya gaya hai."
    return "Boss, ek khaali naya tab open kar diya gaya hai."


@function_tool(
    name="close_browser_tab",
    description="Close a specific browser tab by number/title, or the active tab if not specified.",
)
async def close_browser_tab(context: RunContext, tab_number_or_title: Optional[str] = None) -> str:
    ctx = await _get_context()
    pages = [p for p in ctx.pages if not p.is_closed()]
    if not pages:
        raise ToolError("Boss, koi tab open nahi hai.")

    target_page = None
    if tab_number_or_title:
        identifier = tab_number_or_title.strip()
        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(pages):
                target_page = pages[idx]
        else:
            for p in pages:
                try:
                    if identifier.lower() in (await p.title()).lower():
                        target_page = p
                        break
                except Exception:
                    continue
    else:
        target_page = _session.active_page

    if not target_page or target_page not in pages:
        target_page = pages[-1]

    try:
        title = await target_page.title()
    except Exception:
        title = "tab"

    if len(pages) == 1:
        # Aakhri tab band karne ke bajaye blank kar dena — taaki Chrome
        # process/CDP session achanak khatam na ho jaaye.
        await target_page.goto("about:blank")
        return f"Boss, yeh akela tab tha, isliye '{title}' close karne ke bajaye blank kar diya."

    await target_page.close()
    if _session.active_page == target_page:
        remaining = [p for p in ctx.pages if not p.is_closed()]
        _session.active_page = remaining[-1] if remaining else None

    return f"Boss, '{title}' tab close kar diya gaya hai."


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

@function_tool(
    name="web_click_element",
    description="Click a visible button, link, menu item, or search result on the active web page, identified by its visible text or label.",
)
async def web_click_element(context: RunContext, text_or_label: str) -> str:
    page = await _get_active_page()
    clean = text_or_label.strip()
    lowered = clean.lower()

    if any(k in lowered for k in ["first result", "top result", "pehla result", "1st result"]):
        generic_result = page.locator(
            "div.g h3, div[data-hveid] h3, li.b_algo h2 a, article h2 a, a h3"
        ).first
        if await generic_result.count() > 0:
            title = (await generic_result.inner_text()).strip()
            try:
                await generic_result.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
                await generic_result.click(timeout=ACTION_TIMEOUT_MS)
                return f"Boss, pehla result '{title}' open kar diya hai."
            except Exception:
                pass  # gir kar neeche generic finder try karega

    target = await _find_best_locator(page, clean)
    if target is None:
        raise ToolError(f"Webpage par '{clean}' naam ka koi visible element nahi mila.")

    try:
        await target.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        await target.click(timeout=ACTION_TIMEOUT_MS)
    except PWTimeoutError:
        try:
            # Kabhi kabhi overlay/animation click intercept kar leta hai — force retry
            await target.click(timeout=ACTION_TIMEOUT_MS, force=True)
        except Exception as e:
            raise ToolError(f"'{clean}' par click perform nahi ho saka: {e}")
    except Exception as e:
        raise ToolError(f"'{clean}' par click perform nahi ho saka: {e}")

    return f"Boss, '{clean}' par click kar diya gaya hai."


@function_tool(
    name="web_fill_form",
    description="Type text into a search box, input field, or form field on the active web page. Optionally submit with Enter.",
)
async def web_fill_form(
    context: RunContext, field_placeholder_or_label: str, value_to_type: str, submit: bool = False
) -> str:
    page = await _get_active_page()
    field = field_placeholder_or_label.strip()

    loc = await _find_best_locator(page, field, roles=["textbox", "searchbox", "combobox"])
    if loc is None:
        fallback = page.locator(
            "input[type='text'], input[type='search'], input[type='email'], input:not([type]), textarea"
        ).first
        if await fallback.count() > 0:
            loc = fallback
        else:
            raise ToolError(f"'{field}' naam ka koi input field nahi mila.")

    try:
        await loc.click(timeout=ACTION_TIMEOUT_MS)
        await loc.fill("", timeout=ACTION_TIMEOUT_MS)
        await loc.fill(value_to_type, timeout=ACTION_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"'{field}' mein text enter nahi ho saka: {e}")

    if submit:
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.3)

    tail = " aur submit kar diya hai." if submit else " hai."
    return f"Boss, '{field}' field mein '{value_to_type}' enter kar diya{tail}"


@function_tool(
    name="web_select_dropdown_option",
    description="Select an option from a dropdown/select field on the active web page.",
)
async def web_select_dropdown_option(context: RunContext, field_label: str, option_text: str) -> str:
    page = await _get_active_page()
    try:
        select_loc = page.get_by_label(field_label, exact=False)
        if await select_loc.count() == 0:
            select_loc = page.locator("select").first
        await select_loc.select_option(label=option_text, timeout=ACTION_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"'{field_label}' dropdown mein '{option_text}' select nahi ho saka: {e}")

    return f"Boss, '{field_label}' mein '{option_text}' select kar diya hai."


@function_tool(
    name="web_scroll_page",
    description="Scroll the active web page up, down, to the top, to the bottom, or to a specific text/element.",
)
async def web_scroll_page(context: RunContext, direction: str = "down", target_text: Optional[str] = None) -> str:
    page = await _get_active_page()

    if target_text:
        loc = await _find_best_locator(page, target_text, roles=["heading", "link", "button", "textbox"])
        if loc:
            await loc.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
            return f"Boss, page ko '{target_text}' tak scroll kar diya hai."
        raise ToolError(f"'{target_text}' page par nahi mila, scroll nahi ho saka.")

    d = direction.strip().lower()
    if "top" in d:
        await _safe_evaluate(page, "() => window.scrollTo({top: 0, behavior: 'smooth'})")
        label = "top"
    elif "bottom" in d or "end" in d:
        await _safe_evaluate(page, "() => window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        label = "bottom"
    elif "up" in d:
        await _safe_evaluate(page, "() => window.scrollBy({top: -600, behavior: 'smooth'})")
        label = "up"
    else:
        await _safe_evaluate(page, "() => window.scrollBy({top: 600, behavior: 'smooth'})")
        label = "down"

    return f"Boss, page ko {label} scroll kar diya hai."


# ---------------------------------------------------------------------------
# Reading / extraction
# ---------------------------------------------------------------------------

_SEARCH_ENGINE_SELECTORS = {
    "google.": {"container": "div.g, div[data-hveid]", "title": "h3", "snippet": ".VwiC3b, span.aCOpRe"},
    "bing.": {"container": "li.b_algo", "title": "h2", "snippet": ".b_caption p"},
    "duckduckgo.": {"container": "article", "title": "h2", "snippet": "[data-result='snippet']"},
}

_EXTRACT_SEARCH_RESULTS_JS = """([engineCfg]) => {
    const title = document.title;
    const url = window.location.href;

    if (engineCfg) {
        const items = [];
        document.querySelectorAll(engineCfg.container).forEach((el) => {
            const h = el.querySelector(engineCfg.title);
            const snip = el.querySelector(engineCfg.snippet);
            if (h && h.innerText.trim()) {
                items.push(`* ${h.innerText.trim()} - ${snip ? snip.innerText.trim() : ''}`);
            }
        });
        if (items.length > 0) {
            return `Search Results for "${title}":\\n\\n` + items.slice(0, 6).join('\\n\\n');
        }
    }

    // Generic readability-style extraction: chrome/nav/script/style hata kar
    // sirf meaningful paragraphs uthana.
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll('script, style, nav, footer, noscript, svg, header, aside').forEach(e => e.remove());
    const text = clone.innerText || '';
    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 20);
    return `Page: ${title}\\nURL: ${url}\\n\\n` + lines.slice(0, 30).join('\\n');
}"""


@function_tool(
    name="read_web_page_content",
    description="Read and summarize the active web page's visible text, headings, or search results (Google/Bing/DuckDuckGo aware).",
)
async def read_web_page_content(context: RunContext, max_chars: int = 1500) -> str:
    page = await _get_active_page()

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=4000)
    except Exception:
        pass

    hostname = urllib.parse.urlsplit(page.url).hostname or ""
    engine_cfg = next((cfg for key, cfg in _SEARCH_ENGINE_SELECTORS.items() if key in hostname), None)

    extracted = await _safe_evaluate(page, _EXTRACT_SEARCH_RESULTS_JS, [engine_cfg])

    if not extracted or len(extracted.strip()) < 30:
        title = await page.title()
        return f"Page Title: {title}. Abhi screen par koi detailed text nahi mila."

    return extracted[:max_chars]


_EXTRACT_LINKS_JS = """() => {
    const seen = new Set();
    const results = [];
    document.querySelectorAll('a[href]').forEach(a => {
        const text = (a.innerText || a.getAttribute('aria-label') || '').trim();
        const href = a.href;
        if (!text || !href || href.startsWith('javascript:')) return;
        const key = href.split('#')[0];
        if (seen.has(key)) return;
        const rect = a.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        seen.add(key);
        results.push({ text, href });
    });
    return results;
}"""


@function_tool(
    name="extract_page_links",
    description="Extract visible links (text + URL) from the active web page, optionally filtered by a keyword.",
)
async def extract_page_links(context: RunContext, filter_keyword: Optional[str] = None, limit: int = 15) -> str:
    page = await _get_active_page()
    links = await _safe_evaluate(page, _EXTRACT_LINKS_JS)

    if not links:
        return "Boss, is page par koi clickable link nahi mila."

    if filter_keyword:
        fk = filter_keyword.lower()
        links = [l for l in links if fk in l["text"].lower() or fk in l["href"].lower()]

    if not links:
        return f"Boss, '{filter_keyword}' se match karta koi link nahi mila."

    lines = [f"* {l['text'][:60]} -> {l['href']}" for l in links[:limit]]
    return "Links found:\n" + "\n".join(lines)


@function_tool(
    name="take_page_screenshot",
    description="Take a screenshot of the active web page and save it to disk.",
)
async def take_page_screenshot(context: RunContext, full_page: bool = False) -> str:
    page = await _get_active_page()
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    safe_name = re.sub(r"[^\w\-]", "_", (await page.title()) or "page")[:40] or "page"
    path = os.path.join(SCREENSHOT_DIR, f"{safe_name}_{int(time.time())}.png")

    try:
        await page.screenshot(path=path, full_page=full_page, timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"Screenshot lene mein error aaya: {e}")

    return f"Boss, screenshot save ho gaya hai: {path}"


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

_YT_CONTROL_JS = """([act, secs]) => {
    const v = document.querySelector('video');
    if (!v) return 'no_video';

    if (act.includes('pause') || act.includes('stop')) { v.pause(); return 'paused'; }
    if (act.includes('play') || act.includes('resume')) { v.play(); return 'playing'; }
    if (act.includes('unmute')) { v.muted = false; return 'unmuted'; }
    if (act.includes('mute')) { v.muted = true; return 'muted'; }
    if (act.includes('forward') || act.includes('skip')) { v.currentTime += secs; return 'seeked forward'; }
    if (act.includes('back') || act.includes('rewind')) { v.currentTime = Math.max(0, v.currentTime - secs); return 'seeked back'; }
    if (act.includes('volume up') || act.includes('louder')) { v.volume = Math.min(1, v.volume + 0.1); return 'volume up'; }
    if (act.includes('volume down') || act.includes('quieter')) { v.volume = Math.max(0, v.volume - 0.1); return 'volume down'; }
    if (act.includes('fullscreen')) {
        const btn = document.querySelector('.ytp-fullscreen-button');
        if (btn) { btn.click(); return 'fullscreen toggled'; }
    }
    if (act.includes('next')) {
        const nextBtn = document.querySelector('.ytp-next-button');
        if (nextBtn) { nextBtn.click(); return 'next video'; }
    }
    return 'unknown';
}"""


@function_tool(
    name="youtube_search_and_play",
    description="Search YouTube and play the most relevant genuine video result (skips Shorts, playlists, and channel links).",
)
async def youtube_search_and_play(context: RunContext, search_query: str) -> str:
    page = await _get_active_page()
    encoded = urllib.parse.quote_plus(search_query)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"YouTube search open nahi ho saka: {e}")

    await _dismiss_consent_banner(page)

    video_selector = "ytd-video-renderer a#video-title"
    try:
        await page.wait_for_selector(video_selector, timeout=8000)
    except PWTimeoutError:
        raise ToolError("YouTube search results load nahi hue.")

    videos = page.locator(video_selector)
    count = await videos.count()

    chosen = None
    chosen_title = None
    for i in range(min(count, 8)):
        v = videos.nth(i)
        href = await v.get_attribute("href")
        if not href or "/watch?v=" not in href:
            continue  # Shorts/playlists/channels skip kiya
        chosen = v
        chosen_title = (await v.inner_text()).strip()
        break

    if not chosen:
        raise ToolError(f"'{search_query}' ke liye koi playable video nahi mila.")

    try:
        await chosen.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        await chosen.click(timeout=ACTION_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"Video par click nahi ho saka: {e}")

    await asyncio.sleep(1.5)
    await _safe_evaluate(page, """() => {
        const v = document.querySelector('video');
        if (v && v.paused) v.play();
        const skip = document.querySelector('.ytp-ad-skip-button, .ytp-skip-ad-button');
        if (skip) skip.click();
    }""")

    return f"Boss, YouTube par '{chosen_title}' play kar diya gaya hai."


@function_tool(
    name="youtube_media_control",
    description="Control YouTube playback: play, pause, mute, unmute, seek forward/back, volume up/down, fullscreen, or next video (also skips ads).",
)
async def youtube_media_control(context: RunContext, action: str, seconds: int = 10) -> str:
    page = await _get_active_page()
    act = action.strip().lower()

    result = await _safe_evaluate(page, _YT_CONTROL_JS, [act, seconds])

    if result in (None, "no_video"):
        raise ToolError("Active tab mein koi YouTube video element nahi mila.")
    if result == "unknown":
        raise ToolError(f"Action '{action}' samjh nahi aaya.")

    return f"Boss, YouTube video {result} kar diya gaya hai."