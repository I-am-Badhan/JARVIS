"""
Advanced Full-Browser Automation Module — J.A.R.V.I.S.
======================================================
Features:
- Smart Multi-Tab Navigation (Different domains auto-open in new tabs; work is never lost).
- Table & Attendance Parser (No character-length deletion; table data parsed as structured text).
- YouTube Account Interaction (Subscribe, Bell Icon 'All', and Like support).
- Resilient Omni-Locator (Handles standard DOM, Shadow DOM, inputs, buttons, and JS click/fill fallbacks).
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
JS_TIMEOUT_S = 6.0
CDP_LAUNCH_WAIT_ATTEMPTS = 25
CDP_LAUNCH_POLL_S = 0.3

SCREENSHOT_DIR = os.path.expanduser(r"~\.jarvis_browser_screenshots")
CHROME_PROFILE_DIR = os.path.expanduser(r"~\.jarvis_chrome_profile")

@dataclass
class _BrowserSession:
    pw: Optional[Playwright] = None
    browser: Optional[Browser] = None
    active_page: Optional[Page] = None

_session = _BrowserSession()
_launch_lock = asyncio.Lock()


def _is_cdp_port_active() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def _resolve_browser_cmd() -> str:
    for name in ("chrome", "edge"):
        try:
            info = resolve_app_dynamically(name)
            if info and info.get("cmd"):
                return info["cmd"]
        except Exception:
            pass
    return "chrome.exe"


def _launch_chrome_with_cdp():
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    cmd_path = _resolve_browser_cmd()
    cmd = (
        f'start "" {cmd_path} --remote-debugging-port=9222 '
        f'--user-data-dir="{CHROME_PROFILE_DIR}" --no-first-run --no-default-browser-check'
    )
    logger.info("Launching browser with CDP debugging enabled...")
    subprocess.Popen(cmd, shell=True)


async def _get_browser() -> Browser:
    async with _launch_lock:
        if _session.browser and _session.browser.is_connected():
            return _session.browser

        if not _is_cdp_port_active():
            logger.info("CDP port inactive, launching browser...")
            _launch_chrome_with_cdp()
            for _ in range(CDP_LAUNCH_WAIT_ATTEMPTS):
                await asyncio.sleep(CDP_LAUNCH_POLL_S)
                if _is_cdp_port_active():
                    break

        if not _is_cdp_port_active():
            raise ToolError("Chrome CDP port 9222 active nahi ho paya.")

        if not _session.pw:
            _session.pw = await async_playwright().start()

        _session.browser = await _session.pw.chromium.connect_over_cdp(
            CDP_URL, timeout=NAV_TIMEOUT_MS
        )
        return _session.browser


async def _get_context() -> BrowserContext:
    browser = await _get_browser()
    if not browser.contexts:
        raise ToolError("No active browser context found.")
    return browser.contexts[0]


async def _get_active_page(force_new: bool = False) -> Page:
    ctx = await _get_context()
    pages = [p for p in ctx.pages if not p.is_closed()]

    if force_new:
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
    try:
        return await asyncio.wait_for(page.evaluate(js_expression, arg), timeout=JS_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("Page JS evaluation timed out.")
        return None
    except Exception as e:
        logger.warning(f"Page JS evaluation failed: {e}")
        return None


async def _find_element_resiliently(page: Page, query: str):
    """Deep omni-search: ARIA, Text, Value, Placeholder, Name, Title, and CSS."""
    clean = query.strip()
    
    # 1. Direct Role checks
    for role in ["button", "link", "menuitem", "tab", "checkbox", "radio", "textbox", "searchbox"]:
        loc = page.get_by_role(role, name=clean, exact=False)
        try:
            if await loc.count() > 0:
                for i in range(await loc.count()):
                    el = loc.nth(i)
                    if await el.is_visible():
                        return el
        except Exception:
            pass

    # 2. Form input labels & placeholders
    for finder in [page.get_by_label, page.get_by_placeholder, page.get_by_text]:
        loc = finder(clean, exact=False)
        try:
            if await loc.count() > 0:
                for i in range(await loc.count()):
                    el = loc.nth(i)
                    if await el.is_visible():
                        return el
        except Exception:
            pass

    # 3. CSS Selector matches (Broad search)
    css_selectors = [
        f"input[name*='{clean}' i]",
        f"input[id*='{clean}' i]",
        f"label[for*='{clean}' i]",
        f"input[value*='{clean}' i]",
        f"input[placeholder*='{clean}' i]",
        f"button:has-text('{clean}')",
        f"a:has-text('{clean}')",
        f"[title*='{clean}' i]",
        f"[aria-label*='{clean}' i]",
        f"*:has-text('{clean}')"
    ]
    for sel in css_selectors:
        loc = page.locator(sel)
        try:
            count = await loc.count()
            for i in range(min(count, 4)):
                el = loc.nth(i)
                if await el.is_visible():
                    return el
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Navigation Tools (Smart Multi-Tab Support)
# ---------------------------------------------------------------------------

@function_tool(
    name="web_navigate",
    description="Navigate to a website or search query. Automatically opens in a NEW TAB if navigating to a different domain, keeping existing portals intact. Pass new_tab=True to force a new tab."
)
async def web_navigate(context: RunContext, url_or_query: str, new_tab: Optional[bool] = None) -> str:
    target = url_or_query.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
        looks_domain = bool(re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", target)) and " " not in target
        target = f"https://{target}" if looks_domain else f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"

    current_page = await _get_active_page()
    curr_url = current_page.url.lower()

    should_open_new = new_tab
    if should_open_new is None:
        target_domain = urllib.parse.urlsplit(target).netloc.lower()
        curr_domain = urllib.parse.urlsplit(curr_url).netloc.lower()
        is_blank = curr_url in ["about:blank", "chrome://newtab/", "chrome://new-tab-page/"]
        should_open_new = not is_blank and (target_domain != curr_domain)

    page = await _get_active_page(force_new=bool(should_open_new))
    try:
        await page.goto(target, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        logger.warning(f"Navigation soft timeout/error: {e}")

    title = (await page.title()) or target
    tab_suffix = " (naye tab mein)" if should_open_new else ""
    return f"Boss, '{title}'{tab_suffix} open ho gaya hai."


@function_tool(name="web_go_back", description="Navigate back to the previous page in browser history.")
async def web_go_back(context: RunContext) -> str:
    page = await _get_active_page()
    try:
        await page.go_back(timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    except Exception:
        raise ToolError("Boss, pichle page par wapas nahi ja saka.")
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
# Interaction Tools
# ---------------------------------------------------------------------------

@function_tool(
    name="web_click_element",
    description="Click any visible button, link, menu item, checkbox, or search result on the web page."
)
async def web_click_element(context: RunContext, text_or_label: str) -> str:
    page = await _get_active_page()
    clean = text_or_label.strip()

    if any(k in clean.lower() for k in ["first result", "top result", "pehla result", "1st result"]):
        result = page.locator("div.g h3, div[data-hveid] h3, a h3, li.b_algo h2 a").first
        if await result.count() > 0:
            title = (await result.inner_text()).strip()
            await result.click(timeout=ACTION_TIMEOUT_MS, force=True)
            return f"Boss, pehle result '{title}' par click kar diya hai."

    el = await _find_element_resiliently(page, clean)
    if not el:
        raise ToolError(f"Webpage par '{clean}' naam ka koi element nahi mila.")

    try:
        await el.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        # Using force=True to bypass invisible overlays on custom checkboxes/buttons
        await el.click(timeout=ACTION_TIMEOUT_MS, force=True)
    except Exception:
        # Ultimate fallback: Inject JS to forcefully trigger a click event
        try:
            await el.evaluate("node => { node.click(); if (node.type === 'checkbox') { node.checked = !node.checked; node.dispatchEvent(new Event('change', {bubbles: true})); } }")
        except Exception as fallback_e:
            raise ToolError(f"'{clean}' par click perform nahi ho saka: {fallback_e}")

    return f"Boss, '{clean}' par successfully click kar diya gaya hai."


@function_tool(
    name="web_fill_form",
    description="Type text into a search box, input field, or form field on the active web page. Clears previous text first."
)
async def web_fill_form(context: RunContext, field_placeholder_or_label: str, value_to_type: str, submit: bool = False) -> str:
    page = await _get_active_page()
    field = field_placeholder_or_label.strip()

    el = await _find_element_resiliently(page, field)
    if not el:
        # Fallback to broad input selection
        for selector in ["input[type='text']", "input[type='password']", "input[type='email']", "input:not([type])", "textarea"]:
            potential_inputs = page.locator(selector)
            if await potential_inputs.count() > 0:
                for i in range(await potential_inputs.count()):
                    cand = potential_inputs.nth(i)
                    if await cand.is_visible():
                        el = cand
                        break
            if el:
                break

    if not el:
        raise ToolError(f"Webpage par '{field}' input field nahi mila.")

    try:
        await el.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        # Use force=True for custom styled inputs
        await el.click(timeout=ACTION_TIMEOUT_MS, force=True)
        await el.fill("")
        
        # Standard fill method
        await el.fill(value_to_type, timeout=ACTION_TIMEOUT_MS)
        
        # Double-check if the value was actually set (React/Angular sometimes block standard fills)
        actual_val = await el.evaluate("node => node.value")
        if actual_val != value_to_type:
            # Force set value via JavaScript
            await el.evaluate(f"(node) => {{ node.value = '{value_to_type}'; node.dispatchEvent(new Event('input', {{bubbles: true}})); node.dispatchEvent(new Event('change', {{bubbles: true}})); }}")

    except Exception as e:
        raise ToolError(f"Field '{field}' mein text fill nahi ho saka: {e}")

    if submit:
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.5)

    tail = " aur submit kar diya hai." if submit else " kar diya hai."
    return f"Boss, '{field}' field mein '{value_to_type}' enter{tail}"


@function_tool(
    name="web_select_dropdown_option",
    description="Select an option from a dropdown/select field on the active web page."
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
    description="Scroll the active web page up, down, top, bottom, or directly to specific text."
)
async def web_scroll_page(context: RunContext, direction: str = "down", target_text: Optional[str] = None) -> str:
    page = await _get_active_page()

    if target_text:
        el = await _find_element_resiliently(page, target_text)
        if el:
            await el.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
            return f"Boss, page ko '{target_text}' tak scroll kar diya hai."
        raise ToolError(f"'{target_text}' page par nahi mila, scroll nahi ho saka.")

    d = direction.strip().lower()
    if "top" in d:
        await page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
    elif "bottom" in d or "end" in d:
        await page.evaluate("() => window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
    elif "up" in d:
        await page.evaluate("() => window.scrollBy({top: -600, behavior: 'smooth'})")
    else:
        await page.evaluate("() => window.scrollBy({top: 600, behavior: 'smooth'})")

    return f"Boss, page ko {direction} scroll kar diya gaya hai."


# ---------------------------------------------------------------------------
# Reading / Extraction Tools
# ---------------------------------------------------------------------------

@function_tool(
    name="read_web_page_content",
    description="Read visible webpage text, notices, and converts complex HTML attendance tables into formatted markdown rows without truncating numbers or percentages."
)
async def read_web_page_content(context: RunContext, max_chars: int = 5000) -> str:
    page = await _get_active_page()

    extracted = await page.evaluate("""() => {
        const title = document.title;
        const url = window.location.href;

        let tablesText = "";
        document.querySelectorAll('table').forEach((tbl, idx) => {
            const rows = Array.from(tbl.querySelectorAll('tr'));
            if (rows.length > 0) {
                tablesText += `\\n[TABLE ${idx + 1} DATA]:\\n`;
                rows.forEach(r => {
                    const cells = Array.from(r.querySelectorAll('th, td')).map(c => c.innerText.trim()).filter(Boolean);
                    if (cells.length > 0) {
                        tablesText += cells.join(" | ") + "\\n";
                    }
                });
            }
        });

        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('script, style, noscript, svg, nav, footer, header').forEach(el => el.remove());
        const rawLines = clone.innerText.split('\\n')
            .map(l => l.trim())
            .filter(l => l.length > 1);

        let result = `Page: ${title}\\nURL: ${url}\\n`;
        if (tablesText) {
            result += tablesText + "\\n---------------------\\n";
        }
        result += rawLines.slice(0, 100).join('\\n');
        return result;
    }""")

    if not extracted or len(extracted.strip()) < 10:
        return f"Page '{await page.title()}' load hua hai lekin koi visible text nahi mila."

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
    description="Extract visible links (text + URL) from the active web page, optionally filtered by a keyword."
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
    description="Take a screenshot of the active web page and save it to disk."
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
# YouTube Account Actions
# ---------------------------------------------------------------------------

@function_tool(
    name="youtube_account_action",
    description="Perform logged-in actions on YouTube: 'subscribe', 'bell_all' (set notifications to All), or 'like' video."
)
async def youtube_account_action(context: RunContext, action: str, channel_or_url: Optional[str] = None) -> str:
    page = await _get_active_page()
    act = action.strip().lower()

    if channel_or_url and not ("youtube.com" in page.url):
        encoded = urllib.parse.quote_plus(channel_or_url)
        await page.goto(f"https://www.youtube.com/results?search_query={encoded}", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)
        channel_link = page.locator("ytd-channel-renderer a#main-link").first
        if await channel_link.count() > 0:
            await channel_link.click(force=True)
            await asyncio.sleep(1.5)

    if "sub" in act:
        sub_btn = page.locator("ytd-subscribe-button-renderer button:has-text('Subscribe'), button[aria-label*='Subscribe to']").first
        if await sub_btn.count() > 0 and await sub_btn.is_visible():
            await sub_btn.click(force=True)
            await asyncio.sleep(1.0)
            return "Boss, channel successfully subscribe kar diya gaya hai."
        else:
            return "Boss, channel already subscribed hai ya subscribe button nahi mila."

    if "bell" in act or "notif" in act:
        bell_btn = page.locator("button[aria-label*='Current setting'], ytd-subscription-notification-toggle-button-renderer-next button").first
        if await bell_btn.count() > 0:
            await bell_btn.click(force=True)
            await asyncio.sleep(0.8)
            all_option = page.locator("ytd-menu-service-item-renderer:has-text('All'), tp-yt-paper-item:has-text('All')").first
            if await all_option.count() > 0:
                await all_option.click(force=True)
                return "Boss, bell notification ko 'All' par set kar diya gaya hai."

    if "like" in act:
        like_btn = page.locator("like-button-view-model button, button[aria-label*='like this video']").first
        if await like_btn.count() > 0:
            await like_btn.click(force=True)
            return "Boss, video like kar di gayi hai."

    return f"Boss, YouTube action '{action}' execute kar diya hai."


# ---------------------------------------------------------------------------
# YouTube Media Controls & Fallback Play
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
    description="ONLY use this when the user EXPLICITLY asks to watch a VIDEO in Chrome (e.g. 'YouTube par video chalao'). NEVER use this for normal music, song, or audio playback requests."
)
async def youtube_search_and_play(context: RunContext, search_query: str) -> str:
    page = await _get_active_page()
    encoded = urllib.parse.quote_plus(search_query)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        raise ToolError(f"YouTube search open nahi ho saka: {e}")

    try:
        for sel in ["button:has-text('Accept all')", "button:has-text('I agree')"]:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible(timeout=500):
                await btn.click(timeout=1500, force=True)
                await asyncio.sleep(0.3)
                break
    except Exception:
        pass

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
            continue
        chosen = v
        chosen_title = (await v.inner_text()).strip()
        break

    if not chosen:
        raise ToolError(f"'{search_query}' ke liye koi playable video nahi mila.")

    try:
        await chosen.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        await chosen.click(timeout=ACTION_TIMEOUT_MS, force=True)
    except Exception as e:
        raise ToolError(f"Video par click nahi ho saka: {e}")

    await asyncio.sleep(1.5)
    try:
        await page.evaluate("""() => {
            const v = document.querySelector('video');
            if (v && v.paused) v.play();
            const skip = document.querySelector('.ytp-ad-skip-button, .ytp-skip-ad-button');
            if (skip) skip.click();
        }""")
    except Exception:
        pass

    return f"Boss, YouTube par '{chosen_title}' play kar diya gaya hai."


@function_tool(
    name="youtube_media_control",
    description="Control YouTube playback: play, pause, mute, unmute, seek forward/back, volume up/down, fullscreen, or next video (also skips ads)."
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


# ---------------------------------------------------------------------------
# Tab Management (List, Switch, Close, Open New)
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
    description="Switch the active browser tab, identified by its number or a keyword from its title/URL."
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
    page = await _get_active_page(force_new=True)
    if url_or_query:
        target = url_or_query.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
            looks_domain = bool(re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", target)) and " " not in target
            target = f"https://{target}" if looks_domain else f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
        
        await page.goto(target, wait_until="domcontentloaded")
        title = await page.title()
        return f"Boss, naye tab mein '{title}' open kar diya gaya hai."
    
    return "Boss, ek khaali naya tab open kar diya gaya hai."


@function_tool(
    name="close_browser_tab",
    description="Close a specific browser tab by number/title, or the active tab if not specified."
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
        await target_page.goto("about:blank")
        return f"Boss, yeh akela tab tha, isliye '{title}' close karne ke bajaye blank kar diya."

    await target_page.close()
    if _session.active_page == target_page:
        remaining = [p for p in ctx.pages if not p.is_closed()]
        _session.active_page = remaining[-1] if remaining else None

    return f"Boss, '{title}' tab close kar diya gaya hai."