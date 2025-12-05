"""Console TTS implementation that prints assistant responses."""

from __future__ import annotations

from ..interfaces import TextToSpeech


class ConsoleTextToSpeech(TextToSpeech):
    """
    Speaks by printing to stdout.

    Swap this out for Piper, a speaker driver, or a cloud TTS service later.
    """

    def speak(self, text: str) -> None:
        print(f"Assistant: {text}")
