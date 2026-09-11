import os
import socket
import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from livekit.api import AccessToken, VideoGrants
from dotenv import load_dotenv

load_dotenv(".env.local")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://127.0.0.1:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

# 1. LiveKit Room Access Token Endpoint
@app.get("/api/token")
async def get_token():
    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("commander")
        .with_name("Commander")
        .with_grants(VideoGrants(room_join=True, room="jarvis-room"))
    )
    return {
        "url": LIVEKIT_URL,
        "token": token.to_jwt()
    }

# 2. Real System Hardware Telemetry Endpoint
@app.get("/api/system-stats")
async def get_system_stats():
    # Real CPU, RAM, Disk usage
    cpu_percent = psutil.cpu_percent(interval=None)
    ram_percent = psutil.virtual_memory().percent
    disk_path = "C:\\" if os.name == "nt" else "/"
    disk_percent = psutil.disk_usage(disk_path).percent

    # Real Battery / Power calculation
    battery = psutil.sensors_battery()
    if battery:
        power_pct = round(battery.percent)
        power_status = "CHARGING" if battery.power_plugged else "BATTERY"
    else:
        # Desktop / Wall Power
        power_pct = 100
        power_status = "OPTIMAL"

    # Real Network Connectivity Ping
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

# Serve frontend directory
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")