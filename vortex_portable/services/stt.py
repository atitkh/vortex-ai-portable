"""STT placeholder that echoes the typed transcript hint."""

from __future__ import annotations

from typing import Optional

from ..interfaces import SpeechToText
from ..models import CapturedAudio


class EchoSpeechToText(SpeechToText):
    """
    Minimal STT implementation for the CLI harness.

    It simply trusts the transcript hint supplied by :class:`ConsoleRecorder`.
    Replace this class with a Whisper, VAD-backed, or cloud STT service without
    changing the rest of the pipeline.
    """

    def transcribe(self, audio: CapturedAudio, *, language: Optional[str] = None) -> str:
        if audio.transcript_hint:
            return audio.transcript_hint

        raise ValueError("No transcript_hint found; supply audio decoding to enable STT.")
