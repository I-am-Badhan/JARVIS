import asyncio
import uuid

import edge_tts

from livekit.agents import tts


class EdgeTTS(tts.TTS):
    def __init__(
        self,
        voice: str = "hi-IN-MadhurNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,
            ),
            sample_rate=24000,
            num_channels=1,
        )

        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    def synthesize(
        self,
        text: str,
        *,
        conn_options=None,
    ):
        return EdgeTTSStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )


class EdgeTTSStream(tts.ChunkedStream):
    def __init__(
        self,
        tts: EdgeTTS,
        input_text: str,
        conn_options=None,
    ):
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )

        self._edge_tts = tts
        self._segment_id = str(uuid.uuid4())

    async def _run(self, output_emitter):

        output_emitter.initialize(
            request_id=self._segment_id,
            sample_rate=24000,
            num_channels=1,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=True,
        )

        output_emitter.start_segment(
            segment_id=self._segment_id
        )

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",

            "-hide_banner",
            "-loglevel",
            "error",

            "-f",
            "mp3",

            "-i",
            "pipe:0",

            "-f",
            "s16le",

            "-ar",
            "24000",

            "-ac",
            "1",

            "pipe:1",

            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        communicate = edge_tts.Communicate(
            text=self.input_text,
            voice=self._edge_tts.voice,
            rate=self._edge_tts.rate,
            volume=self._edge_tts.volume,
            pitch=self._edge_tts.pitch,
        )

        async def read_pcm():

            while True:

                pcm = await process.stdout.read(9600)

                if not pcm:
                    break

                output_emitter.push(pcm)

        pcm_task = asyncio.create_task(
            read_pcm()
        )

        try:

            async for chunk in communicate.stream():

                if chunk["type"] != "audio":
                    continue

                data = chunk["data"]

                if not data:
                    continue

                process.stdin.write(data)

                await process.stdin.drain()

            process.stdin.close()

            await process.stdin.wait_closed()

            await pcm_task

            await process.wait()

            if process.returncode != 0:

                stderr = await process.stderr.read()

                raise RuntimeError(
                    "FFmpeg streaming failed: "
                    + stderr.decode(
                        errors="ignore"
                    )
                )

        except Exception:

            if process.returncode is None:

                process.kill()

                await process.wait()

            raise

        finally:

            if process.returncode is None:

                process.kill()

                await process.wait()

        output_emitter.flush()