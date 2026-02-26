"""Remote Piper TTS adapter via HTTP API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Optional

from ..interfaces import TextToSpeech


class RemoteTextToSpeech(TextToSpeech):
    """
    Text-to-speech using a remote Piper API.

    Args:
        base_url: Base URL for the Piper service (e.g., "http://piper:5000")
        timeout: HTTP timeout in seconds.
        sample_rate: Playback sample rate (Hz).
        ssl_context: Optional SSL context for HTTPS.

    Expected API format:
        POST /synthesize
        Content-Type: application/json
        Body: {"text": "text to speak", "speaker": "optional"}
        
        Response: audio/wav (raw audio data)
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
        sample_rate: int = 16000,
        speaker: Optional[str] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/synthesize"
        self._timeout = timeout
        self._sample_rate = sample_rate
        self._speaker = speaker
        self._ssl_context = ssl_context

    def speak(self, text: str) -> None:
        if not text.strip():
            return

        payload = {"text": text}
        if self._speaker:
            payload["speaker"] = self._speaker

        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=self._ssl_context) as response:  # type: ignore[arg-type]
                audio_data = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Piper request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Piper request could not reach the server: {exc.reason}") from exc

        if not audio_data:
            raise RuntimeError("Piper produced no audio output.")

        # Play the audio using sounddevice
        self._play_audio(audio_data)

    def _play_audio(self, audio_data: bytes) -> None:
        """Play audio data through sounddevice."""
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("sounddevice and numpy required for audio playback. Install via pip.") from exc

        # Assume the response is WAV format - parse it
        # Skip WAV header (44 bytes) if present
        if audio_data.startswith(b'RIFF'):
            pcm_data = audio_data[44:]
        else:
            pcm_data = audio_data

        # Convert to numpy array and play
        pcm = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(pcm, samplerate=self._sample_rate, device=sd.default.device[1])
        sd.wait()
