"""Whisper-based STT adapter."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import numpy as np

from ..interfaces import SpeechToText
from ..models import CapturedAudio


class WhisperSpeechToText(SpeechToText):
    """
    Speech-to-text implementation using OpenAI Whisper.

    Args:
        model_size: Whisper model name (e.g., "tiny", "base", "small", "medium", "large").
        device: Device string passed to whisper (e.g., "cpu", "cuda").

    Notes:
        - Requires the `whisper` package and ffmpeg.
        - Expects 16-bit PCM audio bytes; resampling is handled by Whisper internally.
    """

    def __init__(self, *, model_size: str = "tiny", device: Optional[str] = None) -> None:
        self.model_size = model_size
        self.device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = _load_whisper(self.model_size, device=self.device)
        return self._model

    def transcribe(self, audio: CapturedAudio, *, language: Optional[str] = None) -> str:
        if not audio.data:
            raise ValueError("No audio data provided for transcription.")

        pcm = np.frombuffer(audio.data, dtype=np.int16).astype(np.float32) / 32768.0
        result = self.model.transcribe(pcm, language=language)
        text = result.get("text", "")
        return text.strip()


@lru_cache(maxsize=1)
def _load_whisper(model_size: str, device: Optional[str]):
    try:
        import whisper  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("whisper package is required for WhisperSpeechToText. Install via pip.") from exc

    return whisper.load_model(model_size, device=device)
