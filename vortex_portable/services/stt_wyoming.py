"""Wyoming Whisper STT adapter via Wyoming protocol."""

from __future__ import annotations

import asyncio
from typing import Optional

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

from ..interfaces import SpeechToText
from ..models import CapturedAudio


class WyomingSpeechToText(SpeechToText):
    """
    Speech-to-text implementation using Wyoming Whisper protocol.

    Uses the official Wyoming protocol library for proper communication.
    
    Args:
        host: Wyoming service host (e.g., "localhost")
        port: Wyoming service port (e.g., 10300 for whisper)
        timeout: Connection timeout in seconds.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 10300,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    def transcribe(self, audio: CapturedAudio, *, language: Optional[str] = None) -> str:
        if not audio.data:
            raise ValueError("No audio data provided for transcription.")

        # Wyoming expects raw PCM data, not WAV
        # Run async transcription in event loop
        try:
            print(f"[stt] Connecting to {self._host}:{self._port}...")
            result = asyncio.run(self._async_transcribe(audio.data, audio.sample_rate, language))
            print(f"[stt] Transcription complete")
            return result
        except Exception as exc:
            raise RuntimeError(f"Wyoming Whisper error: {exc}") from exc

    async def _async_transcribe(self, pcm_data: bytes, sample_rate: int, language: Optional[str]) -> str:
        """Perform async transcription using Wyoming protocol."""
        try:
            # Normalize language code: strip region codes (en-US -> en)
            lang = language or "en"
            if "-" in lang:
                lang = lang.split("-")[0]
            
            async with AsyncTcpClient(self._host, self._port) as client:
                # Start transcription
                await client.write_event(Transcribe(language=lang).event())
                
                # Send audio start
                await client.write_event(
                    AudioStart(
                        rate=sample_rate,
                        width=2,
                        channels=1,
                    ).event()
                )
                
                # Send audio data in chunks (raw PCM)
                chunk_size = 8192
                for i in range(0, len(pcm_data), chunk_size):
                    chunk = pcm_data[i:i + chunk_size]
                    await client.write_event(
                        AudioChunk(
                            audio=chunk,
                            rate=sample_rate,
                            width=2,
                            channels=1,
                        ).event()
                    )
                
                # Send audio stop
                await client.write_event(AudioStop().event())
                
                # Wait for transcript
                while True:
                    event = await asyncio.wait_for(
                        client.read_event(),
                        timeout=self._timeout
                    )
                    
                    if event is None:
                        break
                    
                    if Transcript.is_type(event.type):
                        transcript = Transcript.from_event(event)
                        return transcript.text.strip()
                
                raise RuntimeError("No transcript received from Wyoming Whisper")
                
        except asyncio.TimeoutError:
            raise RuntimeError(f"Wyoming Whisper request timed out after {self._timeout}s")
