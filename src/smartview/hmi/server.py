"""驾驶室 HMI：FastAPI + 单页中文界面。

启动后用车载触摸屏浏览器（kiosk 模式）打开 ``http://<orin-ip>:8080/``。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from smartview import __version__
from smartview.bus import StateBus
from smartview.pipeline.controls import Controls

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


class MuteBody(BaseModel):
    seconds: float = Field(30.0, ge=1, le=600)


class SettingsBody(BaseModel):
    speed_kmh: float | None = Field(None, ge=0, le=30)
    speed_source: Literal["manual", "nmea"] | None = None
    sensitivity: Literal["low", "medium", "high"] | None = None


class TestAlarmBody(BaseModel):
    level: int = Field(2, ge=1, le=3)


class PurgeBody(BaseModel):
    channel: str | None = None


def _placeholder_jpeg(text: str = "NO SIGNAL") -> bytes:
    img = np.full((180, 320, 3), 40, dtype=np.uint8)
    cv2.putText(img, text, (60, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (90, 90, 200), 2, cv2.LINE_AA)
    return cv2.imencode(".jpg", img)[1].tobytes()


def create_app(bus: StateBus, controls: Controls) -> FastAPI:
    app = FastAPI(title="smartview HMI", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    placeholder = _placeholder_jpeg()

    def full_state() -> dict[str, Any]:
        st = bus.snapshot()
        st["settings"] = controls.settings()
        st["version_str"] = __version__
        return st

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/state")
    def api_state() -> JSONResponse:
        return JSONResponse(full_state())

    @app.get("/api/health")
    def api_health() -> JSONResponse:
        st = bus.snapshot()
        return JSONResponse({"cameras": {k: v["health"] for k, v in st["cameras"].items()}, "alarm": st["alarm"], "system": st["system"]})

    @app.get("/api/events")
    def api_events(limit: int = 50, since: float | None = None, min_level: int = 0) -> JSONResponse:
        return JSONResponse({"events": controls.events(limit=min(max(limit, 1), 500), since=since, min_level=min_level), "stats": controls.stats()})

    @app.get("/api/events/{event_id}")
    def api_event(event_id: int) -> JSONResponse:
        ev = controls.event(event_id)
        if ev is None:
            raise HTTPException(404, "事件不存在")
        return JSONResponse(ev)

    @app.get("/api/events/{event_id}/snapshot.jpg")
    def api_event_snapshot(event_id: int):
        ev = controls.event(event_id)
        if ev is None or not ev.get("snapshot_path") or not Path(ev["snapshot_path"]).exists():
            raise HTTPException(404, "无快照")
        return FileResponse(ev["snapshot_path"], media_type="image/jpeg")

    @app.get("/api/events/{event_id}/clip")
    def api_event_clip(event_id: int):
        ev = controls.event(event_id)
        if ev is None or not ev.get("clip_path") or not Path(ev["clip_path"]).exists():
            raise HTTPException(404, "无片段")
        return FileResponse(ev["clip_path"], media_type="video/x-msvideo", filename=Path(ev["clip_path"]).name)

    @app.post("/api/ack")
    def api_ack() -> JSONResponse:
        return JSONResponse(controls.ack())

    @app.post("/api/mute")
    def api_mute(body: MuteBody | None = None) -> JSONResponse:
        secs = body.seconds if body else 30.0
        return JSONResponse(controls.mute(secs))

    @app.post("/api/unmute")
    def api_unmute() -> JSONResponse:
        return JSONResponse(controls.unmute())

    @app.get("/api/settings")
    def api_settings() -> JSONResponse:
        return JSONResponse(controls.settings())

    @app.put("/api/settings")
    def api_put_settings(body: SettingsBody) -> JSONResponse:
        return JSONResponse(controls.update_settings(body.speed_kmh, body.speed_source, body.sensitivity))

    @app.post("/api/test-alarm")
    def api_test_alarm(body: TestAlarmBody | None = None) -> JSONResponse:
        return JSONResponse(controls.test_alarm(body.level if body else 2))

    @app.get("/api/purge")
    def api_purge_status() -> JSONResponse:
        return JSONResponse(controls.purge_status())

    @app.post("/api/purge")
    def api_purge(body: PurgeBody | None = None) -> JSONResponse:
        return JSONResponse(controls.purge(body.channel if body else None))

    @app.get("/api/cam/{cam_id}.jpg")
    def api_cam_jpeg(cam_id: str) -> Response:
        data = bus.cam_jpeg(cam_id)
        return Response(content=data or placeholder, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/stream/{cam_id}.mjpg")
    async def stream(cam_id: str, request: Request, frames: int | None = None, fps: float = 8.0) -> StreamingResponse:
        interval = 1.0 / max(min(fps, 30.0), 0.5)

        async def gen():
            sent = 0
            last = None
            while True:
                if await request.is_disconnected():
                    break
                data = bus.cam_jpeg(cam_id)
                if data is None:
                    data = placeholder
                if data is not last or frames is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
                    last = data
                    sent += 1
                    if frames is not None and sent >= frames:
                        break
                await asyncio.sleep(interval)

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store"})

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        version = -1
        try:
            while True:
                cur = bus.version
                if cur != version:
                    version = cur
                    await sock.send_text(json.dumps(full_state(), ensure_ascii=False))
                new_version = await asyncio.to_thread(bus.wait_for_change, version, 1.0)
                if new_version != version:
                    await asyncio.sleep(0.2)  # ≤ 5 Hz
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            log.debug("ws 结束: %s", exc)

    return app
