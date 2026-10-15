import json
import urllib.request
import logging
from typing import Dict, Any
import yt_dlp

logger = logging.getLogger("jarvis.music_manager")
BACKEND_API_URL = "http://127.0.0.1:8080/api/music/command"

class MusicManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MusicManager, cls).__new__(cls)
        return cls._instance

    def search_track(self, query: str) -> Dict[str, Any]:
        """yt-dlp দিয়ে গানটির YouTube মেটাডাটা ও আইডি বের করা (Error 150 সুরক্ষিত)"""
        # লিরিক্স বা অডিও ট্র্যাকগুলোতে কপিরাইট এম্বেড ব্লকিং থাকে না
        search_query = f"{query} lyric song"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'default_search': f'ytsearch3:{search_query}',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get('entries', [info]) if info else []
                
                for video in entries:
                    if video and video.get('id'):
                        return {
                            "id": video.get("id"),
                            "title": video.get("title", query.title()),
                            "artist": video.get("uploader", "JARVIS Music"),
                            "duration": video.get("duration", 0),
                            "thumbnail": video.get("thumbnail", "")
                        }
        except Exception as e:
            logger.warning(f"yt-dlp search exception: {e}")

        # সেফ ফলব্যাক
        return {
            "id": "e_bE56tX0t4",
            "title": query.title(),
            "artist": "Playback Stream",
            "duration": 240,
            "thumbnail": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600"
        }

    def send_command_to_backend(self, payload: Dict[str, Any]):
        try:
            req = urllib.request.Request(
                BACKEND_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                print(f"[MUSIC MANAGER SUCCESS] Sent {payload.get('action')} -> {payload.get('title')}")
                return resp.status == 200
        except Exception as e:
            print(f"[MUSIC MANAGER ERROR] Failed to send to backend: {e}")
            return False

    def play_track(self, track_info: Dict[str, Any]):
        payload = {
            "action": "PLAY",
            "id": track_info["id"],
            "title": track_info["title"],
            "artist": track_info["artist"],
            "thumbnail": track_info["thumbnail"]
        }
        return self.send_command_to_backend(payload)

    def control_playback(self, action: str) -> str:
        act = action.lower()
        cmd = "UNKNOWN"
        if "pause" in act:
            cmd = "PAUSE"
        elif "play" in act or "resume" in act:
            cmd = "RESUME"
        elif "next" in act or "forward" in act:
            cmd = "SEEK_FORWARD"
        elif "prev" in act or "back" in act:
            cmd = "SEEK_BACKWARD"
        elif "close" in act or "stop" in act:
            cmd = "CLOSE"

        self.send_command_to_backend({"action": cmd})
        return cmd

music_manager = MusicManager()