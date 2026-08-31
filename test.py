import asyncio
import edge_tts


async def main():
    text = "Namaste sir, main online hoon."
    voice = "hi-IN-MadhurNeural"

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
    )

    with open("edge_test.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])

    print("Edge TTS audio created: edge_test.mp3")


asyncio.run(main())