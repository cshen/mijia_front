"""
Mijia Web Dashboard — FastAPI backend
Wraps mijiaAPI to expose a REST API consumed by the Vue 3 frontend.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import parse

import requests as req_lib
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mijiaAPI import APIError, LoginError, mijiaAPI
from mijiaAPI.devices import get_device_info

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys as _sys
_BASE_DIR = Path(getattr(_sys, "_MEIPASS", Path(__file__).parent))
_STATIC_DIR = _BASE_DIR / "static"

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Mijia Web Dashboard", docs_url="/docs")

# ── Global state ───────────────────────────────────────────────────────────────
_api: Optional[mijiaAPI] = None
_login_state: Dict[str, Any] = {"status": "idle", "qr_url": None, "error": None}


def get_api() -> mijiaAPI:
    global _api
    if _api is None:
        _api = mijiaAPI()
    return _api


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.get("/api/auth/status")
async def auth_status():
    """Return whether the API token is valid."""
    api = get_api()
    authenticated = await asyncio.to_thread(lambda: api.available)
    return {"authenticated": authenticated, "login_state": _login_state}


@app.post("/api/auth/start")
async def start_auth():
    """
    Initiate QR-code login flow.
    Returns the Xiaomi QR image URL and starts a background task that
    long-polls for scan completion.
    """
    global _login_state
    api = get_api()

    authenticated = await asyncio.to_thread(lambda: api.available)
    if authenticated:
        _login_state = {"status": "done", "qr_url": None, "error": None}
        return {"status": "done"}

    if _login_state.get("status") == "pending":
        return {"status": "pending", "qr_url": _login_state["qr_url"]}

    _login_state = {"status": "starting", "qr_url": None, "error": None}

    # Step 1: Get serviceLogin location params (also refreshes token if still valid)
    try:
        location_data = await asyncio.to_thread(api._get_location)
    except Exception as exc:
        _login_state = {"status": "error", "qr_url": None, "error": str(exc)}
        raise HTTPException(status_code=500, detail=str(exc))

    if location_data.get("code", -1) == 0:
        # Token was quietly refreshed — no QR needed
        _login_state = {"status": "done", "qr_url": None, "error": None}
        return {"status": "done"}

    # Step 2: Fetch the QR image URL + long-poll URL
    headers = {
        "User-Agent": api.user_agent,
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
        "Connection": "keep-alive",
    }
    login_url = "https://account.xiaomi.com/longPolling/loginUrl"
    location_data.update({
        "theme": "",
        "bizDeviceType": "",
        "_hasLogo": "false",
        "_qrsize": "240",
        "_dc": str(int(time.time() * 1000)),
    })
    full_url = login_url + "?" + parse.urlencode(location_data)

    try:
        resp = await asyncio.to_thread(req_lib.get, full_url, **{"headers": headers})
        text = resp.text.replace("&&&START&&&", "")
        login_data = json.loads(text)
    except Exception as exc:
        _login_state = {"status": "error", "qr_url": None, "error": str(exc)}
        raise HTTPException(status_code=500, detail=f"Failed to obtain QR code: {exc}")

    if login_data.get("code", -1) != 0:
        msg = login_data.get("desc", str(login_data))
        _login_state = {"status": "error", "qr_url": None, "error": msg}
        raise HTTPException(status_code=500, detail=msg)

    qr_url = login_data.get("qr")
    lp_url = login_data["lp"]
    _login_state = {"status": "pending", "qr_url": qr_url, "error": None}

    # Step 3: Background task — long-poll for scan result
    async def _poll_login() -> None:
        global _login_state
        try:
            session = req_lib.Session()
            lp_resp = await asyncio.to_thread(
                lambda: session.get(lp_url, headers=headers, timeout=120)
            )
            lp_text = lp_resp.text.replace("&&&START&&&", "")
            lp_data = json.loads(lp_text)

            if lp_data.get("code", -1) != 0:
                _login_state = {
                    "status": "error",
                    "qr_url": None,
                    "error": lp_data.get("desc", str(lp_data)),
                }
                return

            # Persist auth
            for key in ["psecurity", "nonce", "ssecurity", "passToken", "userId", "cUserId"]:
                api.auth_data[key] = lp_data[key]
            await asyncio.to_thread(lambda: session.get(lp_data["location"], headers=headers))
            api.auth_data.update(session.cookies.get_dict())
            api.auth_data["expireTime"] = int(
                (datetime.now() + timedelta(days=30)).timestamp() * 1000
            )
            api._save_auth_data()
            api._init_session()
            _login_state = {"status": "done", "qr_url": None, "error": None}

        except asyncio.TimeoutError:
            _login_state = {"status": "timeout", "qr_url": None, "error": "Scan timed out — please retry"}
        except Exception as exc:
            _login_state = {"status": "error", "qr_url": None, "error": str(exc)}

    asyncio.create_task(_poll_login())
    return {"status": "pending", "qr_url": qr_url}


# ── Devices ────────────────────────────────────────────────────────────────────

@app.get("/api/devices")
async def list_devices():
    """Return all devices across all homes."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        devices = await asyncio.to_thread(api.get_devices_list)
        return devices
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/devices/power")
async def devices_power():
    """
    Return on/off state for every device that exposes a readable 'on' property.
    Uses cached MIoT specs and a single batch prop-get call per device.
    Response: [{did, on: true|false|null}, ...]
    """
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        devices = await asyncio.to_thread(api.get_devices_list)
        params = []
        for device in devices:
            try:
                info = await asyncio.to_thread(
                    get_device_info, device["model"], api.auth_data_path.parent
                )
                on_prop = next(
                    (p for p in info.get("properties", [])
                     if p["name"] == "on" and "r" in (p.get("rw") or "")),
                    None
                )
                if on_prop:
                    params.append({
                        "did": device["did"],
                        "siid": on_prop["method"]["siid"],
                        "piid": on_prop["method"]["piid"],
                    })
            except Exception:
                continue

        if not params:
            return []

        results = await asyncio.to_thread(api.get_devices_prop, params)
        if isinstance(results, dict):
            results = [results]

        return [
            {"did": r["did"], "on": r.get("value") if r.get("code") == 0 else None}
            for r in results
        ]
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/api/homes")
async def list_homes():
    """Return all homes."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        homes = await asyncio.to_thread(api.get_homes_list)
        return homes
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/device/{did}/info")
async def device_info(did: str):
    """Return MIoT spec (properties + actions) for a device."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        devices = await asyncio.to_thread(api.get_devices_list)
        device = next((d for d in devices if d["did"] == did), None)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        info = await asyncio.to_thread(
            get_device_info, device["model"], api.auth_data_path.parent
        )
        return info
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Properties ─────────────────────────────────────────────────────────────────

