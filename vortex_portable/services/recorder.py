"""CLI recorder that captures typed input as if it were audio."""

from __future__ import annotations

from ..interfaces import AudioRecorder
from ..models import CapturedAudio


class ConsoleRecorder(AudioRecorder):
    """
    Records pseudo-audio by asking the user for typed text.

    Usage:
        recorder = ConsoleRecorder()
        audio = recorder.record()
        print(audio.transcript_hint)
    """

    def record(self) -> CapturedAudio:
        text = input("You: ").strip()
        # When integrating a real microphone, replace this logic with actual capture.
        return CapturedAudio(
            data=b"",
            sample_rate=16000,
            transcript_hint=text,
            encoding="text/simulated",
        )
