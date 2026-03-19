import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dispatcher import dispatcher
from actions import REGISTRY


# ── In-memory log ──────────────────────────────────────────────────────────────
action_log: list[dict] = []
connected_ws: list[WebSocket] = []


def make_log_entry(action: str, params: dict, source: str = "api") -> dict:
    return {
        "id":        str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%H:%M:%S"),
        "action":    action,
        "params":    params,
        "source":    source,
        "status":    "queued",
        "result":    None,
        "error":     None,
    }


async def broadcast(msg: dict):
    dead = []
    for ws in connected_ws:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_ws.remove(ws)


# ── Lifespan ────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(dispatcher.start_browser())
    yield
    await dispatcher.stop_browser()


app = FastAPI(title="HealthHub Agent Bridge — Live Site", lifespan=lifespan)


# ── Status ──────────────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    on_singpass = await dispatcher.is_singpass_page()
    return {
        "ready":        dispatcher.ready,
        "current_url":  await dispatcher.current_url(),
        "action_count": dispatcher.action_count,
        "on_singpass_page": on_singpass,
    }


@app.get("/api/actions")
async def list_actions():
    return {
        name: {
            "description":   cls.DESCRIPTION,
            "params_schema": cls.PARAMS_SCHEMA,
        }
        for name, cls in REGISTRY.items()
    }


@app.get("/api/log")
async def get_log():
    return list(reversed(action_log))


# ── Request models ──────────────────────────────────────────────────────────────
class ActionRequest(BaseModel):
    action: str
    params: dict = {}
    source: str = "api"


class NavigateRequest(BaseModel):
    page: str   # home | appointments | medications | lab-reports | profile | dashboard


class BookingRequest(BaseModel):
    institution: str
    specialty:   str
    date:        str   # YYYY-MM-DD
    time:        str   # e.g. "14:00" or "2:00 PM"
    reason:      str


class BrowserActionRequest(BaseModel):
    action:    str
    x:         int = 0
    y:         int = 0
    text:      str = ""    # text to type OR text/label to click
    key:       str = ""
    selector:  str = ""    # optional CSS selector for direct targeting
    role:      str = ""    # ARIA role (button, link, menuitem, …)
    distance:  int = 600   # pixels to scroll (for scroll action)
    direction: str = "down" # scroll direction: "up" or "down"


# ── Browser state (screenshot + Singpass flag) ──────────────────────────────────
@app.get("/api/browser/state")
async def get_browser_state():
    state = await dispatcher.get_page_state()
    # Broadcast Singpass status change via WebSocket so frontend can react
    if state.get("on_singpass_page"):
        await broadcast({"type": "singpass_wall", "url": state.get("url", "")})
    return state


