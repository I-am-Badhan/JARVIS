import os
import socket
import ssl
import time
import json
import urllib.request
import psutil
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from livekit import api
from livekit.api import AccessToken, VideoGrants
from dotenv import load_dotenv

load_dotenv(".env.local")

app = FastAPI(title="JARVIS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://127.0.0.1:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

ssl_ctx = ssl._create_unverified_context()
weather_cache = {"data": None, "timestamp": 0}

WMO_WEATHER_CODES = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Haze", 51: "Light Drizzle", 53: "Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Snow", 80: "Rain Showers", 95: "Thunderstorm"
}

# -------------------------------------------------------------
# Zero-Failure Music State Hub
# -------------------------------------------------------------
current_music_state = {
    "action": "NONE",
    "id": "",
    "title": "Ready to Play",
    "artist": "J.A.R.V.I.S. Audio Subsystem",
    "thumbnail": "",
    "updated_at": 0
}

@app.post("/api/music/command")
async def receive_music_command(payload: dict):
    global current_music_state
    current_music_state = {
        **payload,
        "updated_at": time.time()
    }
    print(f"[MUSIC HUB] State updated -> {current_music_state.get('title')}")
    return {"status": "dispatched", "title": current_music_state.get("title")}

@app.get("/api/music/state")
async def get_music_state():
    return current_music_state


@app.get("/api/token")
async def get_token():
    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("commander")
        .with_name("Commander")
        .with_grants(VideoGrants(room_join=True, room="jarvis-room"))
    )

    try:
        http_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
        async with api.LiveKitAPI(http_url, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) as lk_api:
            await lk_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    room="jarvis-room",
                    agent_name=""
                )
            )
    except Exception:
        pass

    return {
        "url": LIVEKIT_URL,
        "token": token.to_jwt()
    }

@app.get("/api/system-stats")
async def get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=None)
    ram_percent = psutil.virtual_memory().percent
    disk_path = "C:\\" if os.name == "nt" else "/"
    disk_percent = psutil.disk_usage(disk_path).percent

    battery = psutil.sensors_battery()
    if battery:
        power_pct = round(battery.percent)
        power_status = "CHARGING" if battery.power_plugged else "BATTERY"
    else:
        power_pct = 100
        power_status = "OPTIMAL"

    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        net_status = "STABLE"
    except OSError:
        net_status = "OFFLINE"

    return {
        "cpu": cpu_percent,
        "ram": ram_percent,
        "disk": disk_percent,
        "power": {
            "percent": power_pct,
            "status": power_status
        },
        "network": net_status
    }

@app.get("/api/weather")
async def get_weather():
    now = time.time()
    if weather_cache["data"] and (now - weather_cache["timestamp"] < 600):
        return weather_cache["data"]

    try:
        lat, lon = 22.346, 87.232
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        with urllib.request.urlopen(weather_url, context=ssl_ctx, timeout=4) as w_resp:
            w_data = json.loads(w_resp.read().decode())

        curr = w_data.get("current_weather", {})
        temp = round(curr.get("temperature", 28))
        code = curr.get("weathercode", 0)
        condition = WMO_WEATHER_CODES.get(code, "Clear")

        result = {
            "city": "KHARAGPUR, IN",
            "temp": f"{temp}°C",
            "condition": condition
        }
        weather_cache["data"] = result
        weather_cache["timestamp"] = now
        return result

    except Exception:
        return {
            "city": "KHARAGPUR, IN",
            "temp": "28°C",
            "condition": "Clear"
        }

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")