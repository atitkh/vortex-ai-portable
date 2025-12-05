"""Custom exceptions for the assistant."""

from __future__ import annotations


class ChatClientError(RuntimeError):
    """Raised when the chat service responds with an error or invalid payload."""


class WakeWordCancelled(RuntimeError):
    """Raised when the wake flow is intentionally cancelled by the user."""
