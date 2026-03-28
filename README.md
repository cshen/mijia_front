# 🏠 Mijia Web Dashboard

> 🤖 **Note:** This project was created with the assistance of [GitHub Copilot](https://github.com/features/copilot) AI coding.

A clean, dark-themed web dashboard for viewing and controlling all your **Xiaomi Mi Home (米家)** IoT devices — lights, switches, sensors, air purifiers, and more — directly from your browser.

Built on top of [`mijiaAPI`](https://github.com/Do1e/mijia-api) with a **FastAPI** backend and a **Vue 3** single-page frontend.

---

## ✨ Features

- 🔐 **QR-code login** — scan once with the Mi Home app, token is cached for 30 days
- 🏡 **Homes & rooms** — devices grouped by your Mi Home layout
- 💡 **Smart controls** — automatically renders the right UI per property type:
  - Toggle switch for on/off (`bool`)
  - Slider for brightness, color temperature, fan speed, target temperature, etc. (`int` / `float` with range)
  - Dropdown for mode selection (`value-list` enums)
  - Text field for string properties
  - Read-only display for sensor values
- 🟢 **Live online/offline status** — devices with a power property show `[ON]`, `[OFF]`, or `[OFFLINE]` badges; sensors, speakers, and locks show no badge
- ⚡ **Scenes** — one-tap triggering of all your manual Mi Home scenes
- 🔄 **Per-device refresh** — re-read live values any time
- 🍞 **Toast notifications** for success / error feedback
- 📋 **Device actions** — run any MIoT action (e.g. start/stop, feed, identify)
- 🌙 **Dark theme**, responsive grid layout

---

## 📋 Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12 or newer |
| [`uv`](https://docs.astral.sh/uv/) | latest (replaces pip/venv) |
| Mi Home account | with devices already added in the app |

Install `uv` if you don't have it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 🚀 Quick Start

### 1. Clone / enter the project directory

```bash
cd /path/to/mijia_front
```

### 2. Install dependencies

```bash
uv sync
```

This creates a `.venv` and installs `fastapi`, `uvicorn`, and `mijiaapi` automatically.

### 3. Start the server

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

Or use the built-in entry point:

```bash
uv run python main.py
```

### 4. Open the dashboard

Open your browser and navigate to:

```
http://localhost:8765
```

---

## 🔐 First-Time Login

On first launch (or after your token expires) the dashboard shows a login screen:

1. Click **"Get QR Code"**
2. A QR code image from Xiaomi's servers is displayed
3. Open the **Mi Home (米家) app** on your phone → tap the **scan icon** (top-right)
4. Scan the QR code and confirm in the app
5. The dashboard detects the scan automatically and loads your devices

Auth credentials are saved to `~/.config/mijia-api/auth.json` and are valid for **~30 days**. Subsequent visits skip the login step.

> **Note:** If the QR code expires before you scan it (2-minute window), click **"Try Again"** to generate a fresh one.

---

## 🗂️ Project Structure

```
mijia_front/
├── main.py              # FastAPI backend — all REST API endpoints
├── launcher.py          # macOS app entry point (starts server + opens browser)
├── mijia_iot.spec       # PyInstaller build spec for the macOS .app bundle
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Locked dependency versions
└── static/
    ├── index.html       # Vue 3 frontend (single self-contained file)
    ├── icon.svg         # App icon source (SVG)
    └── icon.icns        # Generated macOS icon (auto-built from icon.svg)
```

---

## 🌐 API Reference

The backend exposes a REST API (also browsable at `http://localhost:8765/docs`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/auth/status` | Check if the token is valid |
| `POST` | `/api/auth/start` | Initiate QR login; returns QR image URL |
| `GET` | `/api/homes` | List all Mi Home homes |
| `GET` | `/api/devices` | List all devices across all homes |
| `GET` | `/api/device/{did}/info` | MIoT spec for a device (properties + actions) |
| `POST` | `/api/device/{did}/props/get` | Batch-read property values |
| `POST` | `/api/device/{did}/prop/set` | Write a single property value |
| `POST` | `/api/device/{did}/action` | Execute a device action |
| `GET` | `/api/scenes` | List all manual scenes |
| `POST` | `/api/scenes/{scene_id}/run` | Trigger a manual scene |

### Example — toggle a light on/off

```bash
curl -X POST http://localhost:8765/api/device/YOUR_DID/prop/set \
  -H "Content-Type: application/json" \
  -d '{"siid": 2, "piid": 1, "value": true}'
```

### Example — batch-read properties

```bash
curl -X POST http://localhost:8765/api/device/YOUR_DID/props/get \
  -H "Content-Type: application/json" \
  -d '{"props": [{"siid": 2, "piid": 1}, {"siid": 2, "piid": 2}]}'
```

> `siid` (service ID) and `piid` / `aiid` (property / action ID) values come from the [MIoT spec database](https://home.miot-spec.com/spec/{model}), substituting your device's model string (e.g. `yeelink.light.lamp4`).

---

## ⚙️ Configuration

| Option | How to change |
|--------|---------------|
| Server port | Pass `--port XXXX` to `uvicorn` |
| Server host | Pass `--host 0.0.0.0` to expose on LAN |
| Auth file location | Edit `mijiaAPI(auth_data_path=...)` in `main.py` |
| Auto-reload on code change | Add `--reload` flag (already in quick-start command) |

To run on a different port, e.g. 8080:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 🍎 macOS App

You can run the dashboard as a native **macOS `.app` bundle** — no terminal required. Double-clicking the app starts the server and opens the dashboard in your default browser.

### Build the app

Install the dev dependencies (only needed once):

```bash
uv add --dev pyinstaller cairosvg
```

Convert the SVG icon to `.icns`, then build:

```bash
.venv/bin/python -c "
import cairosvg, os
iconset = '/tmp/mijia.iconset'; os.makedirs(iconset, exist_ok=True)
for s in [16, 32, 128, 256, 512]:
    cairosvg.svg2png(url='static/icon.svg', write_to=f'{iconset}/icon_{s}x{s}.png',    output_width=s,   output_height=s)
    cairosvg.svg2png(url='static/icon.svg', write_to=f'{iconset}/icon_{s}x{s}@2x.png', output_width=s*2, output_height=s*2)
"
iconutil -c icns /tmp/mijia.iconset -o static/icon.icns
.venv/bin/pyinstaller mijia_iot.spec
```

The app appears at `dist/Mijia IoT.app`. Drag it to your **Applications** folder to install it system-wide.

### Run the app

```bash
open "dist/Mijia IoT.app"
```

Or double-click it in Finder. The server starts on `http://localhost:8765` and your browser opens automatically.

### Rebuild after code changes

```bash
rm -rf build dist
.venv/bin/pyinstaller mijia_iot.spec
```

If you also updated `icon.svg`, regenerate `icon.icns` first:

```bash
.venv/bin/python -c "
import cairosvg, os
iconset = '/tmp/mijia.iconset'; os.makedirs(iconset, exist_ok=True)
for s in [16, 32, 128, 256, 512]:
    cairosvg.svg2png(url='static/icon.svg', write_to=f'{iconset}/icon_{s}x{s}.png',    output_width=s,   output_height=s)
    cairosvg.svg2png(url='static/icon.svg', write_to=f'{iconset}/icon_{s}x{s}@2x.png', output_width=s*2, output_height=s*2)
"
iconutil -c icns /tmp/mijia.iconset -o static/icon.icns
```

> **Note:** Auth credentials are stored in `~/.config/mijia-api/auth.json`, outside the bundle, so they persist across rebuilds.

> **Optional menu-bar icon:** Install `rumps` (`uv add rumps`) and rebuild. A menu-bar icon with a **Quit** option will appear automatically.

---



## 🖥️ Running as a Background Service (macOS launchd)

Create `~/Library/LaunchAgents/com.mijia.dashboard.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mijia.dashboard</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/mijia_front/.venv/bin/uvicorn</string>
    <string>main:app</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8765</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/mijia_front</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.mijia.dashboard.plist
```

---

## 🛠️ Troubleshooting

**QR code doesn't appear / "Failed to obtain QR code"**
- Check your internet connection — the QR image is fetched from Xiaomi's servers.
- Try clicking "Try Again".

**Devices list is empty**
- Make sure you completed the QR login successfully.
- Check that your Mi Home account has devices. Try restarting the server.

**Property values show "—"**
- Some devices report properties only when online. Check device connectivity in the Mi Home app.
- Click **↻ Refresh** on the device card to re-poll.

**Device shows `[OFFLINE]` incorrectly**
- BLE devices (e.g. locks) may report `isOnline: 0` in the Xiaomi cloud even when reachable locally. Lock devices are intentionally excluded from the online/offline badge to avoid false positives.
- If a non-lock device shows `[OFFLINE]` but is working, check device connectivity in the Mi Home app — the cloud may take a few minutes to reflect the current state.

**`uv sync` fails**
- Ensure Python 3.12+ is available: `python3 --version`
- Update uv: `uv self update`

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| [`mijiaapi`](https://github.com/Do1e/mijia-api) | Mi Home API client (auth, devices, properties, actions) |
| [`fastapi`](https://fastapi.tiangolo.com/) | Async REST API framework |
| [`uvicorn`](https://www.uvicorn.org/) | ASGI server |
| [Vue 3](https://vuejs.org/) (CDN) | Reactive frontend UI |
| [`pyinstaller`](https://pyinstaller.org) *(dev)* | Packages the app into a macOS `.app` bundle |
| [`cairosvg`](https://cairosvg.org) *(dev)* | Converts `icon.svg` to `icon.icns` for the app bundle |

---

## 📄 License

MIT — use freely, no warranty.
