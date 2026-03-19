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
            # Raw pixel click
            await dispatcher._page.mouse.click(req.x, req.y)

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

            # 2. Try by ARIA role + name
            if not clicked and req.role and req.text:
                loc = page.get_by_role(req.role, name=_re.compile(req.text, _re.IGNORECASE))
                if await loc.first.is_visible():
                    await loc.first.click(timeout=6000)
                    clicked = True

            # 3. Try any role matching the text label
            if not clicked and req.text:
                for role in ["button", "link", "menuitem", "option", "tab"]:
                    loc = page.get_by_role(role, name=_re.compile(req.text, _re.IGNORECASE))
                    try:
                        if await loc.first.is_visible(timeout=1500):
                            await loc.first.click(timeout=6000)
                            clicked = True
                            break
                    except Exception:
                        continue

            # 4. Fallback: get_by_text (partial match)
            if not clicked and req.text:
                loc = page.get_by_text(_re.compile(req.text, _re.IGNORECASE))
                if await loc.first.is_visible(timeout=2000):
                    await loc.first.click(timeout=6000)
                    clicked = True

            if not clicked:
                return {"error": f"Could not find element matching text: '{req.text}'"}

        elif req.action == "read_page":
            # Return the current URL + visible text links/buttons for agent context
            page = dispatcher._page
            url   = page.url
            title = await page.title()
            # Grab visible interactive text
            handles = await page.query_selector_all("a, button, [role='button'], [role='link'], [role='menuitem']")
            elements = []
            for el in handles[:60]:  # cap at 60 to avoid huge payloads
                try:
                    visible = await el.is_visible()
                    if visible:
                        t = (await el.inner_text()).strip().replace("\n", " ")
                        if t:
                            elements.append(t)
                except Exception:
                    pass
            return {"url": url, "title": title, "interactive_elements": elements}

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
        await asyncio.sleep(0.5)
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
