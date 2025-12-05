"""Remote Whisper STT adapter via HTTP API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Optional

from ..interfaces import SpeechToText
from ..models import CapturedAudio


class RemoteSpeechToText(SpeechToText):
    """
    Speech-to-text implementation using a remote Whisper API.

    Args:
        base_url: Base URL for the Whisper service (e.g., "http://whisper:9000")
        timeout: HTTP timeout in seconds.
        ssl_context: Optional SSL context for HTTPS.

    Expected API format:
        POST /transcribe
        Content-Type: audio/wav or multipart/form-data
        Body: audio data (PCM bytes)
        
        Response: {"text": "transcribed text"}
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/transcribe"
        self._timeout = timeout
        self._ssl_context = ssl_context

    def transcribe(self, audio: CapturedAudio, *, language: Optional[str] = None) -> str:
        if not audio.data:
            raise ValueError("No audio data provided for transcription.")

        # Build multipart form data or send raw PCM
        # Most Whisper APIs expect WAV format
        wav_data = self._pcm_to_wav(audio.data, audio.sample_rate)
        
        request = urllib.request.Request(
            self._endpoint,
            data=wav_data,
            headers={
                "Content-Type": "audio/wav",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=self._ssl_context) as response:  # type: ignore[arg-type]
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Whisper request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Whisper request could not reach the server: {exc.reason}") from exc

        if "application/json" in content_type:
            try:
                payload = json.loads(body.decode("utf-8"))
                text = payload.get("text", "")
                return text.strip()
            except json.JSONDecodeError:
                pass

        # Fallback: assume plain text response
        return body.decode("utf-8", errors="ignore").strip()

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int) -> bytes:
        """Convert raw PCM data to WAV format."""
        import struct
        
        # WAV header for 16-bit PCM mono audio
        channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        data_size = len(pcm_data)
        
        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + data_size,  # file size - 8
            b'WAVE',
            b'fmt ',
            16,  # fmt chunk size
            1,   # PCM format
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b'data',
            data_size
        )
        
        return header + pcm_data