# ── Browser click/type actions ──────────────────────────────────────────────────
@app.post("/api/browser/action")
async def do_browser_action(req: BrowserActionRequest):
    if not dispatcher.ready or not dispatcher._page:
        return {"error": "Browser not ready"}
    try:
        if req.action == "click":
            # Use JS elementFromPoint().click() — this triggers React synthetic events
            # which raw mouse.click() does not reliably do on SPA pages.
            page = dispatcher._page
            clicked = await page.evaluate(f"""() => {{
                const el = document.elementFromPoint({req.x}, {req.y});
                if (!el) return false;
                el.click();
                return true;
            }}""")
            if not clicked:
                # Fallback to raw mouse click if JS found nothing at those coords
                await page.mouse.click(req.x, req.y)
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

        elif req.action == "click_text":
            # ARIA / text-based click — much more reliable on live sites
            import re as _re
            page = dispatcher._page
            clicked = False

            # 1. If a CSS selector is provided, use it directly
            if req.selector:
                loc = page.locator(req.selector)
                if await loc.first.is_visible():
                    await loc.first.click(timeout=6000)
                    clicked = True

            # 2. Try by ARIA role + name — EXACT match first to avoid false matches.
            #    e.g. text="No" with partial regex also matches "Sign up now" (contains "no").
            #    If exact match finds nothing, fall back to partial for longer button labels.
            if not clicked and req.role and req.text:
                exact_pat = _re.compile(f"^{_re.escape(req.text)}$", _re.IGNORECASE)
                loc = page.get_by_role(req.role, name=exact_pat)
                try:
                    if await loc.first.is_visible(timeout=1500):
                        await loc.first.click(timeout=6000)
                        clicked = True
                except Exception:
                    pass
                if not clicked:
                    # Partial match fallback for buttons with longer accessible names
                    partial_pat = _re.compile(_re.escape(req.text), _re.IGNORECASE)
                    loc = page.get_by_role(req.role, name=partial_pat)
                    try:
                        if await loc.first.is_visible(timeout=1500):
                            await loc.first.click(timeout=6000)
                            clicked = True
                    except Exception:
                        pass

            # 3. Try any role matching the text label — exact match first, then partial
            if not clicked and req.text:
                for role in ["button", "link", "menuitem", "option", "tab"]:
                    exact_pat = _re.compile(f"^{_re.escape(req.text)}$", _re.IGNORECASE)
                    loc = page.get_by_role(role, name=exact_pat)
                    try:
                        if await loc.first.is_visible(timeout=1500):
                            await loc.first.click(timeout=6000)
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    for role in ["button", "link", "menuitem", "option", "tab"]:
                        partial_pat = _re.compile(_re.escape(req.text), _re.IGNORECASE)
                        loc = page.get_by_role(role, name=partial_pat)
                        try:
                            if await loc.first.is_visible(timeout=1500):
                                await loc.first.click(timeout=6000)
                                clicked = True
                                break
                        except Exception:
                            continue

            # 4. Try label elements (for radio/checkbox inputs) — exact match first
            if not clicked and req.text:
                exact_pat = _re.compile(f"^{_re.escape(req.text)}$", _re.IGNORECASE)
                loc = page.locator("label").filter(has_text=exact_pat)
                try:
                    if await loc.first.is_visible(timeout=1500):
                        await loc.first.click(timeout=6000)
                        clicked = True
                except Exception:
                    pass
                if not clicked:
                    # Partial fallback for labels with longer text
                    partial_pat = _re.compile(_re.escape(req.text), _re.IGNORECASE)
                    loc = page.locator("label").filter(has_text=partial_pat)
                    try:
                        if await loc.first.is_visible(timeout=1500):
                            await loc.first.click(timeout=6000)
                            clicked = True
                    except Exception:
                        pass

            # 5. Try radio/checkbox inputs by associated label — exact match only
            if not clicked and req.text:
                for sel in [
                    "[role='radio']", "[role='checkbox']",
                    "input[type='radio']", "input[type='checkbox']",
                ]:
                    try:
                        els = page.locator(sel)
                        count = await els.count()
                        for i in range(count):
                            el = els.nth(i)
                            if not await el.is_visible(timeout=500):
                                continue
                            # Check associated label — use EXACT match to avoid
                            # "No" matching "No additional symptoms", etc.
                            label_text = ""
                            try:
                                el_id = await el.get_attribute("id")
                                if el_id:
                                    lbl = page.locator(f"label[for='{el_id}']")
                                    label_text = (await lbl.inner_text()).strip()
                            except Exception:
                                pass
                            if _re.fullmatch(_re.escape(req.text), label_text, _re.IGNORECASE):
                                await el.click(timeout=6000)
                                clicked = True
                                break
                        if clicked:
                            break
                    except Exception:
                        continue

            # 6. Fallback: get_by_text — exact match first, then partial
            if not clicked and req.text:
                # Exact text match (Playwright exact=True requires full string equality)
                loc = page.get_by_text(req.text, exact=True)
                try:
                    if await loc.first.is_visible(timeout=2000):
                        await loc.first.click(timeout=6000)
                        clicked = True
                except Exception:
                    pass
                if not clicked:
                    # Partial fallback (last resort)
                    loc = page.get_by_text(_re.compile(_re.escape(req.text), _re.IGNORECASE))
                    try:
                        if await loc.first.is_visible(timeout=2000):
                            await loc.first.click(timeout=6000)
                            clicked = True
                    except Exception:
                        pass

            if not clicked:
                return {"error": f"Could not find element matching text: '{req.text}'"}

        elif req.action == "read_page":
            page = dispatcher._page
            url   = page.url
            title = await page.title()

            # 1. Interactive elements with centre coordinates (so LLM can use action=click x,y)
            handles = await page.query_selector_all(
                "a, button, [role='button'], [role='link'], [role='menuitem'], "
                "[role='radio'], [role='checkbox'], label, input[type='submit']"
            )
            elements = []
            seen = set()

            async def _try_add_el(el):
                try:
                    if not await el.is_visible():
                        return
                    # Skip header/footer chrome — prevents "Sign up now", "Log out",
                    # newsletter links etc. from appearing in interactive_elements and
                    # being accidentally clicked by the LLM.
                    in_chrome = await el.evaluate(
                        "el => !!el.closest('header, footer, [role=\"banner\"], [role=\"contentinfo\"]')"
                    )
                    if in_chrome:
                        return
                    t = (await el.inner_text()).strip().replace("\n", " ")
                    if not t or t in seen:
                        return
                    seen.add(t)
                    box = await el.bounding_box()
                    entry = {"text": t}
                    if box:
                        entry["x"] = int(box["x"] + box["width"] / 2)
                        entry["y"] = int(box["y"] + box["height"] / 2)
                    elements.append(entry)
                except Exception:
                    pass

            # Priority pass: always include Yes/No/Confirm buttons regardless of DOM position
            for priority_text in ["Yes", "No", "Confirm", "Next", "Continue", "Submit", "Back"]:
                try:
                    import re as _re2
                    loc = page.get_by_role("button", name=_re2.compile(f"^{priority_text}$", _re2.IGNORECASE))
                    count = await loc.count()
                    for i in range(count):
                        await _try_add_el(await loc.nth(i).element_handle())
                except Exception:
                    pass

            # General pass: scan up to first 80 visible elements in DOM order
            for el in handles:
                if len(elements) >= 80:
                    break
                await _try_add_el(el)

            # 2. All visible text via JS tree walker — catches div/p/span/li including
            #    short words like "Fever", "Cough" (no length filter) and question text
            #    inside div containers that CSS selectors miss
            try:
                page_text = await page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();
                    // Prefer main content area, fall back to body
                    const root = document.querySelector(
                        'main, [role="main"], .main-content, #main-content, article'
                    ) || document.body;
                    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                    let node;
                    while ((node = walker.nextNode())) {
                        const t = node.textContent.trim().replace(/\\s+/g, ' ');
                        if (t.length < 2) continue;
                        const el = node.parentElement;
                        if (!el) continue;
                        const s = window.getComputedStyle(el);
                        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0')
                            continue;
                        if (!seen.has(t)) { seen.add(t); results.push(t); }
                    }
                    return results.slice(0, 60);
                }""")
            except Exception:
                page_text = []

            return {
                "url": url,
                "title": title,
                "interactive_elements": elements,
                "page_text": page_text,
            }

        elif req.action == "js_eval":
            result = await dispatcher._page.evaluate(req.text)
            return {"result": result}

        elif req.action == "type":
            await dispatcher._page.keyboard.type(req.text)
        elif req.action == "press":
            await dispatcher._page.keyboard.press(req.key)
        elif req.action == "clear_modals":
            await dispatcher._clear_modals()

        elif req.action == "scroll":
            page = dispatcher._page
            dist = req.distance if req.distance else 600
            # Negative delta scrolls UP; positive scrolls DOWN
            delta = -dist if req.direction == "up" else dist

            # If a CSS selector is given, scroll that specific element
            if req.selector:
                el = page.locator(req.selector).first
                try:
                    await el.evaluate(f"el => el.scrollBy(0, {delta})")
                except Exception:
                    pass  # fallback to page-level scroll below
            else:
                # Use mouse.wheel — works correctly inside nested scrollable divs
                await page.mouse.wheel(0, delta)

            await asyncio.sleep(0.6)  # let lazy-loaded content render
            return {"scrolled": delta, "direction": req.direction}
        await asyncio.sleep(1.2)  # extra wait for React/SPA state updates to settle

        # Auto-clear any popup/modal that appeared as a side-effect of the action,
        # then re-fire the original click so the underlying form still advances.
        # The HealthHub newsletter ant-modal (z=1000) appears after triage Yes/No
        # clicks and absorbs them — dismissing it alone is not enough, we must retry.
        if req.action in ("click", "click_text"):
            popup_present = await dispatcher._page.evaluate("""() => {
                const wrap = document.querySelector('.ant-modal-wrap');
                return wrap && window.getComputedStyle(wrap).display !== 'none';
            }""")
            if popup_present:
                await dispatcher._clear_modals()
                await asyncio.sleep(0.8)
                # Retry the original click now that the popup is gone
                try:
                    import re as _re_retry
                    page = dispatcher._page
                    if req.action == "click_text" and req.text:
                        for role in ["button", "link"]:
                            loc = page.get_by_role(role, name=_re_retry.compile(req.text, _re_retry.IGNORECASE))
                            try:
                                if await loc.first.is_visible(timeout=1500):
                                    await loc.first.click(timeout=4000)
                                    break
                            except Exception:
                                continue
                    elif req.action == "click":
                        await page.evaluate(f"""() => {{
                            const el = document.elementFromPoint({req.x}, {req.y});
                            if (el) el.click();
                        }}""")
                    await asyncio.sleep(1.0)
                except Exception:
                    pass

        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


# ── Wait for Singpass login to complete ─────────────────────────────────────────
@app.post("/api/singpass/wait")
async def wait_for_singpass(timeout_ms: int = 180_000):
    """
    Long-poll: blocks until the browser leaves the Singpass domain (user scanned QR).
    Returns {"logged_in": True} or {"timed_out": True}.
    """
    success = await dispatcher.wait_for_post_singpass(timeout_ms)
    if success:
        await broadcast({"type": "singpass_done"})
        return {"logged_in": True}
    return {"timed_out": True}


# ── Navigate ─────────────────────────────────────────────────────────────────────
@app.post("/api/navigate")
async def navigate(req: NavigateRequest):
    try:
        result = await dispatcher.navigate_healthhub(req.page)
        await broadcast({"type": "navigate", "page": req.page, "url": result.get("url", "")})
        if result.get("on_singpass_page"):
            await broadcast({"type": "singpass_wall", "step": "navigate"})
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ── Full booking ─────────────────────────────────────────────────────────────────
@app.post("/api/booking/full")
async def booking_full(req: BookingRequest):
    if not dispatcher.ready:
        return JSONResponse(status_code=503, content={"error": "Browser not ready"})

    await broadcast({"type": "booking_start", "details": req.model_dump()})
    try:
        result = await dispatcher.book_on_healthhub(
            req.institution, req.specialty, req.date, req.time, req.reason
        )
        # Graceful ui_mismatch — broadcast so frontend / agent know to ask user
        if result.get("ui_mismatch"):
            await broadcast({"type": "ui_mismatch", "result": result})
        elif result.get("on_singpass_page"):
            await broadcast({"type": "singpass_wall", "step": "booking"})
        else:
            await broadcast({"type": "booking_done", "result": result})
        return result
    except Exception as exc:
        import traceback
        err = traceback.format_exc()
        print(f"[booking_full ERROR] {err}")
        await broadcast({"type": "booking_error", "error": str(exc)})
        return JSONResponse(status_code=500, content={"error": str(exc), "detail": err})


# ── Agent action (registry) ──────────────────────────────────────────────────────
@app.post("/api/agent/action")
async def run_action(req: ActionRequest):
    error = dispatcher.validate(req.action, req.params)
    if error:
        return JSONResponse(status_code=400, content={"success": False, "error": error})

    entry = make_log_entry(req.action, req.params, req.source)
    action_log.append(entry)
    await broadcast({"type": "action_started", "entry": entry})
    entry["status"] = "running"
    await broadcast({"type": "action_update", "entry": entry})

    try:
        result = await dispatcher.execute(req.action, req.params)
        entry["status"] = "success"
        entry["result"] = result
        await broadcast({"type": "action_complete", "entry": entry})
        return {"success": True, "action": req.action, "result": result}
    except Exception as exc:
        entry["status"] = "failed"
        entry["error"] = str(exc)
        await broadcast({"type": "action_failed", "entry": entry})
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


# ── WebSocket — live screenshot stream ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_ws.append(ws)
    await ws.send_text(json.dumps({"type": "log_sync", "log": list(reversed(action_log))}))
    try:
        while True:
            if dispatcher.ready:
                state = await dispatcher.get_page_state()
                if state.get("image"):
                    await ws.send_text(json.dumps({
                        "type":             "screenshot",
                        "data":             state["image"],
                        "url":              state.get("url", ""),
                        "on_singpass_page": state.get("on_singpass_page", False),
                    }))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ws in connected_ws:
            connected_ws.remove(ws)


# ── Static monitoring panel ──────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=7001, reload=False)
