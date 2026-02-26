"""Protocol interfaces for dependency injection."""

from __future__ import annotations

from typing import Iterator, Optional, Protocol, runtime_checkable

from .models import CapturedAudio, ChatResponse


class WakeWordDetector(Protocol):
    """Waits for a wake signal before recording."""

    def await_wake_word(self) -> bool:
        """
        Block until the wake word is detected.

        Returns:
            True when woken, False when the session should exit.
        """


class AudioRecorder(Protocol):
    """Captures audio from the user."""

    def record(self) -> CapturedAudio:
        """Return a captured audio buffer."""


class SpeechToText(Protocol):
    """Transcribes recorded audio into text."""

    def transcribe(self, audio: CapturedAudio, *, language: Optional[str] = None) -> str:
        """Return the transcribed text for the provided audio."""


class ChatClient(Protocol):
    """Sends chat messages to the Vortex backend."""

    def chat(self, message: str, *, conversation_id: str, debug: bool = False) -> ChatResponse:
        """Send a single message into a conversation and return the assistant reply."""


@runtime_checkable
class StreamingChatClient(Protocol):
    """
    Chat client that supports streaming responses.
    
    Streaming allows the assistant to start speaking before the full response
    is generated, significantly reducing perceived latency.
    """

    def chat(self, message: str, *, conversation_id: str, debug: bool = False) -> ChatResponse:
        """Send a single message into a conversation and return the assistant reply."""

    def chat_stream(
        self, 
        message: str, 
        *, 
        conversation_id: str,
        system_prompt: Optional[str] = None,
        debug: bool = False
    ) -> Iterator[str]:
        """
        Send a message and stream response chunks as they arrive.
        
        Yields:
            Text chunks as they become available
        """


class TextToSpeech(Protocol):
    """Speaks assistant responses."""

    def speak(self, text: str) -> None:
        """Render speech for the provided text."""
