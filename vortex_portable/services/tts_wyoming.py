"""Wyoming Piper TTS adapter via Wyoming protocol."""

from __future__ import annotations

import asyncio
from typing import Optional

from wyoming.audio import AudioChunk, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize

from ..interfaces import TextToSpeech


class WyomingTextToSpeech(TextToSpeech):
    """
    Text-to-speech using Wyoming Piper protocol.

    Uses the official Wyoming protocol library for proper communication.
    
    Args:
        host: Wyoming service host (e.g., "localhost")
        port: Wyoming service port (e.g., 10200 for piper)
        timeout: Connection timeout in seconds.
        sample_rate: Playback sample rate (Hz).
        speaker: Optional speaker/voice identifier.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 10200,
        timeout: float = 30.0,
        sample_rate: int = 22050,
        speaker: Optional[str] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sample_rate = sample_rate
        self._speaker = speaker

    def speak(self, text: str) -> None:
        if not text.strip():
            return

        try:
            print(f"[tts] Connecting to {self._host}:{self._port}...")
            asyncio.run(self._async_speak(text))
            print(f"[tts] Playback complete")
        except Exception as exc:
            raise RuntimeError(f"Wyoming Piper error: {exc}") from exc

    async def _async_speak(self, text: str) -> None:
        """Perform async TTS using Wyoming protocol."""
        try:
            async with AsyncTcpClient(self._host, self._port) as client:
                # Start synthesis
                await client.write_event(
                    Synthesize(
                        text=text,
                        voice=self._speaker,
                    ).event()
                )
                
                # Collect audio chunks
                audio_chunks = []
                actual_rate = self._sample_rate
                actual_width = 2
                actual_channels = 1
                
                while True:
                    event = await asyncio.wait_for(
                        client.read_event(),
                        timeout=self._timeout
                    )
                    
                    if event is None:
                        break
                    
                    if AudioChunk.is_type(event.type):
                        chunk = AudioChunk.from_event(event)
                        audio_chunks.append(chunk.audio)
                        actual_rate = chunk.rate
                        actual_width = chunk.width
                        actual_channels = chunk.channels
                    elif AudioStop.is_type(event.type):
                        break
                
                if not audio_chunks:
                    raise RuntimeError("Wyoming Piper produced no audio output")
                
                # Combine and play audio
                audio_data = b"".join(audio_chunks)
                self._play_audio(audio_data, actual_rate, actual_width, actual_channels)
                
        except asyncio.TimeoutError:
            raise RuntimeError(f"Wyoming Piper request timed out after {self._timeout}s")

    def _play_audio(self, audio_data: bytes, rate: int, width: int, channels: int) -> None:
        """Play audio data through sounddevice."""
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("sounddevice and numpy required for audio playback. Install via pip.") from exc

        # Convert based on sample width
        if width == 2:
            pcm = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif width == 4:
            pcm = np.frombuffer(audio_data, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise RuntimeError(f"Unsupported audio width: {width}")
        
        # Reshape for channels if needed
        if channels > 1:
            pcm = pcm.reshape(-1, channels)
        
        sd.play(pcm, samplerate=rate, device=sd.default.device[1])
        sd.wait()
