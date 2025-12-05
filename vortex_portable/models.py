"""Shared dataclasses for the assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Sequence

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    """Represents a single chat turn."""

    role: Role
    content: str

    def as_dict(self) -> Dict[str, str]:
        """Convert to the API shape expected by the chat endpoint."""
        return {"role": self.role, "content": self.content}


@dataclass
class CapturedAudio:
    """
    Audio blob captured by the recorder.

    Attributes:
        data: Raw PCM or encoded audio bytes.
        sample_rate: Sample rate in Hz (e.g., 16000).
        transcript_hint: Optional text used by the CLI harness in lieu of real STT.
        encoding: Audio encoding label (e.g., "pcm_s16le", "wav").
    """

    data: bytes
    sample_rate: int
    transcript_hint: Optional[str] = None
    encoding: str = "pcm_s16le"


@dataclass
class ChatResponse:
    """Normalized response returned by the chat service."""

    text: str
    conversation_id: Optional[str]
    raw: Dict[str, Any]


MessageSequence = Sequence[Message]