class PropsGetRequest(BaseModel):
    props: List[Dict[str, Any]]  # [{siid, piid}, ...]


@app.post("/api/device/{did}/props/get")
async def get_props(did: str, body: PropsGetRequest):
    """Batch-read device properties."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        params = [{"did": did, "siid": p["siid"], "piid": p["piid"]} for p in body.props]
        result = await asyncio.to_thread(api.get_devices_prop, params)
        return result
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class PropSetRequest(BaseModel):
    siid: int
    piid: int
    value: Any


@app.post("/api/device/{did}/prop/set")
async def set_prop(did: str, body: PropSetRequest):
    """Write a single device property."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        param = {"did": did, "siid": body.siid, "piid": body.piid, "value": body.value}
        result = await asyncio.to_thread(api.set_devices_prop, param)
        return result
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Actions ────────────────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    siid: int
    aiid: int
    value: Optional[List[Any]] = None


@app.post("/api/device/{did}/action")
async def run_device_action(did: str, body: ActionRequest):
    """Execute a device action."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        param: Dict[str, Any] = {"did": did, "siid": body.siid, "aiid": body.aiid}
        if body.value is not None:
            param["value"] = body.value
        result = await asyncio.to_thread(api.run_action, param)
        return result
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Scenes ─────────────────────────────────────────────────────────────────────

@app.get("/api/scenes")
async def list_scenes():
    """Return all manual scenes across all homes."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        scenes = await asyncio.to_thread(api.get_scenes_list)
        return scenes
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class RunSceneRequest(BaseModel):
    home_id: str


@app.post("/api/scenes/{scene_id}/run")
async def run_scene(scene_id: str, body: RunSceneRequest):
    """Trigger a manual scene."""
    api = get_api()
    if not await asyncio.to_thread(lambda: api.available):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = await asyncio.to_thread(api.run_scene, scene_id, body.home_id)
        return {"success": bool(result)}
    except APIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Static / SPA ───────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=True)
