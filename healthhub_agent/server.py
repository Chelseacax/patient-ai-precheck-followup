import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

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
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%H:%M:%S"),
        "action": action,
        "params": params,
        "source": source,
        "status": "queued",
        "result": None,
        "error": None,
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


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(dispatcher.start_browser())
    yield
    await dispatcher.stop_browser()


app = FastAPI(title="HealthHub Agent Bridge", lifespan=lifespan)


# ── API routes ─────────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    return {
        "ready": dispatcher.ready,
        "current_url": await dispatcher.current_url(),
        "action_count": dispatcher.action_count,
    }


@app.get("/api/actions")
async def list_actions():
    return {
        name: {
            "description": cls.DESCRIPTION,
            "params_schema": cls.PARAMS_SCHEMA,
        }
        for name, cls in REGISTRY.items()
    }


@app.get("/api/log")
async def get_log():
    return list(reversed(action_log))


class ActionRequest(BaseModel):
    action: str
    params: dict = {}
    source: str = "api"


class NavigateRequest(BaseModel):
    page: str  # home | appointments | medications | lab-reports | profile


class BookingRequest(BaseModel):
    institution: str
    specialty: str
    date: str        # YYYY-MM-DD
    time: str        # e.g. "14:00" or "2:00 PM"
    reason: str


@app.post("/api/navigate")
async def navigate(req: NavigateRequest):
    try:
        result = await dispatcher.navigate_healthhub(req.page)
        await broadcast({"type": "navigate", "page": req.page})
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/booking/full")
async def booking_full(req: BookingRequest):
    if not dispatcher.ready:
        return JSONResponse(status_code=503, content={"error": "Browser not ready"})
    await broadcast({"type": "booking_start", "details": req.model_dump()})
    try:
        result = await dispatcher.book_on_healthhub(
            req.institution, req.specialty, req.date, req.time, req.reason
        )
        await broadcast({"type": "booking_done", "result": result})
        return result
    except Exception as exc:
        import traceback
        err = traceback.format_exc()
        print(f"[booking_full ERROR] {err}")
        await broadcast({"type": "booking_error", "error": str(exc)})
        return JSONResponse(status_code=500, content={"error": str(exc), "detail": err})


@app.post("/api/agent/action")
async def run_action(req: ActionRequest):
    # Validate
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


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_ws.append(ws)
    # Send current log on connect
    await ws.send_text(json.dumps({"type": "log_sync", "log": list(reversed(action_log))}))
    try:
        while True:
            if dispatcher.ready:
                screenshot = await dispatcher.screenshot_b64()
                if screenshot:
                    url = await dispatcher.current_url()
                    await ws.send_text(json.dumps({
                        "type": "screenshot",
                        "data": screenshot,
                        "url": url,
                    }))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ws in connected_ws:
            connected_ws.remove(ws)


# ── Static mount — optional monitoring panel ───────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=7001, reload=False)
