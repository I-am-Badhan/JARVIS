import asyncio
from livekit.agents import function_tool, RunContext, ToolError
from services.music_manager import music_manager

@function_tool(
    name="play_music_in_ui",
    description="PRIMARY AND DEFAULT TOOL for playing ANY song, music, track, or artist requested by the user (e.g., 'play Kesariya', 'gana sunao', 'play music', 'Arijit Singh ka gana chalao'). ALWAYS plays directly inside the dedicated JARVIS Music HUD window."
)
async def play_music_in_ui(context: RunContext, song_name: str) -> str:
    try:
        track = await asyncio.to_thread(music_manager.search_track, song_name)
        if not track or not track.get("id"):
            raise ToolError(f"'{song_name}' ka koi audio stream nahi mila.")

        music_manager.play_track(track)
        return f"Boss, JARVIS Music Widget mein '{track['title']}' play ho raha hai."
    except Exception as e:
        raise ToolError(f"Music play karne mein issue: {e}")


@function_tool(
    name="control_music_player",
    description="Control the active JARVIS Music HUD player playback: 'pause', 'resume', 'play', 'forward', 'rewind', 'next', 'previous', 'close', or 'stop'."
)
async def control_music_player(context: RunContext, action: str) -> str:
    res = music_manager.control_playback(action)
    return f"Boss, Music Player command '{res}' execute kar di gayi hai."